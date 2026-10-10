"""Command-line interface: ``ruff-score PATH [--config FILE] [--fail-under N] [--json]``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict

from .scorer import RuffError, format_report, score_path


def main(argv: list[str] | None = None) -> int:
    """Run the ``ruff-score`` command and return its exit code."""
    parser = argparse.ArgumentParser(prog="ruff-score", description="Pylint-style quality score from Ruff output.")
    parser.add_argument("target", help="Python file or directory to score")
    parser.add_argument("--config", help="Path to a Ruff config file")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        help="Exit with status 1 if the score is below this value (for CI)",
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    try:
        result = score_path(args.target, args.config)
    except (RuffError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(result), indent=2) if args.json else format_report(result))
    return 1 if result.score < args.fail_under else 0


if __name__ == "__main__":
    raise SystemExit(main())