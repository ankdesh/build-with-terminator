import os
import argparse

def chunk_file(file_path, output_dir, sector_size=512):
    file_name = os.path.basename(file_path)
    os.makedirs(output_dir, exist_ok=True)
    
    with open(file_path, "rb") as f:
        chunk_idx = 0
        while True:
            chunk = f.read(sector_size)
            if not chunk:
                break
            
            # Apply zero-padding if the final chunk is non-aligned
            if len(chunk) < sector_size:
                padding = b'\x00' * (sector_size - len(chunk))
                chunk += padding
                print(f"Padded final chunk {chunk_idx} of {file_name} with {len(padding)} bytes.")
            
            chunk_name = f"{file_name}_chunk_{chunk_idx:06d}.bin"
            with open(os.path.join(output_dir, chunk_name), "wb") as cf:
                cf.write(chunk)
            
            chunk_idx += 1
            
    print(f"Divided {file_name} into {chunk_idx} chunks.")

def main():
    parser = argparse.ArgumentParser(description="Chunk arbitrary files into sector-sized blocks for forensic analysis.")
    parser.add_argument("input", help="Path to file or directory of files to chunk.")
    parser.add_argument("--output-dir", default="./output/chunks", help="Directory to save chunks.")
    parser.add_argument("--sector-size", type=int, default=512, help="Sector size (512 or 4096).")
    args = parser.parse_args()

    if os.path.isfile(args.input):
        chunk_file(args.input, args.output_dir, args.sector_size)
    elif os.path.isdir(args.input):
        for fname in os.listdir(args.input):
            fpath = os.path.join(args.input, fname)
            if os.path.isfile(fpath):
                chunk_file(fpath, args.output_dir, args.sector_size)
    else:
        print(f"Error: {args.input} is not a valid file or directory.")

if __name__ == "__main__":
    main()
