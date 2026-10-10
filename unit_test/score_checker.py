import json
import subprocess
import sys

import pytest

from ruff_score.scorer import RuffError, calculate_score, classify, rating, score_path


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("C401", ("refactor", 1)),  # C4 prefix contains a digit
        ("C901", ("warning", 2)),  # C90
        ("T201", ("warning", 1)),  # T20
        ("T100", ("warning", 2)),  # T10
        ("PLE0101", ("error", 5)),  # multi-letter prefix
        ("ASYNC100", ("warning", 3)),
        ("E501", ("convention", 1)),  # exact override beats "E"
        ("E999", ("error", 5)),  # falls back to "E"
        ("F401", ("warning", 2)),
        ("F821", ("error", 5)),
        ("ZZZ999", ("refactor", 1)),  # unknown -> default
        (None, ("error", 5)),  # syntax error
        ("", ("error", 5)),
    ],
)
def test_classify(code, expected):
    assert classify(code) == expected


def test_score_clean_code_is_ten():
    score, counts = calculate_score([], 100)
    assert score == 10.0
    assert counts["error"] == 0


def test_score_weighted():
    issues = [{"code": "F821"}, {"code": "E501"}]  # weights 5 + 1
    score, counts = calculate_score(issues, 10)
    assert score == pytest.approx(4.0)
    assert counts["error"] == 1
    assert counts["convention"] == 1


def test_score_is_clamped():
    score, _ = calculate_score([{"code": "F821"}] * 100, 10)
    assert score == 0.0


def test_zero_statements_with_issues_is_not_perfect():
    score, counts = calculate_score([{"code": None}], 0)
    assert score == 0.0
    assert counts["error"] == 1


def test_rating_thresholds():
    assert rating(9.5).startswith("Excellent")
    assert rating(7.0) == "Good code quality"
    assert rating(0.0).startswith("Poor")


@pytest.fixture
def ef_config(tmp_path):
    """A minimal Ruff config so results don't depend on any config found near the temp files."""
    config = tmp_path / "ruff.toml"
    config.write_text('[lint]\nselect = ["E", "F"]\n')
    return config


def test_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        score_path(tmp_path / "nope.py")


def test_score_file_end_to_end(tmp_path, ef_config):
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n")
    assert score_path(clean, ef_config).score == 10.0

    dirty = tmp_path / "dirty.py"
    dirty.write_text("import os\nprint(undefined)\n")
    result = score_path(dirty, ef_config)
    assert result.counts["error"] >= 1  # F821 undefined name
    assert result.score < 10.0


def test_bad_config_raises_instead_of_perfect_score(tmp_path):
    target = tmp_path / "a.py"
    target.write_text("import os\n")
    bad_config = tmp_path / "ruff.toml"
    bad_config.write_text("this is = not valid toml [[[")
    with pytest.raises(RuffError):
        score_path(target, bad_config)


def test_directory_scoring_respects_ruff_excludes(tmp_path, ef_config):
    (tmp_path / "keep.py").write_text("x = 1\n")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "ignored.py").write_text("y = 2\nz = 3\n")
    result = score_path(tmp_path, ef_config)
    assert result.files_analyzed == 1
    assert result.statements == 1


def test_cli_json_and_fail_under(tmp_path, ef_config):
    target = tmp_path / "dirty.py"
    target.write_text("print(undefined)\n")
    cmd = [sys.executable, "-m", "ruff_score.cli", str(target), "--config", str(ef_config)]

    ok = subprocess.run([*cmd, "--json"], capture_output=True, text=True, check=False)
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["counts"]["error"] >= 1

    gated = subprocess.run([*cmd, "--fail-under", "9"], capture_output=True, text=True, check=False)
    assert gated.returncode == 1