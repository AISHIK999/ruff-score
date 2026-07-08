# Ruff Score 🎯

A Pylint-style scoring system for Ruff linter output. Get a numerical quality score (0-10) for your Python code based on Ruff's analysis, using a rule-category mapping that covers every prefix in [Ruff's rule set](https://docs.astral.sh/ruff/rules/).

## Features

- 🎯 **Pylint-style scoring**: Familiar 0-10 quality score system, using Pylint's own formula
- 🔧 **Ruff integration**: Built on top of the fast Ruff linter
- 🗂️ **Full rule coverage**: Every Ruff prefix (E, F, PLE/PLC/PLR/PLW, ASYNC, S, TRY, RUF, and 40+ more) is mapped to a Pylint-style category and severity weight — not just a handful of common ones
- ⚖️ **Two-level weighting**: Issues are bucketed into `error` / `warning` / `convention` / `refactor`, and within a category, individual rules can carry different weights (e.g. a SQL-injection finding counts for more than a stray `print`)
- 📊 **Detailed reports**: Categorized issue breakdown with a printable summary
- 📁 **File & directory support**: Analyze single files or entire projects
- ⚙️ **Configurable**: Use your existing Ruff configuration file, and override weights/categories in Python

## Installation

```bash
pip install ruff-score
```

## Quick Start

```python
from ruff_score import RuffScorer

scorer = RuffScorer()

# Score a single file
result = scorer.score_file("myfile.py")
print(f"Score: {result['score']:.2f}/10.00")

# Score a directory
result = scorer.score_directory("src/")
scorer.print_report(result)

# Score against a specific Ruff config
result = scorer.score_directory("src/", config_file="pyproject.toml")
```

## How It Works

Ruff Score uses the same scoring formula as Pylint:

```
Score = 10.0 - ((5*errors + warnings + refactor + convention) / statements * 10)
```

`statements` is the number of AST statement nodes in the analyzed file(s), and `errors` / `warnings` / `refactor` / `convention` are the **weighted** issue totals for each category — not just raw counts. So a category's contribution to the score is the sum of each issue's individual rule weight, which means two "warning"-category issues aren't necessarily worth the same amount if one rule is riskier than another.

### Rule Categories & Weights

Every Ruff prefix is mapped to one of four Pylint-style categories, based on [Ruff's documented rule set](https://docs.astral.sh/ruff/rules/):

| Category | Meaning | Example prefixes | Typical weight |
|---|---|---|---|
| **Error** | Real bugs / correctness issues | `E` (pycodestyle), `F` (Pyflakes), `PLE` (Pylint errors), `AIR` (Airflow) | 3–5 |
| **Warning** | Security risks and likely-bug patterns | `S` (bandit/security), `B` (bugbear), `ASYNC`, `TRY`, `PERF`, `T20`/`T10`, `DTZ`, `PLW` | 1–4 |
| **Convention** | Naming, docs, style, imports | `N` (naming), `D` (docstrings), `ANN`, `I` (isort), `Q`, `COM`, `PLC` | 1 |
| **Refactor** | Modernization / simplification | `UP` (pyupgrade), `SIM` (simplify), `PLR`, `PTH`, `C4`, `RUF` | 1 |

The full mapping (`RULE_CATEGORIES` and `RULE_WEIGHTS`) lives at the top of `ruff_scorer.py` and covers ~50 rule prefixes, including ones that embed a digit in the prefix itself (e.g. `C4`, `C90`, `T10`, `T20`) and multi-letter prefixes (e.g. `PLE`, `ASYNC`, `TRY`). Any prefix Ruff adds in the future that isn't in the table falls back to `default_weight` / `default_category`.

### Score Interpretation

- **9.0-10.0**: Excellent code quality
- **7.0-8.9**: Good code quality
- **5.0-6.9**: Needs improvement
- **0.0-4.9**: Poor code quality

## Example Output

```
==================================================
RUFF QUALITY SCORE REPORT
==================================================
Target: src/
Score: 8.45/10.00
Statements analyzed: 1,247
Files analyzed: 23
Total issues: 12

Issues by category:
  Error: 0
  Warning: 3
  Convention: 8
  Refactor: 1

Good code quality
```

## Advanced Usage

### Custom Weights and Categories

```python
from ruff_scorer import RuffScorer

# Change the fallback used for any rule prefix not in RULE_WEIGHTS/RULE_CATEGORIES
scorer = RuffScorer(default_weight=2, default_category="warning")

# Override the weight or category for a specific prefix
scorer.RULE_WEIGHTS["D"] = 1        # docstring issues
scorer.RULE_CATEGORIES["D"] = "convention"

# Inspect how a given rule code resolves
scorer.get_rule_weight("S608")      # -> 4
scorer.get_rule_category("S608")    # -> "warning"
```

### Integration with CI/CD

```python
# check_quality.py
import sys
from ruff_scorer import RuffScorer

scorer = RuffScorer()
result = scorer.score_directory("src/")
scorer.print_report(result)

THRESHOLD = 7.0
sys.exit(0 if result["score"] >= THRESHOLD else 1)
```

```bash
python check_quality.py && echo "Quality check passed!" || echo "Quality check failed!"
```

## Configuration

Ruff Score respects your existing Ruff configuration by passing it straight through to `ruff check --config`. Place your settings in:

- `pyproject.toml`
- `ruff.toml`
- `.ruff.toml`

Example configuration:

```toml
[tool.ruff]
line-length = 88
target-version = "py38"

[tool.ruff.lint]
select = ["E", "F", "W", "C", "N", "D", "S", "B"]
ignore = ["E501", "D100"]
```

## Requirements

- Python 3.8+
- Ruff installed and available on your `PATH`

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Related Projects

- [Ruff](https://github.com/astral-sh/ruff) - The fast Python linter
- [Pylint](https://github.com/pylint-dev/pylint) - The original Python code quality tool
