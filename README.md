# Ruff Score 🎯

A Pylint-style scoring system for Ruff linter output. Get a numerical quality score (0-10) for your Python code based on Ruff's analysis, using a rule-category mapping that covers about 60 prefixes from [Ruff's rule set](https://docs.astral.sh/ruff/rules/).

## Features

- 🎯 **Pylint-style scoring**: Familiar 0-10 quality score, based on Pylint's formula
- 🔧 **Ruff integration**: Built on top of the fast Ruff linter
- 🗂️ **Broad rule coverage**: About 60 Ruff prefixes (E, F, PLE/PLC/PLR/PLW, ASYNC, S, TRY, RUF, and more) are mapped to a Pylint-style category and severity weight. Any prefix not in the table falls back to a configurable default.
- ⚖️ **Per-rule weighting**: Issues are bucketed into `error` / `warning` / `convention` / `refactor`, and each rule carries its own weight (e.g. a SQL-injection finding counts for more than a stray `print`). Exact codes can override their prefix, so `E501` (line too long) is a convention issue while the rest of `E` stays an error.
- 🚨 **Syntax errors count as errors**: Files Ruff cannot parse are scored as severe errors instead of slipping through.
- 📊 **Detailed reports**: Categorized issue breakdown as text or JSON
- 📁 **File & directory support**: Analyze single files or entire projects. Directory scoring only counts the files Ruff actually checks, so `.venv/`, `node_modules/` and anything in your `exclude` / `.gitignore` are ignored.
- 💻 **CLI with CI support**: `--fail-under` makes the exit code usable as a quality gate
- ⚙️ **Configurable**: Use your existing Ruff configuration file, and override weights/categories in Python

## Installation

```bash
pip install ruff-score
```

Ruff is installed automatically as a dependency. `ruff-score` runs it with the same Python interpreter, so it doesn't need to be on your `PATH`.

## Quick Start

### Command line

```bash
# Score a file or directory
ruff-score src/

# Use a specific Ruff config
ruff-score src/ --config pyproject.toml

# Fail (exit code 1) if the score is below 7.0
ruff-score src/ --fail-under 7.0

# Machine-readable output
ruff-score src/ --json
```

Exit codes: `0` = OK, `1` = score below `--fail-under`, `2` = error (Ruff failed, path not found).

### Python API

```python
from pathlib import Path
from ruff_score import format_report, score_path

# Score a single file
result = score_path(Path("myfile.py"))
print(f"Score: {result.score:.2f}/10.00")

# Score a directory and print a report
result = score_path(Path("src/"))
print(format_report(result))

# Score against a specific Ruff config
result = score_path(Path("src/"), config_file="pyproject.toml")
```

`score_path` accepts a file or a directory and returns a frozen `ScoreResult` dataclass:

| Field | Description |
|---|---|
| `target` | The path that was scored |
| `score` | Quality score, clamped to 0.0-10.0 |
| `statements` | Number of AST statements analyzed |
| `files_analyzed` | Number of files included in the statement count |
| `counts` | Issue count per category (`error`, `warning`, `convention`, `refactor`) |
| `total_issues` | Total number of Ruff issues |
| `issues` | Raw Ruff issue dicts |

If Ruff can't be launched, crashes, or returns unparseable output, `score_path` raises `ruff_score.RuffError` instead of returning a misleading score.

## How It Works

```
Score = 10.0 - (sum of issue weights / statements) * 10
```

`statements` is the number of AST statement nodes in the analyzed file(s). Each issue contributes its own rule **weight** to the sum, so two issues in the same category aren't necessarily worth the same. Errors default to a weight of 5, which reproduces Pylint's "errors count five times as much" rule without a second multiplier. The result is clamped to the range 0-10.

Edge cases:

- A file Python can't parse counts as 0 statements (a warning is logged), but Ruff still reports its syntax error, which is weighted as an error.
- If no statements are found, the score is 10.0 when Ruff reports nothing and 0.0 otherwise.

### Rule Categories & Weights

Each rule code is resolved with a **longest-prefix match** against the `RULES` table, so `F401` is found before `F`, and prefixes that embed a digit (`C4`, `C90`, `T10`, `T20`) or span several letters (`PLE`, `ASYNC`) resolve correctly. Based on [Ruff's documented rule set](https://docs.astral.sh/ruff/rules/):

| Category | Meaning | Example prefixes | Typical weight |
|---|---|---|---|
| **Error** | Real bugs / correctness issues | `E` (pycodestyle), `F` (Pyflakes), `PLE` (Pylint errors), `AIR` (Airflow) | 3-5 |
| **Warning** | Security risks and likely-bug patterns | `S` (bandit/security), `B` (bugbear), `ASYNC`, `TRY`, `PERF`, `T20`/`T10`, `DTZ`, `PLW` | 1-4 |
| **Convention** | Naming, docs, style, imports | `N` (naming), `D` (docstrings), `ANN`, `I` (isort), `Q`, `COM`, `PLC` | 1 |
| **Refactor** | Modernization / simplification | `UP` (pyupgrade), `SIM` (simplify), `PLR`, `PTH`, `C4`, `RUF` | 1 |

Exact-code overrides take precedence over their prefix:

| Code | Category | Weight | Why |
|---|---|---|---|
| `E402`, `E501`, `E741` | convention | 1 | Style issues, not bugs |
| `E711`, `E712` | warning | 2 | Comparisons to `None` / `True` / `False` |
| `E722` | warning | 3 | Bare `except` |
| `F401`, `F841` | warning | 2 | Unused import / variable |

Special cases:

- **Syntax errors** (Ruff reports them with no rule code): `error`, weight 5
- **Unknown prefixes**: `refactor`, weight 1 (`DEFAULT_RULE`)

The full table lives at the top of `src/ruff_score/scorer.py`.

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
Score: 9.42/10.00
Statements analyzed: 240
Files analyzed: 6
Total issues: 12

Issues by category:
  Error: 0
  Warning: 3
  Convention: 8
  Refactor: 1

Excellent code quality!
```

## Advanced Usage

### Custom Weights and Categories

The rules are plain module-level data, so you can change them before scoring:

```python
from ruff_score import classify, scorer

# Re-categorize or re-weight a prefix: (category, weight)
scorer.RULES["D"] = ("convention", 2)       # docstring issues count double
scorer.RULES["E501"] = ("convention", 0)    # ignore line length entirely

# Change the fallback for prefixes that aren't in the table
scorer.DEFAULT_RULE = ("warning", 2)

# Inspect how a given rule code resolves
classify("S608")     # -> ("warning", 4)
classify("E501")     # -> ("convention", 0)
classify(None)       # -> ("error", 5)  (syntax error)
```

### Integration with CI/CD

The simplest gate is the CLI:

```bash
ruff-score src/ --fail-under 7.0
```

For more control, use the Python API:

```python
# check_quality.py
import sys
from ruff_score import RuffError, format_report, score_path

THRESHOLD = 7.0

try:
    result = score_path("src/")
except RuffError as e:
    print(f"Could not run Ruff: {e}", file=sys.stderr)
    sys.exit(2)

print(format_report(result))
sys.exit(0 if result.score >= THRESHOLD else 1)
```

## Configuration

Ruff Score runs `ruff check` for you. Without `--config`, Ruff discovers your settings the usual way (`pyproject.toml`, `ruff.toml` or `.ruff.toml`). With `--config` / `config_file=`, the given file is passed straight through to `ruff check --config`.

Example configuration:

```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "C", "N", "D", "S", "B"]
ignore = ["E501", "D100"]
```

Scores depend on which rules your configuration enables. A project that selects only `E` and `F` will score higher than the same code checked with `select = ["ALL"]`. To compare scores across projects, use the same Ruff configuration for all of them.

## Requirements

- Python 3.10+
- Ruff (installed automatically as a dependency)

## Development

```bash
pip install -e . pytest
pytest
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Related Projects

- [Ruff](https://github.com/astral-sh/ruff) - The fast Python linter
- [Pylint](https://github.com/pylint-dev/pylint) - The original Python code quality tool