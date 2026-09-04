"""Ruff Quality Score Calculator
Implements a Pylint-style scoring system for Ruff output.

Rule categories/prefixes are sourced from https://docs.astral.sh/ruff/rules/
(current as of the "Legend" / table-of-contents on that page). Ruff prefixes
are NOT all single letters (e.g. "PLC", "PLE", "ASYNC", "TRY", "RUF"), so the
prefix must be extracted as the full leading alphabetic run, not just the
first character.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar


@dataclass
class CheckResult:
    """Data model for Ruff check result."""

    files: list[Path] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)


class RuffScorer:
    """Calculate code quality scores based on Ruff output."""

    # Pylint-style category for every Ruff rule prefix, per
    # https://docs.astral.sh/ruff/rules/
    #
    # "error"      -> real bugs / correctness issues (Pylint E-equivalent)
    # "warning"    -> security risks & likely-bug patterns (Pylint W-equivalent,
    #                 bumped up for security)
    # "convention" -> naming/docs/style/import conventions (Pylint C-equivalent)
    # "refactor"   -> modernization / simplification / structure (Pylint R-equivalent)
    RULE_CATEGORIES: ClassVar = {
        # --- Correctness / errors ---
        "E": "error",  # pycodestyle Error
        "F": "error",  # Pyflakes
        "PLE": "error",  # Pylint Error
        "AIR": "error",  # Airflow (misuse leads to runtime/DAG errors)
        # --- Security (flake8-bandit) — treated as high-severity warnings ---
        "S": "warning",
        # --- Likely-bug / risk patterns (Pylint W-equivalent) ---
        "B": "warning",  # flake8-bugbear
        "BLE": "warning",  # flake8-blind-except
        "ASYNC": "warning",  # flake8-async
        "DTZ": "warning",  # flake8-datetimez (naive datetimes)
        "G": "warning",  # flake8-logging-format
        "LOG": "warning",  # flake8-logging
        "PERF": "warning",  # Perflint
        "PLW": "warning",  # Pylint Warning
        "TRY": "warning",  # tryceratops (exception handling anti-patterns)
        "RET": "warning",  # flake8-return
        "RSE": "warning",  # flake8-raise
        "SLF": "warning",  # flake8-self (private member access)
        "ARG": "warning",  # flake8-unused-arguments
        "T20": "warning",  # flake8-print (left-over prints)
        "T10": "warning",  # flake8-debugger (left-over debugger traces)
        "ISC": "warning",  # flake8-implicit-str-concat
        "FBT": "warning",  # flake8-boolean-trap
        "DJ": "warning",  # flake8-django
        "NPY": "warning",  # NumPy-specific rules
        "PD": "warning",  # pandas-vet
        "C90": "warning",  # mccabe complexity
        "FAST": "warning",  # FastAPI
        # --- Convention / style / naming / imports / docs ---
        "W": "convention",  # pycodestyle Warning (mostly stylistic)
        "N": "convention",  # pep8-naming
        "D": "convention",  # pydocstyle
        "DOC": "convention",  # pydoclint
        "COM": "convention",  # flake8-commas
        "Q": "convention",  # flake8-quotes
        "PT": "convention",  # flake8-pytest-style
        "PYI": "convention",  # flake8-pyi (stub file conventions)
        "ANN": "convention",  # flake8-annotations
        "FA": "convention",  # flake8-future-annotations
        "ICN": "convention",  # flake8-import-conventions
        "TID": "convention",  # flake8-tidy-imports
        "I": "convention",  # isort
        "CPY": "convention",  # flake8-copyright
        "INP": "convention",  # flake8-no-pep420
        "EXE": "convention",  # flake8-executable
        "YTT": "convention",  # flake8-2020
        "INT": "convention",  # flake8-gettext
        "PLC": "convention",  # Pylint Convention
        "PGH": "convention",  # pygrep-hooks
        "TD": "convention",  # flake8-todos
        "FIX": "convention",  # flake8-fixme
        "EM": "convention",  # flake8-errmsg
        "A": "convention",  # flake8-builtins (shadowing)
        "SLOT": "convention",  # flake8-slots
        # --- Refactor / modernization / simplification ---
        "UP": "refactor",  # pyupgrade
        "SIM": "refactor",  # flake8-simplify
        "PLR": "refactor",  # Pylint Refactor
        "PTH": "refactor",  # flake8-use-pathlib
        "ERA": "refactor",  # eradicate (commented-out code)
        "C4": "refactor",  # flake8-comprehensions
        "PIE": "refactor",  # flake8-pie
        "FLY": "refactor",  # flynt (f-string conversion)
        "FURB": "refactor",  # refurb
        "RUF": "refactor",  # Ruff-specific rules
    }

    # Weight applied per category (used in the Pylint-style score formula).
    # error counts get their usual x5 multiplier baked in via CATEGORY_MULTIPLIER,
    # but individual prefixes can still be nudged with a per-prefix weight for
    # severity within a category (e.g. security issues weigh more than a stray print).
    RULE_WEIGHTS: ClassVar = {
        # errors
        "E": 5,
        "F": 5,
        "PLE": 5,
        "AIR": 3,
        # security — weighted highest among non-error issues
        "S": 4,
        # warnings
        "B": 2,
        "BLE": 2,
        "ASYNC": 3,
        "DTZ": 2,
        "G": 1,
        "LOG": 1,
        "PERF": 2,
        "PLW": 2,
        "TRY": 2,
        "RET": 1,
        "RSE": 1,
        "SLF": 1,
        "ARG": 1,
        "T20": 1,
        "T10": 2,
        "ISC": 1,
        "FBT": 1,
        "DJ": 2,
        "NPY": 1,
        "PD": 1,
        "C90": 2,
        "FAST": 1,
        # conventions
        "W": 1,
        "N": 1,
        "D": 1,
        "DOC": 1,
        "COM": 1,
        "Q": 1,
        "PT": 1,
        "PYI": 1,
        "ANN": 1,
        "FA": 1,
        "ICN": 1,
        "TID": 1,
        "I": 1,
        "CPY": 1,
        "INP": 1,
        "EXE": 1,
        "YTT": 1,
        "INT": 1,
        "PLC": 1,
        "PGH": 1,
        "TD": 1,
        "FIX": 1,
        "EM": 1,
        "A": 1,
        "SLOT": 1,
        # refactor
        "UP": 1,
        "SIM": 1,
        "PLR": 1,
        "PTH": 1,
        "ERA": 1,
        "C4": 1,
        "PIE": 1,
        "FLY": 1,
        "FURB": 1,
        "RUF": 1,
    }

    def __init__(self, default_weight: int = 1, default_category: str = "refactor"):
        """Initialize RuffScore."""
        self.default_weight = default_weight
        self.default_category = default_category

    def count_statements(self, file_path: Path) -> int:
        """Count the number of statements in a Python file."""
        try:
            with file_path.open(encoding="utf-8") as f:
                tree = ast.parse(f.read())
            return self._count_statements_in_node(tree)
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return 0

    def _count_statements_in_node(self, node: ast.AST) -> int:
        """Recursively count statements in an AST node."""
        count = 0
        if isinstance(node, ast.stmt):
            count = 1

        for child in ast.iter_child_nodes(node):
            count += self._count_statements_in_node(child)

        return count

    def _get_rule_prefix(self, rule_code: str) -> str:
        """Resolve a Ruff code like 'E501', 'PLE0101', 'ASYNC100', or 'C401' to
        its category prefix ('E', 'PLE', 'ASYNC', 'C4' respectively).

        Most Ruff prefixes are purely alphabetic (E, F, PLE, ASYNC, ...), but
        a handful embed a digit as part of the prefix itself (C4, C90, T10,
        T20), so we can't just grab the leading alphabetic run — we match
        against every known prefix and take the longest one that the code
        starts with.
        """
        if not rule_code:
            return ""

        best_match = ""
        for candidate in self.RULE_WEIGHTS:
            if rule_code.startswith(candidate) and len(candidate) > len(best_match):
                best_match = candidate

        if best_match:
            return best_match

        # Fall back to the leading alphabetic characters (unknown prefix).
        alpha = ""
        for ch in rule_code:
            if ch.isalpha():
                alpha += ch
            else:
                break
        return alpha

    def _get_checked_files(self, cmd: list[str]) -> list[Path]:
        """Get a list of files checked by Ruff."""
        cmd.extend(["--show-files"])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.stdout:
                sys.stdout.flush()
                all_files = [Path(p) for p in result.stdout.split("\n")[:-1]]
                return [p for p in all_files if p.suffix == ".py"]
        except subprocess.CalledProcessError as e:
            print(f"Error running Ruff: {e}")
        return []

    def get_rule_weight(self, rule_code: str) -> int:
        """Get the weight for a specific rule code."""
        prefix = self._get_rule_prefix(rule_code)
        return self.RULE_WEIGHTS.get(prefix, self.default_weight)

    def get_rule_category(self, rule_code: str) -> str:
        """Get the Pylint-style category (error/warning/convention/refactor)
        for a specific rule code.
        """
        prefix = self._get_rule_prefix(rule_code)
        return self.RULE_CATEGORIES.get(prefix, self.default_category)

    def run_ruff(self, path: Path, config_file: Path | None = None) -> CheckResult:
        """Run Ruff and return JSON output."""
        cmd = ["ruff", "check", "--output-format=json", path]
        if config_file:
            cmd.extend(["--config", config_file])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            checked_files = self._get_checked_files(cmd)
            if result.stdout:
                return CheckResult(files=checked_files, issues=json.loads(result.stdout))
            return CheckResult(files=checked_files)
        except subprocess.CalledProcessError as e:
            print(f"Error running Ruff: {e}")
            return CheckResult()
        except json.JSONDecodeError as e:
            print(f"Error parsing Ruff JSON output: {e}")
            return CheckResult()

    def categorize_issues(self, issues: list[dict]) -> dict[str, int]:
        """Categorize issues by Pylint-style type (error/warning/convention/refactor)."""
        categories = {"error": 0, "warning": 0, "convention": 0, "refactor": 0}

        for issue in issues:
            rule_code = issue.get("code", "")
            category = self.get_rule_category(rule_code)
            categories[category] = categories.get(category, 0) + 1

        return categories

    def calculate_score(self, issues: list[dict], total_statements: int) -> tuple[float, dict]:
        """Calculate Pylint-style score.

        Uses the standard Pylint formula:
            10.0 - ((5*error + warning + refactor + convention) / statements) * 10

        Each issue also carries a per-rule weight (get_rule_weight) reflecting
        its severity within its category (e.g. SQL injection vs. a stray print);
        that weight is summed in place of a flat "1 per issue" count so more
        dangerous rules within the same category still hurt the score more.
        """
        if total_statements == 0:
            return 10.0, {}

        categories = {"error": 0, "warning": 0, "convention": 0, "refactor": 0}
        weighted_totals = {"error": 0, "warning": 0, "convention": 0, "refactor": 0}

        for issue in issues:
            rule_code = issue.get("code", "")
            category = self.get_rule_category(rule_code)
            weight = self.get_rule_weight(rule_code)
            categories[category] = categories.get(category, 0) + 1
            weighted_totals[category] = weighted_totals.get(category, 0) + weight

        # Errors keep Pylint's x5 emphasis; other categories use their
        # accumulated per-rule weights directly.
        weighted_issues = (
            5 * weighted_totals["error"]
            + weighted_totals["warning"]
            + weighted_totals["refactor"]
            + weighted_totals["convention"]
        )

        score = 10.0 - ((float(weighted_issues) / total_statements) * 10)

        return score, categories

    def score_file(self, file_path: Path, config_file: Path | None = None) -> dict:
        """Score a single file."""
        issues = self.run_ruff(file_path, config_file)
        statements = self.count_statements(file_path)
        score, categories = self.calculate_score(issues, statements)

        return {
            "file": file_path,
            "score": score,
            "statements": statements,
            "issues": categories,
            "total_issues": len(issues),
            "raw_issues": issues,
        }

    def score_directory(self, directory: Path, config_file: Path | None = None) -> dict:
        """Score all Python files in a directory."""
        result = self.run_ruff(directory, config_file)

        # Count total statements in all Python files
        total_statements = 0
        for py_file in result.files:
            total_statements += self.count_statements(py_file)

        score, categories = self.calculate_score(result.issues, total_statements)

        return {
            "directory": directory,
            "score": score,
            "statements": total_statements,
            "files_analyzed": len(result.files),
            "issues": categories,
            "total_issues": len(result.issues),
            "raw_issues": result.issues,
        }

    def print_report(self, result: dict) -> None:
        """Print a formatted report."""
        print("=" * 50)
        print("RUFF QUALITY SCORE REPORT")
        print("=" * 50)
        print(f"Target: {result.get('file', result.get('directory', 'Unknown'))}")
        print(f"Score: {result['score']:.2f}/10.00")
        print(f"Statements analyzed: {result['statements']}")
        if "files_analyzed" in result:
            print(f"Files analyzed: {result['files_analyzed']}")
        print(f"Total issues: {result['total_issues']}")
        print()
        print("Issues by category:")
        for category, count in result["issues"].items():
            print(f"  {category.title()}: {count}")
        print()

        # Show score interpretation
        if result["score"] >= 9.0:
            print("Excellent code quality!")
        elif result["score"] >= 7.0:
            print("Good code quality")
        elif result["score"] >= 5.0:
            print("Needs improvement")
        else:
            print("Poor code quality - significant issues found")
