import torch
from src.fifty_model import FiFTy

model = FiFTy(num_classes=16, embed_dim=64)
# Batch size 2, Sequence length 512, values between 0 and 255
dummy_input = torch.randint(0, 256, (2, 512))
output = model(dummy_input)
print(f"Output shape: {output.shape}")
