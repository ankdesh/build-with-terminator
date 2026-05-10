## 1. Environment and Data Setup

- [x] 1.1 Install required dependencies: `torch`, `torchvision`, `numpy`, `requests`, `scikit-learn`, `gdown`
- [x] 1.2 Implement `data_preparation.py`: Script to download VFF-16 archives from Google Drive/Internet and extract to `./data/RFF/`
- [x] 1.3 Support configurable dataset volume in `data_preparation.py` (e.g., `--max-gb` or sampling limit)
- [x] 1.4 Ensure `classes.json` is downloaded/created in `./data/FFT/` for index-to-label mapping

## 2. Model Architecture

- [x] 2.1 Implement `CNN_4L` class in `model.py` with `nn.Embedding` for bytes and learnable position embeddings
- [x] 2.2 Add conditional downsampling logic (3 layers of Conv1d) for 4096-byte inputs
- [x] 2.3 Implement the core 4-layer convolutional feature extractor (Conv1d -> BatchNorm -> ReLU)
- [x] 2.4 Implement Global Average Pooling (`AdaptiveAvgPool1d`) and the final Linear classification head

## 3. Training and Validation Pipeline

- [x] 3.1 Implement `VFF16Dataset` in `dataset.py` using `np.uint8` to `torch.LongTensor` conversion
- [x] 3.2 Implement the training script `train.py` with SGD optimizer (Momentum=0.9, Weight Decay=0.1)
- [x] 3.3 Add Linear Warmup scheduler (500 steps) and Cosine Annealing (96 epochs)
- [x] 3.4 Implement validation logic to track peak accuracy and save `best_cnn_model.pth`

## 4. Forensic Inference Tools

- [x] 4.1 Implement `chunk_custom_files.py`: Divide arbitrary files into 512/4k blocks with mandatory zero-padding for final chunks
- [x] 4.2 Implement `predict_custom.py`: Load pre-trained model and process custom chunks in evaluation mode
- [x] 4.3 Implement Sector-Level Reporting: Output logs/CSV containing fragment index, predicted class, and softmax probability for every individual sector

## 5. Verification

- [x] 5.1 Run `data_preparation.py` to verify download and directory structure
- [x] 5.2 Execute a short training run (1-2 epochs) to verify the pipeline and serialization
- [x] 5.3 Validate the inference tool on a known file and verify that every sector is reported independently
