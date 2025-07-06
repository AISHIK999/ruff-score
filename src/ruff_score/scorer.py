"""
Ruff Quality Score Calculator
Implements a Pylint-style scoring system for Ruff output.
"""

import json
import subprocess
import ast
from pathlib import Path
from typing import Dict, List, Tuple


class RuffScorer:
    """Calculate code quality scores based on Ruff output."""

    # Ruff rule categories mapped to Pylint-style weights
    RULE_WEIGHTS = {
        "E": 5,  # Error (like Pylint errors)
        "W": 1,  # Warning
        "F": 5,  # Pyflakes (errors)
        "C": 1,  # Convention (mccabe, flake8-comprehensions, etc.)
        "N": 1,  # Naming conventions
        "D": 1,  # Docstring conventions
        "S": 2,  # Security (bandit) - higher weight
        "B": 2,  # Bugbear - higher weight
        "A": 1,  # Builtins
        "T": 1,  # Print/TODO
        "I": 1,  # Import sorting
        "UP": 1,  # Pyupgrade
        "SIM": 1,  # Simplify
        "PIE": 1,  # Flake8-pie
        "RET": 1,  # Return
        "ICN": 1,  # Import conventions
        "TCH": 1,  # Type checking
        "ARG": 1,  # Unused arguments
        "PTH": 1,  # Pathlib
        "ERA": 1,  # Eradicate
        "PL": 1,  # Pylint rules
        "TRY": 1,  # Tryceratops
        "RSE": 1,  # Raise
        "SLF": 1,  # Self
        "RUF": 1,  # Ruff-specific
    }

    def __init__(self, default_weight: int = 1):
        self.default_weight = default_weight

    def count_statements(self, file_path: str) -> int:
        """Count the number of statements in a Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
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

    def get_rule_weight(self, rule_code: str) -> int:
        """Get the weight for a specific rule code."""
        # Extract the rule prefix (e.g., 'E' from 'E501')
        prefix = rule_code[0] if rule_code else ""
        return self.RULE_WEIGHTS.get(prefix, self.default_weight)

    def run_ruff(self, path: str, config_file: str = None) -> List[Dict]:
        """Run Ruff and return JSON output."""
        cmd = ["ruff", "check", "--output-format=json", path]
        if config_file:
            cmd.extend(["--config", config_file])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.stdout:
                return json.loads(result.stdout)
            return []
        except subprocess.CalledProcessError as e:
            print(f"Error running Ruff: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing Ruff JSON output: {e}")
            return []

    def categorize_issues(self, issues: List[Dict]) -> Dict[str, int]:
        """Categorize issues by type with weights."""
        categories = {"error": 0, "warning": 0, "convention": 0, "refactor": 0}

        for issue in issues:
            rule_code = issue.get("code", "")
            weight = self.get_rule_weight(rule_code)

            # Map to Pylint-style categories
            if weight >= 5:
                categories["error"] += 1
            elif weight >= 2:
                categories["warning"] += 1
            elif rule_code.startswith(("C", "N", "D", "I")):
                categories["convention"] += 1
            else:
                categories["refactor"] += 1

        return categories

    def calculate_score(
        self, issues: List[Dict], total_statements: int
    ) -> Tuple[float, Dict]:
        """Calculate Pylint-style score."""
        if total_statements == 0:
            return 10.0, {}

        categories = self.categorize_issues(issues)

        # Pylint formula: 10.0 - ((float(5*error + warning + refactor + convention)/statement)*10)
        weighted_issues = (
            5 * categories["error"]
            + categories["warning"]
            + categories["refactor"]
            + categories["convention"]
        )

        score = 10.0 - ((float(weighted_issues) / total_statements) * 10)

        return score, categories

    def score_file(self, file_path: str, config_file: str = None) -> Dict:
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

    def score_directory(self, directory: str, config_file: str = None) -> Dict:
        """Score all Python files in a directory."""
        issues = self.run_ruff(directory, config_file)

        # Count total statements in all Python files
        total_statements = 0
        py_files = list(Path(directory).rglob("*.py"))

        for py_file in py_files:
            total_statements += self.count_statements(str(py_file))

        score, categories = self.calculate_score(issues, total_statements)

        return {
            "directory": directory,
            "score": score,
            "statements": total_statements,
            "files_analyzed": len(py_files),
            "issues": categories,
            "total_issues": len(issues),
            "raw_issues": issues,
        }

    def print_report(self, result: Dict):
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
            print("🎉 Excellent code quality!")
        elif result["score"] >= 7.0:
            print("✅ Good code quality")
        elif result["score"] >= 5.0:
            print("⚠️  Needs improvement")
        else:
            print("❌ Poor code quality - significant issues found")
