# Ruff Score 🎯

A Pylint-style scoring system for Ruff linter output. Get a numerical quality score (0-10) for your Python code based on Ruff's analysis.

## Features

- 🎯 **Pylint-style scoring**: Familiar 0-10 quality score system
- 🔧 **Ruff integration**: Built on top of the fast Ruff linter
- 📊 **Detailed reports**: Categorized issue breakdown
- 🎨 **Visual feedback**: Color-coded quality indicators
- 📁 **File & directory support**: Analyze single files or entire projects
- ⚙️ **Configurable**: Use your existing Ruff configuration

## Installation

```bash
pip install ruff-score
```

## Quick Start

### Command Line Usage

```bash
# Score a single file
ruff-score myfile.py

# Score a directory
ruff-score src/

# Use with custom Ruff config
ruff-score src/ pyproject.toml
```

### Python API

```python
from ruff_score import RuffScorer

scorer = RuffScorer()

# Score a file
result = scorer.score_file("myfile.py")
print(f"Score: {result['score']:.2f}/10.00")

# Score a directory
result = scorer.score_directory("src/")
scorer.print_report(result)
```

## How It Works

Ruff Score uses the same scoring formula as Pylint:

```
Score = 10.0 - ((5*errors + warnings + refactor + convention) / statements * 10)
```

### Rule Weights

Different Ruff rule categories have different weights:

- **Errors (E, F)**: Weight 5 (syntax errors, undefined names)
- **Security (S), Bugbear (B)**: Weight 2 (potential bugs, security issues)
- **Everything else**: Weight 1 (style, conventions, etc.)

### Score Interpretation

- **9.0-10.0**: 🎉 Excellent code quality
- **7.0-8.9**: ✅ Good code quality  
- **5.0-6.9**: ⚠️ Needs improvement
- **0.0-4.9**: ❌ Poor code quality

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

✅ Good code quality
```

## Advanced Usage

### Custom Rule Weights

```python
from ruff_score import RuffScorer

scorer = RuffScorer(default_weight=2)
# Customize weights for specific rule categories
scorer.RULE_WEIGHTS['D'] = 0.5  # Lower weight for docstring issues
```

### Integration with CI/CD

```bash
# Exit with non-zero code if score is below threshold
ruff-score src/ && echo "Quality check passed!" || echo "Quality check failed!"
```

## Configuration

Ruff Score respects your existing Ruff configuration. Place your settings in:

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
- Ruff 0.1.0+

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Related Projects

- [Ruff](https://github.com/astral-sh/ruff) - The fast Python linter
- [Pylint](https://github.com/pylint-dev/pylint) - The original Python code quality tool