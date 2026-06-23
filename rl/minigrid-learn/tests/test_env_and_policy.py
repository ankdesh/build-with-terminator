import numpy as np
from stable_baselines3 import PPO

from minigrid_learn.envs import make_minigrid_env
from minigrid_learn.policy import MiniGridCNN
from minigrid_learn.training import make_vec_env


def test_image_observation_and_deterministic_seed() -> None:
    first = make_minigrid_env("MiniGrid-Empty-8x8-v0", seed=7)
    second = make_minigrid_env("MiniGrid-Empty-8x8-v0", seed=7)
    first_observation, _ = first.reset(seed=7)
    second_observation, _ = second.reset(seed=7)
    assert first_observation.shape == (7, 7, 3)
    assert first_observation.dtype == np.uint8
    np.testing.assert_array_equal(first_observation, second_observation)
    first.close()
    second.close()


def test_cnn_policy_accepts_transposed_minigrid_image() -> None:
    env = make_vec_env("MiniGrid-Empty-8x8-v0", seed=0)
    observation = env.reset()
    assert observation.shape == (1, 3, 7, 7)
    model = PPO(
        "CnnPolicy",
        env,
        n_steps=8,
        batch_size=4,
        policy_kwargs={
            "features_extractor_class": MiniGridCNN,
            "features_extractor_kwargs": {"features_dim": 32},
        },
    )
    action, _ = model.predict(observation, deterministic=True)
    assert action.shape == (1,)
    env.close()
