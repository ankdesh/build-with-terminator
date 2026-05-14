import os
import torch
from torch.utils.data import Dataset
import numpy as np

class NPZDataset(Dataset):
    def __init__(self, npz_path):
        """
        Loads an NPZ file containing 'x' (features) and 'y' (labels) arrays.
        Loads the data entirely into memory since it usually fits in RAM, 
        optimizing for training speed.
        """
        if not os.path.exists(npz_path):
            raise FileNotFoundError(f"NPZ file not found: {npz_path}")
            
        print(f"Loading data from {npz_path} into memory...")
        data = np.load(npz_path)
        
        if 'x' not in data or 'y' not in data:
            raise ValueError(f"NPZ file {npz_path} must contain 'x' and 'y' keys. Found: {list(data.keys())}")
            
        self.x = data['x']
        self.y = data['y']
        
        # Determine number of classes dynamically
        self.unique_classes = np.unique(self.y)
        self.num_classes = len(self.unique_classes)
        print(f"Loaded {len(self.x)} samples. Number of classes: {self.num_classes}")

    def __len__(self):
        return len(self.x)
        
    def __getitem__(self, idx):
        # We assume x is bytes data (uint8, etc) which we need to cast to int64 for the embedding layer
        x_val = self.x[idx]
        y_val = self.y[idx]
        
        # The embedding layers in model.py and fifty_model.py expect torch.long (int64) for inputs
        return torch.from_numpy(x_val.astype(np.int64)), torch.tensor(y_val, dtype=torch.long)
