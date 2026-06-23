from __future__ import annotations

import gymnasium as gym
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn


class MiniGridCNN(BaseFeaturesExtractor):
    """Compact CNN suitable for MiniGrid's 7x7x3 encoded observation."""

    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 128) -> None:
        super().__init__(observation_space, features_dim)
        channels = observation_space.shape[0]
        self.cnn = nn.Sequential(
            nn.Conv2d(channels, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            sample = torch.as_tensor(observation_space.sample()[None]).float()
            flattened = self.cnn(sample).shape[1]
        self.linear = nn.Sequential(nn.Linear(flattened, features_dim), nn.ReLU())

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.linear(self.cnn(observations))
