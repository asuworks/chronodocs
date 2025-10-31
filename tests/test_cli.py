import pytest
from pathlib import Path
import subprocess
from unittest.mock import patch

from chronodocs.cli import main

@pytest.fixture
def temp_phase_dir_for_cli(tmp_path: Path) -> Path:
    """Sets up a temporary directory structure for CLI testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    (repo_path / ".chronodocs.yml").write_text("phase_dir_template: 'docs/{phase}'")

    phase_dir = repo_path / "docs" / "cli_phase"
    phase_dir.mkdir(parents=True)

    (phase_dir / "test.md").write_text("cli test")

    return repo_path

def test_cli_report_command(temp_phase_dir_for_cli: Path, capsys):
    """Test the 'report' command of the CLI."""

    repo_root = temp_phase_dir_for_cli
    output_file = repo_root / "change_log.md"

    # Use patch to simulate command-line arguments
    with patch('sys.argv', [
        'chronodocs',
        'report',
        '--phase', 'cli_phase',
        '--repo-root', str(repo_root),
        '--output', str(output_file)
    ]):
        main()

    # Check that the output file was created
    assert output_file.is_file()

    # Check the content of the file
    content = output_file.read_text()
    assert "# Phase Change Log" in content
    assert "**Phase:** cli_phase" in content
    assert "test.md" in content

    # Check the stdout message
    captured = capsys.readouterr()
    assert f"Report written to {output_file}" in captured.out
