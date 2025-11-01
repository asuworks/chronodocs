import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from chronodocs.cli import main


@pytest.fixture
def temp_repo_for_cli(tmp_path: Path) -> Path:
    """Sets up a temporary directory structure for CLI testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Create git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )

    # Create config
    config_content = """
phase_dir_template: '.devcontext/progress/{phase}'

watch_paths:
    - "."

ignore_patterns:
    - ".git/"
    - ".creation_index.json"
    - ".update_index.json"
    - "change_log.md"

report:
    extensions:
        - ".md"
        - ".py"
"""
    (repo_path / ".chronodocs.yml").write_text(config_content)

    # Create phase directory with files
    phase_dir = repo_path / ".devcontext" / "progress" / "test_phase"
    phase_dir.mkdir(parents=True)
    (phase_dir / "doc1.md").write_text("Document 1")
    (phase_dir / "doc2.md").write_text("Document 2")

    # Create root file
    (repo_path / "readme.md").write_text("Root readme")

    return repo_path


def test_cli_report_command_with_output(temp_repo_for_cli: Path, capsys):
    """Test the 'report' command with --output flag."""
    repo_root = temp_repo_for_cli
    output_file = repo_root / "my_report.md"

    # Use patch to simulate command-line arguments
    with patch(
        "sys.argv",
        [
            "chronodocs",
            "report",
            "--repo-root",
            str(repo_root),
            "--output",
            str(output_file),
        ],
    ):
        main()

    # Check that the output file was created
    assert output_file.is_file()

    # Check the content of the file
    content = output_file.read_text()
    assert "# Project Change Log" in content
    assert "**Total files:** 3" in content
    assert "doc1.md" in content
    assert "doc2.md" in content
    assert "readme.md" in content

    # Check the stdout message (with rich formatting)
    captured = capsys.readouterr()
    # The output now includes rich formatting with checkmark and cyan color codes
    # Rich may wrap long paths with newlines, so check for key parts
    # Remove newlines added by rich wrapping to check the content
    output_normalized = captured.out.replace("\n", "")
    assert "Report written to" in output_normalized
    assert "my_report.md" in output_normalized


def test_cli_report_command_to_stdout(temp_repo_for_cli: Path, capsys):
    """Test the 'report' command without --output (outputs to stdout)."""
    repo_root = temp_repo_for_cli

    # Use patch to simulate command-line arguments
    with patch(
        "sys.argv",
        ["chronodocs", "report", "--repo-root", str(repo_root)],
    ):
        main()

    # Check stdout contains the report
    captured = capsys.readouterr()
    assert "# Project Change Log" in captured.out
    assert "**Total files:** 3" in captured.out
    assert "doc1.md" in captured.out
    assert "doc2.md" in captured.out
    assert "readme.md" in captured.out


def test_cli_report_scans_all_files(temp_repo_for_cli: Path):
    """Test that report scans all files in watch_paths, not just phase directory."""
    repo_root = temp_repo_for_cli
    output_file = repo_root / "test_report.md"

    # Create additional files in different locations
    src_dir = repo_root / "src"
    src_dir.mkdir()
    (src_dir / "code.py").write_text("# Python code")

    docs_dir = repo_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("# Guide")

    # Commit one of the files
    subprocess.run(["git", "add", "readme.md"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add readme"], cwd=repo_root, check=True
    )

    with patch(
        "sys.argv",
        [
            "chronodocs",
            "report",
            "--repo-root",
            str(repo_root),
            "--output",
            str(output_file),
        ],
    ):
        main()

    content = output_file.read_text()
    assert "code.py" in content
    assert "guide.md" in content
    assert "doc1.md" in content
    assert "readme.md" not in content  # Committed, should be excluded
    assert "**Total files:** 4" in content


def test_cli_reconcile_command(temp_repo_for_cli: Path, capsys):
    """Test the 'reconcile' command."""
    repo_root = temp_repo_for_cli
    phase_dir = repo_root / ".devcontext" / "progress" / "test_phase"

    # Create unordered files
    (phase_dir / "zebra.md").write_text("Last alphabetically")
    (phase_dir / "alpha.md").write_text("First alphabetically")

    with patch(
        "sys.argv",
        [
            "chronodocs",
            "reconcile",
            "--phase",
            "test_phase",
            "--repo-root",
            str(repo_root),
        ],
    ):
        main()

    # Check files were numbered
    files = sorted(phase_dir.glob("*.md"))
    numbered_files = [f for f in files if f.name.startswith(("0", "1", "2", "3"))]
    assert len(numbered_files) > 0

    # Check stdout message
    captured = capsys.readouterr()
    assert "Reconciliation complete" in captured.out


def test_cli_reconcile_dry_run(temp_repo_for_cli: Path, capsys):
    """Test the 'reconcile' command with --dry-run."""
    repo_root = temp_repo_for_cli
    phase_dir = repo_root / ".devcontext" / "progress" / "test_phase"

    original_files = set(f.name for f in phase_dir.glob("*.md"))

    with patch(
        "sys.argv",
        [
            "chronodocs",
            "reconcile",
            "--phase",
            "test_phase",
            "--repo-root",
            str(repo_root),
            "--dry-run",
        ],
    ):
        main()

    # Files should not have been renamed
    current_files = set(f.name for f in phase_dir.glob("*.md"))
    assert original_files == current_files


def test_cli_watch_command_requires_phase(temp_repo_for_cli: Path):
    """Test that 'watch' command requires --phase argument."""
    repo_root = temp_repo_for_cli

    with patch(
        "sys.argv",
        ["chronodocs", "watch", "--repo-root", str(repo_root)],
    ):
        exit_code = main()
        assert exit_code == 2  # argparse error exit code


def test_cli_sentinel_command_requires_phase(temp_repo_for_cli: Path):
    """Test that 'sentinel' command requires --phase argument."""
    repo_root = temp_repo_for_cli

    with patch(
        "sys.argv",
        ["chronodocs", "sentinel", "--repo-root", str(repo_root)],
    ):
        exit_code = main()
        assert exit_code == 2  # argparse error exit code


def test_cli_start_command_requires_phase(temp_repo_for_cli: Path):
    """Test that 'start' command requires --phase argument."""
    repo_root = temp_repo_for_cli

    with patch(
        "sys.argv",
        ["chronodocs", "start", "--repo-root", str(repo_root)],
    ):
        exit_code = main()
        assert exit_code == 2  # argparse error exit code
