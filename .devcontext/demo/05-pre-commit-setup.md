# Pre-commit Hooks Setup

## What Was Done

Added pre-commit hooks to automatically format and lint code before each commit.

## Files Added

- `.pre-commit-config.yaml` - Pre-commit configuration
- Updated `README.md` - Added contributing section with pre-commit instructions

## Setup Commands

```bash
# Install pre-commit
uv tool install pre-commit

# Install the git hooks
pre-commit install

# Run on all files (optional, to format existing code)
pre-commit run --all-files
```

## What the Hooks Do

Every time you commit, these hooks automatically run:

1. **ruff check --fix**
   - Sorts imports
   - Fixes common linting issues
   - Ensures code quality

2. **ruff format**
   - Formats code with black-compatible style
   - Ensures consistent formatting

## Workflow

```bash
# Make changes
vim chronodocs/some_file.py

# Stage changes
git add chronodocs/some_file.py

# Commit (hooks run automatically)
git commit -m "feat: add feature"

# If hooks make changes:
# - Review them: git diff
# - Stage them: git add -u
# - Commit again: git commit -m "feat: add feature"
```

## Manual Usage

```bash
# Run on staged files only
pre-commit run

# Run on all files
pre-commit run --all-files

# Update to latest versions
pre-commit autoupdate

# Skip hooks (emergency only!)
git commit --no-verify
```

## Benefits

✅ Consistent code style across the project
✅ Catches issues before they reach CI
✅ Automatic import sorting
✅ No manual formatting needed
✅ Fast execution (ruff is written in Rust)

## Configuration

The `.pre-commit-config.yaml` file controls which hooks run and how:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.2
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

To customize, edit this file and run `pre-commit install` again.
