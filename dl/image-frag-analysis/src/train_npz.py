import os
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import LambdaLR, CosineAnnealingLR

from model import CNN_4L
from fifty_model import FiFTy
from dataset_npz import NPZDataset

def train():
    parser = argparse.ArgumentParser(description="Train Model for File Fragment Classification with NPZ datasets.")
    parser.add_argument("--model", type=str, default="fifty", choices=["cnn_4l", "fifty"], help="Model architecture to use.")
    parser.add_argument("--data-dir", type=str, default="data/fft75/4k_2", help="Path to the directory containing train.npz and val.npz.")
    parser.add_argument("--batch-size", type=int, default=512, help="Batch size.")
    parser.add_argument("--epochs", type=int, default=96, help="Number of epochs.")
    parser.add_argument("--lr", type=float, default=0.2, help="Max learning rate.")
    parser.add_argument("--num-layers", type=int, default=4, help="Number of convolutional layers (for CNN_4L).")
    parser.add_argument("--log-csv", type=str, help="Path to CSV file to log final results.")
    args = parser.parse_args()

    # 1. Data Loaders
    train_npz_path = os.path.join(args.data_dir, "train.npz")
    val_npz_path = os.path.join(args.data_dir, "val.npz")
    
    print("Loading datasets...")
    train_set = NPZDataset(train_npz_path)
    val_set = NPZDataset(val_npz_path)
    
    num_classes = train_set.num_classes
    print(f"Detected {num_classes} classes from the training dataset.")

    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, num_workers=4)

    # 2. Model, Loss, Optimizer
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    if args.model == "fifty":
        # The embedding dim can be left to default (64) as per fifty_model.py
        model = FiFTy(num_classes=num_classes).to(device)
    else:
        # Using CNN_4L default seq_len=4096 based on the data shape? 
        # The NPZ dataset shape is (N, 4096), so we set seq_len=4096
        model = CNN_4L(seq_len=4096, num_classes=num_classes, num_layers=args.num_layers).to(device)
        
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, weight_decay=0.1)

    # 3. Learning Rate Schedule: Warmup + Cosine Annealing
    warmup_steps = 500
    def lr_lambda(current_step):
        if current_step < warmup_steps:
            return float(current_step) / float(max(1, warmup_steps))
        return 1.0

    warmup_scheduler = LambdaLR(optimizer, lr_lambda)
    cosine_scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)

    # 4. Training Loop
    best_acc = 0.0
    global_step = 0
    
    train_acc = 0.0
    val_acc = 0.0
    
    print(f"Starting training for {args.epochs} epochs...")
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for batch_idx, (data, targets) in enumerate(train_loader):
            data, targets = data.to(device), targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(data)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            # Training Accuracy calculation
            _, predicted = torch.max(outputs.data, 1)
            train_total += targets.size(0)
            train_correct += (predicted == targets).sum().item()
            
            if global_step < warmup_steps:
                warmup_scheduler.step()
                
            total_loss += loss.item()
            global_step += 1
            
            if batch_idx % 100 == 0:
                print(f"Epoch {epoch+1} | Batch {batch_idx}/{len(train_loader)} | Loss: {loss.item():.4f}")
            
        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for data, targets in val_loader:
                data, targets = data.to(device), targets.to(device)
                outputs = model(data)
                _, predicted = torch.max(outputs.data, 1)
                total += targets.size(0)
                correct += (predicted == targets).sum().item()
        
        train_acc = 100 * train_correct / train_total
        val_acc = 100 * correct / total
        print(f"Epoch {epoch+1}/{args.epochs} | Loss: {total_loss/len(train_loader):.4f} | Train Acc: {train_acc:.2f}% | Val Acc: {val_acc:.2f}%")
        
        # Step cosine scheduler after each epoch
        if global_step >= warmup_steps:
            cosine_scheduler.step()
            
        # Save best model
        if val_acc >= best_acc or epoch == 0:
            best_acc = val_acc
            os.makedirs("models", exist_ok=True)
            model_save_path = f"models/best_{args.model}_npz.pth"
            torch.save(model.state_dict(), model_save_path)
            print(f"--> Saved best model to {model_save_path} with Accuracy: {val_acc:.2f}%")

    # Final logging to CSV
    if args.log_csv:
        import csv
        file_exists = os.path.isfile(args.log_csv)
        with open(args.log_csv, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["model", "num_classes", "num_layers", "loss", "train_acc", "val_acc"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "model": f"{args.model}_npz",
                "num_classes": num_classes,
                "num_layers": args.num_layers,
                "loss": f"{total_loss/len(train_loader):.4f}",
                "train_acc": f"{train_acc:.2f}",
                "val_acc": f"{val_acc:.2f}"
            })
        print(f"Final results logged to {args.log_csv}")

if __name__ == "__main__":
    train()
