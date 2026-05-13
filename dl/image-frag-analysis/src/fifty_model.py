import torch
import torch.nn as nn
import torch.nn.functional as F

class FiFTy(nn.Module):
    """
    FiFTy model architecture based on arxiv:1908.06148
    Scenario #1: 512-byte blocks
    Optimal Architecture: E (64) - C1D (128, 27) - MP (4) - AP - D (0.1) - F (256) - F (num_classes)
    """
    def __init__(self, num_classes=16, embed_dim=64):
        super(FiFTy, self).__init__()
        
        # 1. Embedding Layer: Maps bytes (0-255) to a continuous space
        self.embedding = nn.Embedding(256, embed_dim)
        
        # 2. Convolutional Block
        # Using 128 output channels, kernel size of 128, stride of 27.
        self.conv = nn.Conv1d(in_channels=embed_dim, out_channels=128, kernel_size=128, stride=27)
        self.relu = nn.ReLU()
        
        # 3. Max Pooling
        # Kernel size 4 (stride defaults to kernel_size in PyTorch)
        self.max_pool = nn.MaxPool1d(kernel_size=4)
        
        # 4. Average Pooling (Global)
        self.global_avg_pool = nn.AdaptiveAvgPool1d(1)
        
        # 5. Dropout
        self.dropout = nn.Dropout(p=0.1)
        
        # 6. Dense layers
        self.fc1 = nn.Linear(128, 256)
        self.fc_relu = nn.ReLU()
        self.fc2 = nn.Linear(256, num_classes)

    def forward(self, x):
        # x shape: (Batch, Seq_Len) -> raw bytes (0-255)
        
        # Embedding: (Batch, Seq_Len, Embed_Dim)
        x = self.embedding(x)
        
        # Transpose to (Batch, Channels, Seq_Len) for Conv1d
        x = x.transpose(1, 2)
        
        # Convolution + ReLU
        x = self.conv(x)
        x = self.relu(x)
        
        # Max Pooling
        x = self.max_pool(x)
        
        # Global Average Pooling -> flattens to (Batch, 128, 1)
        x = self.global_avg_pool(x)
        x = x.squeeze(-1) # (Batch, 128)
        
        # Dropout
        x = self.dropout(x)
        
        # Dense Layers
        x = self.fc1(x)
        x = self.fc_relu(x)
        logits = self.fc2(x)
        
        return logits
