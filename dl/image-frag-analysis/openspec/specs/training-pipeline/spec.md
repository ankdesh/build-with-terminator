# Capability: training-pipeline

## Purpose
TBD - This capability handles the training process for the file fragment classifier.

## Requirements

### Requirement: SGD with Linear Warmup
The training system SHALL utilize Stochastic Gradient Descent (SGD) with a linear learning rate warmup for the first 500 steps.

#### Scenario: Warmup phase
- **WHEN** training starts (step < 500)
- **THEN** the learning rate increases linearly from 0 to 0.2

### Requirement: Cosine Annealing Decay
The system SHALL apply a Cosine Annealing scheduler to decay the learning rate to zero over 96 epochs.

#### Scenario: Decay phase
- **WHEN** step >= 500
- **THEN** the learning rate follows a cosine curve reaching 0 at epoch 96

### Requirement: Best Model Serialization
The system SHALL monitor validation accuracy and save the model state dictionary when a new peak accuracy is reached.

#### Scenario: Peak accuracy reached
- **WHEN** validation accuracy is higher than any previous epoch
- **THEN** the system saves `best_cnn_model.pth` to the project root
