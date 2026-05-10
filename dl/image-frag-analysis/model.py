import torch
import torch.nn as nn
import torch.nn.functional as F

class CNN_4L(nn.Module):
    def __init__(self, embed_dim=128, hidden_dim=128, seq_len=512, num_classes=16, num_layers=4):
        super(CNN_4L, self).__init__()
        self.seq_len = seq_len
        self.embed_dim = embed_dim
        
        # 1. Embedding Projection Space
        self.byte_embedding = nn.Embedding(256, embed_dim)
        self.pos_embedding = nn.Embedding(seq_len, embed_dim)
        
        # 2. Dynamic Downsampling for 4k Sectors
        self.downsample = None
        if seq_len == 4096:
            self.downsample = nn.Sequential(
                nn.Conv1d(embed_dim, embed_dim, kernel_size=4, stride=2, padding=1),
                nn.BatchNorm1d(embed_dim),
                nn.ReLU(),
                nn.Conv1d(embed_dim, embed_dim, kernel_size=4, stride=2, padding=1),
                nn.BatchNorm1d(embed_dim),
                nn.ReLU(),
                nn.Conv1d(embed_dim, embed_dim, kernel_size=4, stride=2, padding=1),
                nn.BatchNorm1d(embed_dim),
                nn.ReLU(),
            )
            # Resulting seq_len will be 512
        
        # 3. Core CNN-4L Feature Extractor
        layers = []
        for i in range(num_layers):
            layers.append(nn.Conv1d(embed_dim if i == 0 else hidden_dim, hidden_dim, kernel_size=4, stride=2, padding=1))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
        self.feature_extractor = nn.Sequential(*layers)
        
        # 4. Global Aggregation and Classification Head
        self.gap = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        # x shape: (Batch, Seq_Len)
        batch_size, seq_len = x.shape
        
        # Byte Embeddings
        x_embed = self.byte_embedding(x) # (Batch, Seq_Len, Embed_Dim)
        
        # Position Embeddings
        pos = torch.arange(0, seq_len, device=x.device).unsqueeze(0).repeat(batch_size, 1)
        x_pos = self.pos_embedding(pos) # (Batch, Seq_Len, Embed_Dim)
        
        x = x_embed + x_pos
        
        # Transpose for Conv1d: (Batch, Channels, Seq_Len)
        x = x.transpose(1, 2)
        
        # Apply conditional downsampling
        if self.downsample is not None:
            x = self.downsample(x)
            
        # Core feature extraction
        x = self.feature_extractor(x)
        
        # Global Average Pooling
        x = self.gap(x).squeeze(-1) # (Batch, Hidden_Dim)
        
        # Final classification
        logits = self.classifier(x)
        return logits
