import os
import json
import argparse
import gdown
import shutil
import csv
import random
from tqdm import tqdm

# Standard VFF-16 classes
CLASSES = ["jpg", "gif", "doc", "xls", "ppt", "html", "text", "pdf", "rtf", "png", "log", "csv", "gz", "swf", "eps", "ps"]

def setup_base_directories():
    os.makedirs("./data/generated", exist_ok=True)
    os.makedirs("./data/custom", exist_ok=True)
    os.makedirs("./data/FFT", exist_ok=True)
    print("Ensured data root structure: ./data/{generated, custom} and ./data/FFT")

def save_classes(class_list):
    class_map = {str(i): cls for i, cls in enumerate(class_list)}
    with open("./data/FFT/classes.json", "w") as f:
        json.dump(class_map, f, indent=4)
    print(f"Saved ./data/FFT/classes.json with {len(class_list)} classes.")

# --- Mode: Generate (from GovDocs1/Source) ---
def generate_vff16_from_source(output_root, sector_size, class_to_files, target_classes, limit_bytes):
    print(f"Generating balanced VFF-16. Limit per class: {limit_bytes / (1024*1024):.2f} MB")
    output_dir = os.path.join(output_root, str(sector_size))
    metadata_csv = os.path.join(output_root, f"metadata_{sector_size}.csv")
    
    # Remove existing metadata for this sector size to avoid appending to old runs
    if os.path.exists(metadata_csv):
        os.remove(metadata_csv)

    for class_name in target_classes:
        class_files = class_to_files.get(class_name, [])
        output_class_dir = os.path.join(output_dir, class_name)
        os.makedirs(output_class_dir, exist_ok=True)
        
        all_fragments = []
        random.shuffle(class_files)
        total_bytes_processed = 0
        
        for fpath in tqdm(class_files, desc=f"Processing {class_name}"):
            if total_bytes_processed >= limit_bytes: break
            
            try:
                with open(fpath, "rb") as f: data = f.read()
            except: continue
            
            # If this file takes us over the limit, truncate it (aligned to sector size)
            if total_bytes_processed + len(data) > limit_bytes:
                remaining = limit_bytes - total_bytes_processed
                num_sectors_to_take = int(remaining // sector_size)
                if num_sectors_to_take == 0: break
                data = data[:num_sectors_to_take * sector_size]
            
            # Pad to sector size (only if not already aligned/truncated)
            padding_size = (sector_size - (len(data) % sector_size)) % sector_size
            if padding_size > 0: data += os.urandom(padding_size)
            
            num_sectors = len(data) // sector_size
            if num_sectors == 0: continue
            
            # Fragmentation logic
            num_frags = random.randint(1, min(10, num_sectors))
            splits = sorted(random.sample(range(1, num_sectors), num_frags - 1)) if num_frags > 1 else []
            splits = [0] + splits + [num_sectors]
            
            for i in range(num_frags):
                frag_data = data[splits[i]*sector_size : splits[i+1]*sector_size]
                all_fragments.append({
                    "data": frag_data,
                    "original_file": os.path.basename(fpath),
                    "start_sector_in_file": splits[i]
                })
            
            total_bytes_processed += len(data)

        # Shuffle fragments and save sectors
        random.shuffle(all_fragments)
        sample_idx = 0
        metadata_records = []
        for frag in all_fragments:
            frag_data = frag["data"]
            for i in range(len(frag_data) // sector_size):
                sector = frag_data[i*sector_size : (i+1)*sector_size]
                sample_name = f"sample_{sample_idx:06d}.bin"
                with open(os.path.join(output_class_dir, sample_name), "wb") as f:
                    f.write(sector)
                
                metadata_records.append({
                    "sample_name": sample_name,
                    "class": class_name,
                    "original_file": frag["original_file"],
                    "sector_index": frag["start_sector_in_file"] + i
                })
                sample_idx += 1
        
        if metadata_records:
            file_exists = os.path.isfile(metadata_csv)
            with open(metadata_csv, "a", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["sample_name", "class", "original_file", "sector_index"])
                if not file_exists: writer.writeheader()
                writer.writerows(metadata_records)
            
        print(f"Generated {sample_idx} sectors for {class_name}")

# --- Mode: Custom ---
def handle_custom(input_path, output_root, sector_size, target_class="unlabeled"):
    output_dir = os.path.join(output_root, str(sector_size), target_class)
    os.makedirs(output_dir, exist_ok=True)
    metadata_csv = os.path.join(output_root, f"metadata_{sector_size}.csv")
    
    files_to_process = []
    if os.path.isfile(input_path): 
        files_to_process.append(input_path)
    elif os.path.isdir(input_path):
        for root, _, filenames in os.walk(input_path):
            for f in filenames:
                files_to_process.append(os.path.join(root, f))

    all_mappings = []
    for fpath in files_to_process:
        file_name = os.path.basename(fpath)
        try:
            with open(fpath, "rb") as f:
                chunk_idx = 0
                while True:
                    chunk = f.read(sector_size)
                    if not chunk: break
                    if len(chunk) < sector_size:
                        chunk += b'\x00' * (sector_size - len(chunk))
                    
                    chunk_name = f"{file_name}_s{chunk_idx:06d}.bin"
                    with open(os.path.join(output_dir, chunk_name), "wb") as cf:
                        cf.write(chunk)
                    
                    all_mappings.append({
                        "chunk_name": chunk_name, 
                        "parent_file": file_name, 
                        "sector_index": chunk_idx, 
                        "class": target_class
                    })
                    chunk_idx += 1
            print(f"Processed {file_name} into {chunk_idx} chunks in folder '{target_class}'")
        except Exception as e:
            print(f"Error processing {fpath}: {e}")

    if all_mappings:
        file_exists = os.path.isfile(metadata_csv)
        with open(metadata_csv, "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["chunk_name", "parent_file", "sector_index", "class"])
            if not file_exists: writer.writeheader()
            writer.writerows(all_mappings)
        print(f"Metadata saved to {metadata_csv}")

def main():
    parser = argparse.ArgumentParser(description="Unified Data Preparation Tool.")
    subparsers = parser.add_subparsers(dest="mode", help="Execution mode")

    # Generate
    generate_parser = subparsers.add_parser("generate", help="Generate VFF-16 from source directory")
    generate_parser.add_argument("--source-dir", required=True)
    generate_parser.add_argument("--sector-size", type=int, choices=[512, 4096], default=512)
    generate_parser.add_argument("--max-mb-per-class", type=float, default=50.0)
    generate_parser.add_argument("--num-classes", type=int, help="Number of classes to select (top classes by size)")

    # Custom
    custom_parser = subparsers.add_parser("custom", help="Chunk custom files")
    custom_parser.add_argument("input")
    custom_parser.add_argument("--class-name", default="unlabeled")
    custom_parser.add_argument("--sector-size", type=int, choices=[512, 4096], default=512)

    args = parser.parse_args()
    setup_base_directories()

    if args.mode == "generate":
        # 1. Scan source directory and count bytes per class
        class_to_files = {}
        class_to_size = {}
        
        print(f"Scanning {args.source_dir} for available data...")
        for root, _, filenames in os.walk(args.source_dir):
            for f in filenames:
                ext = os.path.splitext(f)[1][1:].lower()
                if ext in CLASSES:
                    fpath = os.path.join(root, f)
                    size = os.path.getsize(fpath)
                    if ext not in class_to_files:
                        class_to_files[ext] = []
                        class_to_size[ext] = 0
                    class_to_files[ext].append(fpath)
                    class_to_size[ext] += size
        
        # 2. Sort by size and pick top N
        sorted_classes = sorted(class_to_size.items(), key=lambda x: x[1], reverse=True)
        num_to_pick = args.num_classes if args.num_classes else len(sorted_classes)
        top_n_info = sorted_classes[:num_to_pick]
        target_classes = [info[0] for info in top_n_info]
        
        # 3. Determine the minimum available bytes among the selected classes
        min_available_bytes = min([info[1] for info in top_n_info])
        
        # 4. Final limit is the minimum of (min_available, user_max_mb)
        limit_bytes = min(min_available_bytes, int(args.max_mb_per_class * 1024 * 1024))
        
        print(f"Selected top {len(target_classes)} classes: {target_classes}")
        print(f"Balancing dataset: Each class will be limited to {limit_bytes / (1024*1024):.2f} MB.")
        
        save_classes(target_classes)
        generate_vff16_from_source("./data/generated", args.sector_size, class_to_files, target_classes, limit_bytes)
        
    elif args.mode == "custom":
        save_classes(CLASSES)
        handle_custom(args.input, "./data/custom", args.sector_size, args.class_name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
