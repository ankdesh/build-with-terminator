import os
import torch
from torch.utils.data import Dataset
import numpy as np

class VFF16Dataset(Dataset):
    def __init__(self, data_root, sector_size=512, class_to_idx=None):
        self.data_root = data_root
        self.sector_size = sector_size
        self.class_to_idx = class_to_idx
        self.samples = []
        
        # Crawl the directory structure: data_root/class_name/*.bin
        for class_name in os.listdir(data_root):
            class_dir = os.path.join(data_root, class_name)
            if not os.path.isdir(class_dir):
                continue
                
            class_idx = self.class_to_idx.get(class_name) if self.class_to_idx else None
            if class_idx is None:
                continue
                
            for fname in os.listdir(class_dir):
                if fname.endswith(".bin") or fname.endswith(".sample"): # Generic binary extensions
                    fpath = os.path.join(class_dir, fname)
                    self.samples.append((fpath, class_idx))
                    
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        fpath, label = self.samples[idx]
        
        # Read exactly sector_size bytes
        with open(fpath, "rb") as f:
            byte_data = f.read(self.sector_size)
            
        # Convert to numpy uint8
        data = np.frombuffer(byte_data, dtype=np.uint8)
        
        # If the file was shorter than expected, pad with zeros
        if len(data) < self.sector_size:
            data = np.pad(data, (0, self.sector_size - len(data)), 'constant')
            
        # Cast to torch.LongTensor for embedding layer
        return torch.from_numpy(data.astype(np.int64)), torch.tensor(label, dtype=torch.long)
