import os
import pandas as pd
import argparse

def verify_dataset(dataset_path, sector_size):
    print(f"Verifying dataset at {dataset_path} with sector size {sector_size}...")
    
    classes = [d for d in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, d))]
    
    for class_name in classes:
        class_dir = os.path.join(dataset_path, class_name)
        meta_path = os.path.join(class_dir, "metadata.csv")
        
        if not os.path.exists(meta_path):
            print(f"Error: Metadata missing for class {class_name}")
            continue
            
        df = pd.read_csv(meta_path)
        
        # 1. Check if all samples in metadata exist on disk
        missing_samples = []
        for sample_name in df['sample_name']:
            if not os.path.exists(os.path.join(class_dir, sample_name)):
                missing_samples.append(sample_name)
        
        if missing_samples:
            print(f"Error: {len(missing_samples)} samples in metadata are missing from disk in {class_name}")
        else:
            print(f"OK: All {len(df)} samples in metadata exist on disk for {class_name}")
            
        # 2. Check sector sizes
        wrong_size = 0
        for sample_name in df['sample_name']:
            size = os.path.getsize(os.path.join(class_dir, sample_name))
            if size != sector_size:
                wrong_size += 1
        
        if wrong_size:
            print(f"Error: {wrong_size} samples have incorrect size in {class_name}")
        else:
            print(f"OK: All samples have correct sector size ({sector_size}) in {class_name}")
            
        # 3. Check fragment continuity (optional but good)
        # Sort by fragment_id and offset_in_original to check if sectors are sequential
        # Actually, they are shuffled, so we just check if offsets are multiples of sector_size
        if not (df['offset_in_original'] % sector_size == 0).all():
            print(f"Error: Some offsets are not sector-aligned in {class_name}")
        else:
            print(f"OK: All offsets are sector-aligned in {class_name}")

def main():
    parser = argparse.ArgumentParser(description="Verify generated VFF-16 dataset.")
    parser.add_argument("--dataset-path", type=str, required=True, help="Path to the generated dataset root (e.g., ./data/RFF/512)")
    parser.add_argument("--sector-size", type=int, required=True, help="Sector size (512 or 4096)")
    args = parser.parse_args()
    
    verify_dataset(args.dataset_path, args.sector_size)

if __name__ == "__main__":
    main()
