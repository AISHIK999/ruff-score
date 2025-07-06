"""Allow ruff-score to be run as a module with python -m ruff_score."""

from .cli import main

if __name__ == "__main__":
    main()
