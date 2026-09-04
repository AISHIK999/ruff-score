"""Command-line interface for ruff-score."""

import sys
from pathlib import Path

from .scorer import RuffScorer


def main() -> None:
    """Main entry point for the CLI."""
    if len(sys.argv) < 2:
        print("Usage: ruff-score <file_or_directory> [config_file]")
        print("       python -m ruff_score <file_or_directory> [config_file]")
        sys.exit(1)

    target = sys.argv[1]
    config_file = sys.argv[2] if len(sys.argv) > 2 else None

    scorer = RuffScorer()

    if Path(target).is_file():
        result = scorer.score_file(Path(target), config_file)
    else:
        result = scorer.score_directory(Path(target), config_file)

    scorer.print_report(result)


if __name__ == "__main__":
    main()
