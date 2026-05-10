import os
import json
import torch
import torch.nn.functional as F
import numpy as np
import argparse
from model import CNN_4L
import csv

def predict():
    parser = argparse.ArgumentParser(description="Predict file fragment types for custom chunks.")
    parser.add_argument("--chunks-dir", default="./output/chunks", help="Directory containing binary chunks.")
    parser.add_argument("--model-path", default="models/best_cnn_model.pth", help="Path to trained model weights.")
    parser.add_argument("--sector-size", type=int, default=512, help="Sector size used for training.")
    parser.add_argument("--num-layers", type=int, default=4, help="Number of convolutional layers.")
    parser.add_argument("--output-csv", default="output/results/inference_results.csv", help="Path to save sector-level results.")
    args = parser.parse_args()
...
    # 4. Sector-Level Reporting (CSV)
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    keys = results[0].keys() if results else []

        class_map = json.load(f)
    idx_to_class = {int(k): v for k, v in class_map.items()}
    num_classes = len(idx_to_class)

    # 2. Load Model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CNN_4L(seq_len=args.sector_size, num_classes=num_classes, num_layers=args.num_layers).to(device)
    
    if os.path.exists(args.model_path):
        model.load_state_dict(torch.load(args.model_path, map_location=device))
        print(f"Loaded model weights from {args.model_path}")
    else:
        print(f"Warning: Model weights not found at {args.model_path}. Using random initialization.")
    
    model.eval()

    # 3. Process Chunks
    results = []
    chunk_files = [f for f in os.listdir(args.chunks_dir) if f.endswith(".bin")]
    chunk_files.sort()
    
    print(f"Processing {len(chunk_files)} chunks from {args.chunks_dir}...")
    
    with torch.no_grad():
        for fname in chunk_files:
            fpath = os.path.join(args.chunks_dir, fname)
            
            with open(fpath, "rb") as f:
                byte_data = f.read(args.sector_size)
            
            data = np.frombuffer(byte_data, dtype=np.uint8)
            if len(data) < args.sector_size:
                data = np.pad(data, (0, args.sector_size - len(data)), 'constant')
            
            input_tensor = torch.from_numpy(data.astype(np.int64)).unsqueeze(0).to(device)
            
            logits = model(input_tensor)
            probs = F.softmax(logits, dim=1)
            conf, pred_idx = torch.max(probs, 1)
            
            results.append({
                "fragment_name": fname,
                "predicted_class": idx_to_class[pred_idx.item()],
                "confidence": f"{conf.item():.4f}"
            })

    # 4. Sector-Level Reporting (CSV)
    keys = results[0].keys() if results else []
    with open(args.output_csv, "w", newline='') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
    
    print(f"Sector-level classification complete. Results saved to {args.output_csv}")

if __name__ == "__main__":
    predict()
