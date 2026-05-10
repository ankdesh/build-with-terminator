import os
import argparse
import numpy as np
import pandas as pd
from tqdm import tqdm
import random

def parse_args():
    parser = argparse.ArgumentParser(description="Generate VFF-16 dataset from raw files.")
    parser.add_argument("--source-dir", type=str, required=True, help="Path to GovDocs1 or similar source directory.")
    parser.add_argument("--output-dir", type=str, default="./data/RFF", help="Path to save generated dataset.")
    parser.add_argument("--sector-size", type=int, choices=[512, 4096], default=512, help="Sector size (512 or 4096).")
    parser.add_argument("--max-mb-per-class", type=float, default=50.0, help="Maximum MB per class.")
    return parser.parse_args()

def main():
    args = parse_args()
    print(f"Generating VFF-16 dataset...")
    
    source_dir = args.source_dir
    output_root = os.path.join(args.output_dir, str(args.sector_size))
    max_bytes = int(args.max_mb_per_class * 1024 * 1024)
    
    # Identify classes
    subdirs = [d for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))]
    
    if subdirs:
        print(f"Detected nested directory structure. Classes: {len(subdirs)}")
        for class_name in subdirs:
            source_class_dir = os.path.join(source_dir, class_name)
            output_class_dir = os.path.join(output_root, class_name)
            generate_class_data(class_name, source_class_dir, output_class_dir, args.sector_size, max_bytes)
    else:
        print(f"Detected flat directory structure. Grouping by extension...")
        files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
        extensions = set(os.path.splitext(f)[1][1:].lower() for f in files if "." in f)
        
        # Create temp mapping for flat files
        import collections
        ext_to_files = collections.defaultdict(list)
        for f in files:
            ext = os.path.splitext(f)[1][1:].lower()
            if ext:
                ext_to_files[ext].append(f)
        
        print(f"Classes found by extension: {list(ext_to_files.keys())}")
        
        for class_name, class_files in ext_to_files.items():
            output_class_dir = os.path.join(output_root, class_name)
            os.makedirs(output_class_dir, exist_ok=True)
            
            # For flat structure, we need to pass the list of files to generate_class_data
            # or refactor it to accept a file list.
            # Let's refactor generate_class_data slightly.
            generate_class_data_from_list(class_name, source_dir, class_files, output_class_dir, args.sector_size, max_bytes)

def generate_class_data_from_list(class_name, source_base_dir, files, output_class_dir, sector_size, max_bytes):
    os.makedirs(output_class_dir, exist_ok=True)
    all_fragments = []
    
    random.shuffle(files)
    
    total_bytes_generated = 0
    pbar = tqdm(total=max_bytes, desc=f"Processing {class_name}", unit="B", unit_scale=True)
    
    for filename in files:
        if total_bytes_generated >= max_bytes:
            break
            
        file_path = os.path.join(source_base_dir, filename)
        file_size = os.path.getsize(file_path)
        
        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
            
        # Pad to sector size
        padding_size = (sector_size - (file_size % sector_size)) % sector_size
        if padding_size > 0:
            data += os.urandom(padding_size)
            
        num_sectors = len(data) // sector_size
        if num_sectors == 0:
            continue
            
        # Fragmentation logic (1 to 10 fragments)
        num_fragments = random.randint(1, min(10, num_sectors))
        
        # Partition sectors into fragments
        if num_fragments > 1:
            split_points = sorted(random.sample(range(1, num_sectors), num_fragments - 1))
        else:
            split_points = []
        split_points = [0] + split_points + [num_sectors]
        
        for i in range(num_fragments):
            start_sector = split_points[i]
            end_sector = split_points[i+1]
            frag_sectors = end_sector - start_sector
            
            fragment_data = data[start_sector * sector_size : end_sector * sector_size]
            
            all_fragments.append({
                "data": fragment_data,
                "metadata": {
                    "original_file": filename,
                    "start_sector": start_sector,
                    "num_sectors": frag_sectors,
                    "padding_start_sector": num_sectors - (padding_size // sector_size) if padding_size > 0 else num_sectors
                }
            })
            
        total_bytes_generated += len(data)
        pbar.update(len(data))
        
    pbar.close()
    
    # Shuffle fragments
    random.shuffle(all_fragments)
    
    # Save sectors and metadata
    metadata_records = []
    sample_idx = 0
    
    for frag in all_fragments:
        frag_data = frag["data"]
        meta = frag["metadata"]
        
        for i in range(meta["num_sectors"]):
            sector_data = frag_data[i * sector_size : (i + 1) * sector_size]
            sample_name = f"sample_{sample_idx:06d}.bin"
            sample_path = os.path.join(output_class_dir, sample_name)
            
            with open(sample_path, "wb") as f:
                f.write(sector_data)
                
            current_sector_in_file = meta["start_sector"] + i
            is_padding = current_sector_in_file >= meta["padding_start_sector"]
            
            metadata_records.append({
                "sample_name": sample_name,
                "original_file": meta["original_file"],
                "offset_in_original": current_sector_in_file * sector_size,
                "fragment_id": f"frag_{meta['original_file']}_{meta['start_sector']}",
                "is_padding": is_padding
            })
            
            sample_idx += 1
            
    if metadata_records:
        df_meta = pd.DataFrame(metadata_records)
        df_meta.to_csv(os.path.join(output_class_dir, "metadata.csv"), index=False)
        print(f"Completed {class_name}: {sample_idx} sectors generated.")
    else:
        print(f"No data generated for {class_name}.")

def generate_class_data(class_name, source_class_dir, output_class_dir, sector_size, max_bytes):
    files = [f for f in os.listdir(source_class_dir) if os.path.isfile(os.path.join(source_class_dir, f))]
    generate_class_data_from_list(class_name, source_class_dir, files, output_class_dir, sector_size, max_bytes)



if __name__ == "__main__":
    main()
