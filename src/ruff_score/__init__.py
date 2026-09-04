"""Ruff Score - A Pylint-style scoring system for Ruff linter output.

This library provides a scoring system similar to Pylint's quality score
but for Ruff linter output. It analyzes code quality based on Ruff rules
and provides a numerical score from 0 to 10.
"""

__version__ = "0.1.0"
__author__ = "Aishik Mukherjee"
__email__ = "aishikm2002@gmail.com"

from .scorer import RuffScorer

__all__ = ["RuffScorer"]
