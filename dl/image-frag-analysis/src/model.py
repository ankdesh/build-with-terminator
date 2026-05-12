import torch
import torch.nn as nn
import torch.nn.functional as F

class CNN_4L(nn.Module):
    def __init__(self, embed_dim=128, hidden_dim=128, seq_len=512, num_classes=16, num_layers=4):
        super(CNN_4L, self).__init__()
        self.seq_len = seq_len
        self.embed_dim = embed_dim
        
        # 1. Input Layer: Embedding Projection Space & Position Embeddings [cite: 222, 673]
        self.byte_embedding = nn.Embedding(256, embed_dim)
        self.pos_embedding = nn.Embedding(seq_len, embed_dim)
        
        # Note: The 3-layer downsampling block was removed. 
        # The PDF specifies this is for JSANet's self-attention, not the CNN-4L baseline [cite: 228-230, 536].
        
        # 2. Core CNN-4L Feature Extractor 
        # Sequentially stacks four layers of Conv1d (kernel=4, stride=2), BN, and ReLU
        layers = []
        in_channels = embed_dim
        for i in range(num_layers):
            layers.append(nn.Conv1d(in_channels, hidden_dim, kernel_size=4, stride=2, padding=1))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            in_channels = hidden_dim # Ensure subsequent layers use hidden_dim
            
        self.feature_extractor = nn.Sequential(*layers)
        
        # 3. Global Aggregation and Classification Head 
        self.gap = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        # x shape: (Batch, Seq_Len)
        batch_size, seq_len = x.shape
        
        # Byte Embeddings
        x_embed = self.byte_embedding(x) # (Batch, Seq_Len, Embed_Dim)
        
        # Position Embeddings
        pos = torch.arange(0, seq_len, device=x.device).unsqueeze(0).repeat(batch_size, 1)
        x_pos = self.pos_embedding(pos)  # (Batch, Seq_Len, Embed_Dim)
        
        # Inject positional information immediately after byte embedding [cite: 231, 673]
        x = x_embed + x_pos
        
        # Transpose for Conv1d: (Batch, Channels, Seq_Len)
        x = x.transpose(1, 2)
        
        # Core feature extraction (4 layers of Conv -> BN -> ReLU) 
        x = self.feature_extractor(x)
        
        # Global Average Pooling flattens the remaining sequence length 
        x = self.gap(x).squeeze(-1)      # (Batch, Hidden_Dim)
        
        # Final fully-connected classification 
        logits = self.classifier(x)
        return logits
