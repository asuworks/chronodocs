import subprocess
from pathlib import Path

import pytest

from chronodocs.config import get_config
from chronodocs.reporter import Reporter


@pytest.fixture
def temp_repo_with_config(tmp_path: Path) -> Path:
    """Creates a temporary git repo with config for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )

    # Create a config file for the repo
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
        - ".txt"
    group_by: "updated_day"
    sort_by: "updated_desc"
"""
    (repo_path / ".chronodocs.yml").write_text(config_content)

    return repo_path


def test_generate_report_scans_all_files(temp_repo_with_config: Path):
    """Test that reporter scans all files based on watch_paths, not just phase directory."""
    repo_root = temp_repo_with_config

    # --- Setup ---
    # 1. Create files in different locations
    root_file = repo_root / "root_doc.md"
    root_file.write_text("This is a root document.")

    phase_dir = repo_root / ".devcontext" / "progress" / "test_phase"
    phase_dir.mkdir(parents=True)
    phase_file = phase_dir / "phase_doc.md"
    phase_file.write_text("This is a phase document.")

    src_dir = repo_root / "src"
    src_dir.mkdir()
    src_file = src_dir / "code.py"
    src_file.write_text("# Python code")

    # 2. Commit some files
    subprocess.run(["git", "add", root_file], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "add root doc"], cwd=repo_root, check=True)

    # --- Test ---
    config = get_config(repo_root)
    reporter = Reporter(config=config, repo_path=repo_root, phase=None)
    report = reporter.generate_report()

    # --- Assertions ---
    assert "# Project Change Log" in report
    assert "**Total files:** 2" in report

    # Check all files are included
    assert "root_doc.md" not in report  # Committed, should be excluded
    assert "phase_doc.md" in report
    assert "code.py" in report

    # Check git statuses
    report_lines = report.split('\n')
    table_lines = [line for line in report_lines if line.startswith("|")]
    table_content = "\n".join(table_lines)
    assert "root_doc.md" not in table_content # Committed, should be excluded

    phase_line = [line for line in table_lines if "phase_doc.md" in line][0]
    assert "🟢 new" in phase_line
    code_line = [line for line in table_lines if "code.py" in line][0]
    assert "🟢 new" in code_line


def test_generate_report_respects_ignore_patterns(temp_repo_with_config: Path):
    """Test that reporter respects ignore patterns."""
    repo_root = temp_repo_with_config

    # --- Setup ---
    # Create files that should be ignored
    (repo_root / ".git" / "config").parent.mkdir(exist_ok=True)
    git_file = repo_root / ".git" / "some_file.txt"
    git_file.write_text("Should be ignored")

    creation_index = repo_root / ".creation_index.json"
    creation_index.write_text('{"test": "ignored"}')

    change_log = repo_root / "change_log.md"
    change_log.write_text("# Should be ignored")

    # Create files that should be included
    doc_file = repo_root / "document.md"
    doc_file.write_text("Should be included")

    # --- Test ---
    config = get_config(repo_root)
    reporter = Reporter(config=config, repo_path=repo_root, phase=None)
    report = reporter.generate_report()

    # --- Assertions ---
    assert "document.md" in report
    assert "Should be ignored" not in report
    assert ".creation_index.json" not in report
    assert "change_log.md" not in report


def test_generate_report_respects_extensions(temp_repo_with_config: Path):
    """Test that reporter only includes files with specified extensions."""
    repo_root = temp_repo_with_config

    # --- Setup ---
    md_file = repo_root / "doc.md"
    md_file.write_text("Markdown file")

    py_file = repo_root / "script.py"
    py_file.write_text("# Python file")

    txt_file = repo_root / "notes.txt"
    txt_file.write_text("Text file")

    # File with non-included extension
    js_file = repo_root / "app.js"
    js_file.write_text("// JavaScript file")

    # --- Test ---
    config = get_config(repo_root)
    reporter = Reporter(config=config, repo_path=repo_root, phase=None)
    report = reporter.generate_report()

    # --- Assertions ---
    assert "doc.md" in report
    assert "script.py" in report
    assert "notes.txt" in report
    assert "app.js" not in report  # .js not in configured extensions


def test_generate_report_with_git_statuses(temp_repo_with_config: Path):
    """Test that reporter correctly shows git statuses."""
    repo_root = temp_repo_with_config

    # --- Setup ---
    # 1. Committed file
    committed_file = repo_root / "committed.md"
    committed_file.write_text("Committed content")
    subprocess.run(["git", "add", committed_file], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add committed file"], cwd=repo_root, check=True
    )

    # 2. Modified file
    modified_file = repo_root / "modified.md"
    modified_file.write_text("Initial content")
    subprocess.run(["git", "add", modified_file], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add modified file"], cwd=repo_root, check=True
    )
    modified_file.write_text("Modified content")

    # 3. New file
    new_file = repo_root / "new.md"
    new_file.write_text("New content")

    # 4. Staged file
    staged_file = repo_root / "staged.md"
    staged_file.write_text("Staged content")
    subprocess.run(["git", "add", staged_file], cwd=repo_root, check=True)

    # --- Test ---
    config = get_config(repo_root)
    reporter = Reporter(config=config, repo_path=repo_root, phase=None)
    report = reporter.generate_report()

    # --- Assertions ---
    assert "committed.md" not in report  # Committed files are excluded
    assert "modified.md" in report
    assert "new.md" in report
    assert "staged.md" in report

    # Check status indicators
    report_lines = report.split('\n')
    table_lines = [line for line in report_lines if line.startswith("|")]
    table_content = "\n".join(table_lines)
    assert "committed.md" not in table_content

    modified_line = [line for line in table_lines if "modified.md" in line][0]
    assert "🟡 modified" in modified_line
    new_line = [line for line in table_lines if "new.md" in line][0]
    assert "🟢 new" in new_line
    staged_line = [line for line in table_lines if "staged.md" in line][0]
    assert "🔵 staged" in staged_line


def test_generate_report_empty_project(temp_repo_with_config: Path):
    """Test reporter with no matching files."""
    repo_root = temp_repo_with_config

    # Don't create any files

    # --- Test ---
    config = get_config(repo_root)
    reporter = Reporter(config=config, repo_path=repo_root, phase=None)
    report = reporter.generate_report()

    # --- Assertions ---
    assert "No staged, unstaged, or untracked files found." in report


def test_generate_report_includes_phase_name_when_provided(temp_repo_with_config: Path):
    """Test that phase name appears in report header when provided."""
    repo_root = temp_repo_with_config

    # Create a test file
    test_file = repo_root / "test.md"
    test_file.write_text("Test content")

    # --- Test with phase ---
    config = get_config(repo_root)
    reporter = Reporter(config=config, repo_path=repo_root, phase="test_phase")
    report = reporter.generate_report()

    assert "**Phase:** test_phase" in report

    # --- Test without phase ---
    reporter_no_phase = Reporter(config=config, repo_path=repo_root, phase=None)
    report_no_phase = reporter_no_phase.generate_report()

    assert (
        "**Phase:**" not in report_no_phase or "**Phase:** None" not in report_no_phase
    )
