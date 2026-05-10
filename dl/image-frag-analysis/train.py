import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import LambdaLR, CosineAnnealingLR
from model import CNN_4L
from dataset import VFF16Dataset
import argparse

def train():
    parser = argparse.ArgumentParser(description="Train CNN-4L for File Fragment Classification.")
    parser.add_argument("--sector-size", type=int, default=512, help="Sector size (512 or 4096).")
    parser.add_argument("--batch-size", type=int, default=512, help="Batch size.")
    parser.add_argument("--epochs", type=int, default=96, help="Number of epochs.")
    parser.add_argument("--lr", type=float, default=0.2, help="Max learning rate.")
    args = parser.parse_args()

    # 1. Load Classes
    with open("./data/FFT/classes.json", "r") as f:
        class_map = json.load(f)
    # Inverse map: label -> index
    class_to_idx = {v: int(k) for k, v in class_map.items()}
    num_classes = len(class_to_idx)

    # 2. Data Loaders (Assuming data exists at ./data/RFF/{sector_size})
    data_path = f"./data/RFF/{args.sector_size if args.sector_size == 512 else '4k'}"
    dataset = VFF16Dataset(data_path, sector_size=args.sector_size, class_to_idx=class_to_idx)
    
    # Simple split for demonstration: 80% train, 20% val
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_set, val_set = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, num_workers=4)

    # 3. Model, Loss, Optimizer
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CNN_4L(seq_len=args.sector_size, num_classes=num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, weight_decay=0.1)

    # 4. Learning Rate Schedule: Warmup + Cosine Annealing
    warmup_steps = 500
    def lr_lambda(current_step):
        if current_step < warmup_steps:
            return float(current_step) / float(max(1, warmup_steps))
        return 1.0

    warmup_scheduler = LambdaLR(optimizer, lr_lambda)
    cosine_scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)

    # 5. Training Loop
    best_acc = 0.0
    global_step = 0
    
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for data, targets in train_loader:
            data, targets = data.to(device), targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(data)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            if global_step < warmup_steps:
                warmup_scheduler.step()
                
            total_loss += loss.item()
            global_step += 1
            
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
        
        val_acc = 100 * correct / total
        print(f"Epoch {epoch+1}/{args.epochs} | Loss: {total_loss/len(train_loader):.4f} | Val Acc: {val_acc:.2f}%")
        
        # Step cosine scheduler after each epoch
        if global_step >= warmup_steps:
            cosine_scheduler.step()
            
        # Save best model
        if val_acc >= best_acc or epoch == 0:
            best_acc = val_acc
            torch.save(model.state_dict(), "best_cnn_model.pth")
            print(f"--> Saved best model with Accuracy: {val_acc:.2f}%")

if __name__ == "__main__":
    train()
