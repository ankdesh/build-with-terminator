## ADDED Requirements

### Requirement: Parameterized CNN-4L Architecture
The system SHALL implement a PyTorch `nn.Module` that accepts parameters for embedding dimension, hidden dimension, sequence length, and number of layers.

#### Scenario: Initialization with 512-byte sequence
- **WHEN** the model is initialized with `seq_len=512`
- **THEN** it bypasses the 4k-specific downsampling blocks and accepts input tensors of shape (Batch, 512)

#### Scenario: Initialization with 4k sequence
- **WHEN** the model is initialized with `seq_len=4096`
- **THEN** it instantiates three downsampling layers to compress the input to 512 before the core feature extractor

### Requirement: Learnable Position Embeddings
The system SHALL incorporate a learnable `nn.Embedding(seq_len, embed_dim)` which is element-wise added to the byte embeddings.

#### Scenario: Position embedding application
- **WHEN** a batch is passed through the embedding layer
- **THEN** position-specific vectors are added to the byte-value vectors to preserve spatial context

### Requirement: Global Average Pooling (GAP)
The system SHALL utilize Global Average Pooling to reduce the final convolutional feature maps to a fixed-length signature vector.

#### Scenario: GAP output shape
- **WHEN** the final convolutional block outputs a tensor of shape (Batch, 128, 32)
- **THEN** the GAP layer outputs a tensor of shape (Batch, 128)
