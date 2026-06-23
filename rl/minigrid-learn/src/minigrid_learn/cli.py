from __future__ import annotations

import argparse
import json
from pathlib import Path

from minigrid_learn.config import load_config
from minigrid_learn.evaluation import evaluate_saved_model
from minigrid_learn.reporting import generate_report
from minigrid_learn.training import train_all, train_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MiniGrid Phase 1 experiment pipeline")
    parser.add_argument("--config", default="configs/phase1.toml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train", help="Train one or all configured runs")
    train.add_argument("--all", action="store_true", help="Run every environment and seed")
    train.add_argument("--env", help="Environment slug or Gymnasium ID")
    train.add_argument("--seed", type=int, default=0)
    train.add_argument("--timesteps", type=int)

    smoke = subparsers.add_parser("smoke", help="Run a short end-to-end experiment")
    smoke.add_argument("--all", action="store_true")
    smoke.add_argument("--env", default="empty-8x8")
    smoke.add_argument("--seed", type=int, default=0)
    smoke.add_argument("--timesteps", type=int, default=512)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a saved PPO model")
    evaluate.add_argument("--env", required=True)
    evaluate.add_argument("--model", type=Path, required=True)
    evaluate.add_argument("--seed", type=int, default=10_000)
    evaluate.add_argument("--episodes", type=int, default=20)

    subparsers.add_parser("report", help="Regenerate report from saved metrics")
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = load_config(args.config)

    if args.command == "train":
        if args.all:
            result = train_all(config, total_timesteps=args.timesteps)
        else:
            if not args.env:
                raise SystemExit("train requires --env or --all")
            result = train_run(
                config,
                config.environment(args.env),
                args.seed,
                total_timesteps=args.timesteps,
            )
    elif args.command == "smoke":
        if args.all:
            result = train_all(config, total_timesteps=args.timesteps, smoke=True)
        else:
            result = train_run(
                config,
                config.environment(args.env),
                args.seed,
                total_timesteps=args.timesteps,
                smoke=True,
            )
    elif args.command == "evaluate":
        result = evaluate_saved_model(
            args.model,
            config.environment(args.env).id,
            seed=args.seed,
            n_episodes=args.episodes,
        )
    else:
        result = {"report": str(generate_report(config))}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
