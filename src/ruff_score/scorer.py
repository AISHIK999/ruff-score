"""Pylint-style quality scores computed from Ruff output.

Score formula (same shape as Pylint's)::

    score = 10 - (sum of issue weights / statements) * 10

Every issue gets a (category, weight) pair from ``RULES`` using longest-prefix
matching, so exact codes (``F401``) override their family (``F``). Errors
default to weight 5, which reproduces Pylint's "errors count x5" rule without a
second multiplier. The score is clamped to the range 0-10.

Ruff prefixes are not single letters (``PLE``, ``ASYNC``, ``C90``, ``T20``...),
which is why lookups try progressively shorter slices of the rule code.
"""

from __future__ import annotations

import ast
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

CATEGORIES = ("error", "warning", "convention", "refactor")

# prefix or exact code -> (category, weight)
RULES: dict[str, tuple[str, int]] = {
    # --- Exact-code overrides (more specific than their family) ---
    "E402": ("convention", 1),  # import not at top of file
    "E501": ("convention", 1),  # line too long
    "E741": ("convention", 1),  # ambiguous variable name
    "E711": ("warning", 2),  # comparison to None
    "E712": ("warning", 2),  # comparison to True/False
    "E722": ("warning", 3),  # bare except
    "F401": ("warning", 2),  # unused import
    "F841": ("warning", 2),  # unused variable
    # --- Errors ---
    "E": ("error", 5),
    "F": ("error", 5),
    "PLE": ("error", 5),
    "AIR": ("error", 3),
    # --- Security ---
    "S": ("warning", 4),
    # --- Warnings ---
    "B": ("warning", 2),
    "BLE": ("warning", 2),
    "ASYNC": ("warning", 3),
    "DTZ": ("warning", 2),
    "G": ("warning", 1),
    "LOG": ("warning", 1),
    "PERF": ("warning", 2),
    "PLW": ("warning", 2),
    "TRY": ("warning", 2),
    "RET": ("warning", 1),
    "RSE": ("warning", 1),
    "SLF": ("warning", 1),
    "ARG": ("warning", 1),
    "T20": ("warning", 1),
    "T10": ("warning", 2),
    "ISC": ("warning", 1),
    "FBT": ("warning", 1),
    "DJ": ("warning", 2),
    "NPY": ("warning", 1),
    "PD": ("warning", 1),
    "C90": ("warning", 2),
    "FAST": ("warning", 1),
    # --- Conventions ---
    "W": ("convention", 1),
    "N": ("convention", 1),
    "D": ("convention", 1),
    "DOC": ("convention", 1),
    "COM": ("convention", 1),
    "Q": ("convention", 1),
    "PT": ("convention", 1),
    "PYI": ("convention", 1),
    "ANN": ("convention", 1),
    "FA": ("convention", 1),
    "ICN": ("convention", 1),
    "TID": ("convention", 1),
    "TC": ("convention", 1),
    "TCH": ("convention", 1),
    "I": ("convention", 1),
    "CPY": ("convention", 1),
    "INP": ("convention", 1),
    "EXE": ("convention", 1),
    "YTT": ("convention", 1),
    "INT": ("convention", 1),
    "PLC": ("convention", 1),
    "PGH": ("convention", 1),
    "TD": ("convention", 1),
    "FIX": ("convention", 1),
    "EM": ("convention", 1),
    "A": ("convention", 1),
    "SLOT": ("convention", 1),
    # --- Refactor ---
    "UP": ("refactor", 1),
    "SIM": ("refactor", 1),
    "PLR": ("refactor", 1),
    "PTH": ("refactor", 1),
    "ERA": ("refactor", 1),
    "C4": ("refactor", 1),
    "PIE": ("refactor", 1),
    "FLY": ("refactor", 1),
    "FURB": ("refactor", 1),
    "RUF": ("refactor", 1),
}

# Ruff reports syntax errors with "code": null. Code that doesn't parse is the
# most severe problem there is.
SYNTAX_ERROR: tuple[str, int] = ("error", 5)
DEFAULT_RULE: tuple[str, int] = ("refactor", 1)

# (minimum score, label), checked in order.
RATINGS: tuple[tuple[float, str], ...] = (
    (9.0, "Excellent code quality!"),
    (7.0, "Good code quality"),
    (5.0, "Needs improvement"),
    (0.0, "Poor code quality - significant issues found"),
)


class RuffError(RuntimeError):
    """Ruff could not be run, crashed, or produced unusable output."""


@dataclass(frozen=True)
class ScoreResult:
    """The outcome of scoring a file or directory."""

    target: str
    score: float
    statements: int
    files_analyzed: int
    counts: dict[str, int]
    total_issues: int
    issues: list[dict]


# --------------------------------------------------------------------------- #
# Ruff integration
# --------------------------------------------------------------------------- #
def _run_ruff(args: list[str], config_file: str | Path | None) -> str:
    # Use the interpreter we're running under so the ruff installed as our
    # dependency is found even when the environment isn't activated.
    cmd = [sys.executable, "-m", "ruff", "check", *args]
    if config_file:
        cmd += ["--config", str(config_file)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    except OSError as e:
        msg = f"could not launch ruff: {e}"
        raise RuffError(msg) from e
    # Ruff exit codes: 0 = clean, 1 = violations found, 2 = ruff itself failed.
    # An exit code of 1 with no output is not "violations found": it means the
    # command failed (e.g. `python -m ruff` when ruff isn't installed).
    failed = result.returncode not in (0, 1) or (result.returncode == 1 and not result.stdout.strip())
    if failed:
        msg = f"ruff failed ({result.returncode}): {result.stderr.strip()}"
        raise RuffError(msg)
    return result.stdout


def run_ruff(path: str | Path, config_file: str | Path | None = None) -> list[dict]:
    """Run ``ruff check`` on *path* and return the parsed JSON issues."""
    stdout = _run_ruff(["--output-format=json", str(path)], config_file)
    try:
        return json.loads(stdout or "[]")
    except json.JSONDecodeError as e:
        msg = f"could not parse ruff JSON output: {e}"
        raise RuffError(msg) from e


def list_checked_files(directory: str | Path, config_file: str | Path | None = None) -> list[Path]:
    """Return the Python files Ruff would check, honouring its exclude/.gitignore settings."""
    stdout = _run_ruff(["--show-files", str(directory)], config_file)
    return [Path(line) for line in stdout.splitlines() if line.endswith(".py")]


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def count_statements(file_path: str | Path) -> int:
    """Count ``ast.stmt`` nodes in a Python file (0 if it can't be parsed)."""
    try:
        # Bytes let ast honour PEP 263 encoding declarations and BOMs.
        tree = ast.parse(Path(file_path).read_bytes())
    except (OSError, SyntaxError, ValueError) as e:
        logger.warning("Could not parse %s: %s", file_path, e)
        return 0
    return sum(isinstance(node, ast.stmt) for node in ast.walk(tree))


def classify(code: str | None) -> tuple[str, int]:
    """Return ``(category, weight)`` for a Ruff rule code via longest-prefix match."""
    if not code:
        return SYNTAX_ERROR
    for end in range(len(code), 0, -1):
        hit = RULES.get(code[:end])
        if hit is not None:
            return hit
    return DEFAULT_RULE


def calculate_score(issues: list[dict], total_statements: int) -> tuple[float, dict[str, int]]:
    """Return ``(score, per-category issue counts)``."""
    counts = dict.fromkeys(CATEGORIES, 0)
    weighted = 0
    for issue in issues:
        category, weight = classify(issue.get("code"))
        counts[category] += 1
        weighted += weight

    if total_statements == 0:
        # Nothing to measure against: perfect only if Ruff found nothing either.
        return (10.0 if not issues else 0.0), counts

    score = 10.0 - (weighted / total_statements) * 10
    return max(0.0, min(10.0, score)), counts


def score_path(path: str | Path, config_file: str | Path | None = None) -> ScoreResult:
    """Score a single file or every file Ruff would check in a directory."""
    target = Path(path)
    if not target.exists():
        msg = f"No such file or directory: {target}"
        raise FileNotFoundError(msg)

    issues = run_ruff(target, config_file)
    files = [target] if target.is_file() else list_checked_files(target, config_file)
    statements = sum(count_statements(f) for f in files)
    score, counts = calculate_score(issues, statements)

    return ScoreResult(
        target=str(target),
        score=score,
        statements=statements,
        files_analyzed=len(files),
        counts=counts,
        total_issues=len(issues),
        issues=issues,
    )


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def rating(score: float) -> str:
    """Return the human-readable quality label for a score."""
    return next(label for minimum, label in RATINGS if score >= minimum)


def format_report(result: ScoreResult) -> str:
    """Render a ``ScoreResult`` as a printable text report."""
    lines = [
        "=" * 50,
        "RUFF QUALITY SCORE REPORT",
        "=" * 50,
        f"Target: {result.target}",
        f"Score: {result.score:.2f}/10.00",
        f"Statements analyzed: {result.statements}",
        f"Files analyzed: {result.files_analyzed}",
        f"Total issues: {result.total_issues}",
        "",
        "Issues by category:",
        *(f"  {name.title()}: {count}" for name, count in result.counts.items()),
        "",
        rating(result.score),
    ]
    return "\n".join(lines)