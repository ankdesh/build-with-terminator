import os
import zipfile
import requests
import json
import argparse
import gdown
import shutil
import csv
import random
from tqdm import tqdm

# Dataset URLs from JSANet repository and research
DATASET_ID = "1LnhoytWihRRJ7CfhLQ76F8YxwxRDlZN3"

# Standard VFF-16 classes
CLASSES = ["jpg", "gif", "doc", "xls", "ppt", "html", "text", "pdf", "rtf", "png", "log", "csv", "gz", "swf", "eps", "ps"]

def setup_base_directories():
    os.makedirs("./data/benchmark", exist_ok=True)
    os.makedirs("./data/generated", exist_ok=True)
    os.makedirs("./data/custom", exist_ok=True)
    os.makedirs("./data/FFT", exist_ok=True)
    print("Ensured data root structure: ./data/{benchmark, generated, custom} and ./data/FFT")

def save_classes():
    class_map = {str(i): cls for i, cls in enumerate(CLASSES)}
    with open("./data/FFT/classes.json", "w") as f:
        json.dump(class_map, f, indent=4)
    print("Saved ./data/FFT/classes.json")

# --- Mode: Benchmark ---
def download_benchmark(sector_size, max_gb=None):
    print(f"Attempting to download benchmark {sector_size}-byte configuration...")
    zip_name = f"rff_{sector_size}.zip"
    output_dir = f"./data/benchmark/{sector_size}"
    os.makedirs(output_dir, exist_ok=True)

    try:
        if not os.path.exists(zip_name):
            print(f"Downloading dataset archive using ID: {DATASET_ID}")
            gdown.download(id=DATASET_ID, output=zip_name, quiet=False)
        
        if os.path.exists(zip_name):
            print(f"Extracting {zip_name}...")
            with zipfile.ZipFile(zip_name, 'r') as zip_ref:
                all_files = zip_ref.namelist()
                if max_gb:
                    print(f"Limiting extraction to a small section per class.")
                    for cls in CLASSES:
                        cls_files = [f for f in all_files if f"/{cls}/" in f][:100]
                        for f in cls_files:
                            zip_ref.extract(f, output_dir)
                else:
                    zip_ref.extractall(output_dir)
            print("Extraction complete.")
        else:
            print("Download failed. Falling back to dummy benchmark data.")
            create_dummy_data(output_dir, sector_size)
    except Exception as e:
        print(f"Error: {e}. Falling back to dummy data.")
        create_dummy_data(output_dir, sector_size)

def create_dummy_data(target_dir, sector_size):
    print(f"Creating dummy benchmark data in {target_dir}")
    for cls in CLASSES:
        cls_dir = os.path.join(target_dir, cls)
        os.makedirs(cls_dir, exist_ok=True)
        for i in range(10): 
            with open(os.path.join(cls_dir, f"sample_{i}.bin"), "wb") as f:
                f.write(os.urandom(int(sector_size)))

# --- Mode: Generate (from GovDocs1) ---
def generate_vff16_from_gov1(source_dir, output_dir, sector_size, max_mb_per_class=50.0):
    print(f"Generating VFF-16 from source: {source_dir}")
    max_bytes = int(max_mb_per_class * 1024 * 1024)
    
    # Simple grouping by extension for GovDocs1 flat structure
    files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
    ext_to_files = {}
    for f in files:
        ext = os.path.splitext(f)[1][1:].lower()
        if ext in CLASSES:
            if ext not in ext_to_files: ext_to_files[ext] = []
            ext_to_files[ext].append(f)

    for class_name, class_files in ext_to_files.items():
        output_class_dir = os.path.join(output_dir, str(sector_size), class_name)
        os.makedirs(output_class_dir, exist_ok=True)
        
        all_fragments = []
        random.shuffle(class_files)
        total_bytes_generated = 0
        
        for filename in tqdm(class_files, desc=f"Processing {class_name}"):
            if total_bytes_generated >= max_bytes: break
            
            fpath = os.path.join(source_dir, filename)
            try:
                with open(fpath, "rb") as f: data = f.read()
            except: continue
            
            # Pad
            padding_size = (sector_size - (len(data) % sector_size)) % sector_size
            if padding_size > 0: data += os.urandom(padding_size)
            
            num_sectors = len(data) // sector_size
            if num_sectors == 0: continue
            
            # Fragmentation
            num_frags = random.randint(1, min(10, num_sectors))
            splits = sorted(random.sample(range(1, num_sectors), num_frags - 1)) if num_frags > 1 else []
            splits = [0] + splits + [num_sectors]
            
            for i in range(num_frags):
                frag_data = data[splits[i]*sector_size : splits[i+1]*sector_size]
                all_fragments.append(frag_data)
            
            total_bytes_generated += len(data)

        # Shuffle and Save
        random.shuffle(all_fragments)
        sample_idx = 0
        for frag in all_fragments:
            for i in range(len(frag) // sector_size):
                sector = frag[i*sector_size : (i+1)*sector_size]
                with open(os.path.join(output_class_dir, f"sample_{sample_idx:06d}.bin"), "wb") as f:
                    f.write(sector)
                sample_idx += 1
        print(f"Generated {sample_idx} sectors for {class_name}")

# --- Mode: Custom ---
def handle_custom(input_path, output_root, sector_size, target_class="unlabeled"):
    output_dir = os.path.join(output_root, str(sector_size), target_class)
    os.makedirs(output_dir, exist_ok=True)
    metadata_csv = os.path.join(output_root, "metadata.csv")
    
    files_to_process = []
    if os.path.isfile(input_path): files_to_process.append(input_path)
    elif os.path.isdir(input_path):
        for fname in os.listdir(input_path):
            fpath = os.path.join(input_path, fname)
            if os.path.isfile(fpath): files_to_process.append(fpath)

    all_mappings = []
    for fpath in files_to_process:
        file_name = os.path.basename(fpath)
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
                
                all_mappings.append({"chunk_name": chunk_name, "parent_file": file_name, "sector_index": chunk_idx, "class": target_class})
                chunk_idx += 1
        print(f"Processed {file_name} into {chunk_idx} chunks in folder '{target_class}'")

    if all_mappings:
        file_exists = os.path.isfile(metadata_csv)
        with open(metadata_csv, "a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["chunk_name", "parent_file", "sector_index", "class"])
            if not file_exists: writer.writeheader()
            writer.writerows(all_mappings)

def main():
    parser = argparse.ArgumentParser(description="Unified Data Preparation Tool.")
    subparsers = parser.add_subparsers(dest="mode", help="Execution mode")

    # Benchmark
    benchmark_parser = subparsers.add_parser("benchmark", help="Download/prepare RFF benchmark")
    benchmark_parser.add_argument("--sector-size", type=int, choices=[512, 4096], default=512)
    benchmark_parser.add_argument("--max-gb", type=float)

    # Generate (GovDocs1)
    generate_parser = subparsers.add_parser("generate", help="Generate VFF-16 from GovDocs1")
    generate_parser.add_argument("--source-dir", required=True)
    generate_parser.add_argument("--sector-size", type=int, choices=[512, 4096], default=512)
    generate_parser.add_argument("--max-mb-per-class", type=float, default=50.0)

    # Custom
    custom_parser = subparsers.add_parser("custom", help="Chunk custom files")
    custom_parser.add_argument("input")
    custom_parser.add_argument("--class-name", default="unlabeled", help="Class folder name (for training compatibility)")
    custom_parser.add_argument("--sector-size", type=int, choices=[512, 4096], default=512)

    args = parser.parse_args()
    setup_base_directories()
    save_classes()

    if args.mode == "benchmark":
        download_benchmark(args.sector_size, args.max_gb)
    elif args.mode == "generate":
        generate_vff16_from_gov1(args.source_dir, "./data/generated", args.sector_size, args.max_mb_per_class)
    elif args.mode == "custom":
        handle_custom(args.input, "./data/custom", args.sector_size, args.class_name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
