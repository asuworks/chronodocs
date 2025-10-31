# ChronoDocs Usage Guide

This guide provides practical examples for using ChronoDocs to manage your documentation.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Basic Workflow](#basic-workflow)
3. [Phase Watcher](#phase-watcher)
4. [Sentinel (Root) Watcher](#sentinel-root-watcher)
5. [Configuration Examples](#configuration-examples)
6. [Common Use Cases](#common-use-cases)
7. [Error Handling & CLI Features](#error-handling--cli-features)
8. [Troubleshooting](#troubleshooting)

## Quick Start

The easiest way to use ChronoDocs is with the `start` command, which runs both watchers together:

```bash
# Install ChronoDocs
uv tool install git+https://github.com/asuworks/chrono-docs

# Create a phase directory
mkdir -p .devcontext/progress/phase_1

# Start both watchers with a single command
chronodocs start --phase phase_1
```

That's it! Now:

- Files in `.devcontext/progress/phase_1/` will be automatically numbered chronologically
- Any changes in your project will trigger a change log update
- Press Ctrl+C to stop both watchers

**This is the recommended way to use ChronoDocs.**

## Basic Workflow

### 1. Initial Setup

```bash
# Install ChronoDocs globally
uv tool install git+https://github.com/asuworks/chrono-docs

# Or install from local clone
git clone https://github.com/asuworks/chrono-docs
cd chrono-docs
uv tool install --editable .

# Verify installation
chronodocs --help
```

### 2. Create a Phase Directory

```bash
mkdir -p .devcontext/progress/phase_1
```

### 3. Add Documentation Files

```bash
# Create some documentation files
echo "# Architecture Overview" > .devcontext/progress/phase_1/architecture.md
echo "# Implementation Plan" > .devcontext/progress/phase_1/implementation.md
echo "# API Design" > .devcontext/progress/phase_1/api-design.md
```

### 4. Run Reconciliation

```bash
# Preview what will be renamed (dry run)
chronodocs reconcile --phase phase_1 --dry-run

# Actually rename the files with chronological prefixes
chronodocs reconcile --phase phase_1
```

After reconciliation, your files will be renamed:

- `00-architecture.md`
- `01-implementation.md`
- `02-api-design.md`

### 5. Generate a Change Log

```bash
# Generate report to stdout
chronodocs report

# Save to file
chronodocs report --output changelog.md
```

Note: The change log automatically includes proper relative links from the phase directory to all tracked files.

## Phase Watcher

The phase watcher monitors a specific phase directory and automatically applies chronological naming when files change.

### Starting the Phase Watcher

```bash
chronodocs watch --phase phase_1
```

### What It Does

1. **On startup:** Runs initial reconciliation to catch any changes made while watcher was stopped
2. Watches `.devcontext/progress/phase_1/` for file changes
3. When files are added, modified, or deleted, waits for the debounce period (default: 2 seconds)
4. Automatically runs reconciliation to update file numbering
5. Maintains `.creation_index.json` and `.update_index.json` to track file history

### Example Workflow with Start Command (Recommended)

```bash
# Start both watchers with a single command
uv run chronodocs start --phase phase_1

# In another terminal, create/edit files
echo "# New Feature" > .devcontext/progress/phase_1/new-feature.md
# The phase watcher automatically renames it to 03-new-feature.md
# The sentinel automatically updates change_log.md
```

### Example Workflow with Separate Watchers (Advanced)

```bash
# Terminal 1: Start the phase watcher
uv run chronodocs watch --phase phase_1

# Terminal 2: Create/edit files
echo "# New Feature" > .devcontext/progress/phase_1/new-feature.md
# The watcher automatically renames it to 03-new-feature.md
```

### Configuration

```yaml
# .chronodocs.yml
debounce:
    phase: 2000 # Wait 2 seconds after last change before reconciling

ignore_patterns:
    - ".creation_index.json"
    - ".update_index.json"
    - "change_log.md"
    - "*.tmp"
```

## Sentinel (Root) Watcher

The sentinel watcher monitors your entire project and automatically generates change logs when files change.

### Starting the Sentinel

```bash
chronodocs sentinel --phase phase_1
```

### What It Does

1. **On startup:** Generates initial change log to catch any changes made while watcher was stopped
2. Watches paths specified in `watch_paths` (entire project or specific directories)
3. When changes are detected, waits for the debounce period (default: 3 seconds)
4. Automatically regenerates the change log
5. Ignores files matching `ignore_patterns`

### Configuration for Sentinel

```yaml
# .chronodocs.yml
watch_paths:
    - "." # Watch entire project
    # Or be more specific:
    # - "src/"
    # - "docs/"
    # - ".devcontext/progress/"

ignore_patterns:
    - ".git/"
    - ".venv/"
    - "node_modules/"
    - "__pycache__/"
    - "change_log.md" # Important: prevent feedback loop
    - ".creation_index.json"
    - ".update_index.json"

debounce:
    root: 3000 # Wait 3 seconds after last change

make_command: "uv run chronodocs report --phase phase_1 --output .devcontext/progress/phase_1/change_log.md"
```

### Example Workflow with Start Command (Recommended)

```bash
# Start both watchers together
uv run chronodocs start --phase phase_1

# Make changes anywhere in your project
echo "# Database Schema" > src/schema.md
# The sentinel detects the change and automatically regenerates change_log.md
```

### Example Workflow with Sentinel Only (Advanced)

```bash
# Terminal 1: Start the sentinel (must specify phase for output location)
chronodocs sentinel --phase current

# Terminal 2: Make changes anywhere in your project
echo "# Database Schema" > src/schema.md
# The sentinel detects the change and automatically regenerates change_log.md
```

## Configuration Examples

### Minimal Configuration

```yaml
# .chronodocs.yml
phase_dir_template: ".devcontext/progress/{phase}"

ignore_patterns:
    - ".git/"
    - ".venv/"
    - ".creation_index.json"
    - ".update_index.json"
    - "change_log.md"

report:
    extensions:
        - ".md"
```

### Full Configuration

```yaml
# .chronodocs.yml
phase_dir_template: ".devcontext/progress/{phase}"

watch_paths:
    - "."

ignore_patterns:
    - ".git/"
    - "node_modules/"
    - ".venv/"
    - "__pycache__/"
    - ".creation_index.json"
    - ".update_index.json"
    - "change_log.md"
    - "*.tmp"
    - ".DS_Store"

debounce:
    phase: 2000 # milliseconds
    root: 3000 # milliseconds

make_command: "uv run chronodocs report --phase current --output .devcontext/progress/current/change_log.md"

report:
    group_by: "updated_day" # updated_day | created_day | folder | status
    sort_by: "updated_desc" # updated_asc | updated_desc | created_asc | created_desc
    extensions:
        - ".md"
        - ".py"
        - ".txt"
        - ".yaml"

logging:
    level: "INFO" # DEBUG | INFO | ERROR
    format: "text" # text | json

timestamp_sources:
    - "git" # Prefer git commit timestamps
    - "filesystem" # Fall back to filesystem timestamps
```

## Common Use Cases

### Use Case 1: AI Agent Documentation

**Scenario:** An AI agent (Claude, Cursor, Windsurf, Copilot) creates documentation files with inconsistent naming.

**Solution:**

1. Configure ChronoDocs:

```yaml
# .chronodocs.yml
phase_dir_template: ".devcontext/progress/{phase}"
```

2. Add instructions for your AI agent (in `.cursorrules`, `.copilot-instructions.md`, or project rules):

```markdown
# Documentation Rules

IMPORTANT: NEVER create documentation files unless explicitly asked to do so.

Project-wide documents should be stored in `.devcontext/progress/{phase}/`

## ChronoDocs Watcher Behavior

The watcher auto-renames files in `.devcontext/progress/{phase}/` to `NN-<name>`
(00-, 01-, …) based on stable creation order.

**Never add numeric prefixes yourself** — create/update docs without them:
- ✅ Good: `architecture.md`, `api-design.md`
- ❌ Bad: `00-architecture.md`, `01-api-design.md`

Don't reference prefixes in links or code; use base names only.

Expect filenames to change automatically after creation.

## Current Phase
We are now in phase_xyz: ALL GENERAL PROJECT DOCUMENTATION MUST BE STORED
IN .devcontext/progress/phase_xyz/
```

3. Start both watchers:

```bash
chronodocs start --phase agent-session-1
```

4. As the agent creates files, they're automatically numbered chronologically and a change log is maintained.

### Use Case 2: Sprint Documentation

**Scenario:** Track all changes during a development sprint.

**Solution:**

1. Create a phase for the sprint:

```bash
mkdir -p .devcontext/progress/sprint-24
```

2. Start both watchers with a single command:

```bash
# Start both watchers for the sprint
chronodocs start --phase sprint-24
```

Or run them separately (advanced):

```bash
# Terminal 1: Watch the sprint documentation folder
chronodocs watch --phase sprint-24

# Terminal 2: Watch the entire project for a comprehensive change log
chronodocs sentinel --phase sprint-24
```

### Use Case 3: Manual Documentation Management

**Scenario:** You want control over when files are numbered.

**Solution:**

Use the `reconcile` and `report` commands manually:

```bash
# Add/edit files manually
vim .devcontext/progress/design/architecture.md

# When ready, apply numbering
chronodocs reconcile --phase design

# Generate the report
chronodocs report --output docs/design-log.md
```

### Use Case 4: Multi-Phase Project

**Scenario:** Multiple development phases with separate documentation.

**Solution:**

Use the `start` command for each phase in separate terminals:

```bash
# Terminal 1: Phase 1 - Planning
chronodocs start --phase planning

# Terminal 2: Phase 2 - Implementation
chronodocs start --phase implementation

# Terminal 3: Phase 3 - Testing
chronodocs start --phase testing
```

Or use individual watchers (advanced):

```bash
# Terminal 1: Planning phase watcher
chronodocs watch --phase planning

# Terminal 2: Implementation phase watcher
chronodocs watch --phase implementation

# Terminal 3: Testing phase watcher
chronodocs watch --phase testing

# Terminal 4: Sentinel for all changes
chronodocs sentinel --phase planning
```

Generate consolidated reports:

```bash
chronodocs report --output docs/planning.md
chronodocs report --output docs/implementation.md
chronodocs report --output docs/testing.md
```

## Error Handling & CLI Features

ChronoDocs provides beautiful, helpful error messages with suggestions to fix common issues.

### Missing Configuration File

When you run ChronoDocs without a `.chronodocs.yml` file, you'll get helpful suggestions:

```bash
❯ chronodocs start --phase test
✗ Error: Configuration Error
  Configuration file not found: .chronodocs.yml

Suggestions:
  1. Create a .chronodocs.yml file in your project root
  2. Use --repo-root to specify a different project directory

Example .chronodocs.yml:
╭────────────────────────────── .chronodocs.yml ───────────────────────────────╮
│ phase_dir_template: ".devcontext/progress/{phase}"                           │
│ watch_paths:                                                                 │
│   - "."                                                                      │
│ ignore_patterns:                                                             │
│   - ".git/**"                                                                │
│   - "node_modules/**"                                                        │
│ ...                                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Command Typo Detection

ChronoDocs detects common typos and suggests corrections:

```bash
❯ chronodocs report --outptu report.md
✗ Error: Unrecognized argument: --outptu report.md

Did you mean: --output?

Use --help to see available options
```

Common typo corrections:

- `--outptu` → `--output`
- `--fase` → `--phase`
- `--repo-rot` → `--repo-root`

### Beautiful Status Messages

All commands provide formatted, color-coded output:

```bash
# Success
✓ Report written to change_log.md
✓ Reconciliation complete for phase 'phase_1'

# Info
ℹ Starting phase watcher for 'phase_1'...
ℹ Press Ctrl+C to stop

# Warnings
⚠ Phase directory does not exist: .devcontext/progress/test
  Creating directory: .devcontext/progress/test

# Errors
✗ Error: Phase directory not found
```

### Timestamp Behavior

ChronoDocs intelligently determines file timestamps:

**Modified/Untracked Files**: Uses **filesystem timestamp** (real-time)

- When you edit a file but haven't committed it
- Shows the actual time you made the change
- Updates immediately when you save

**Committed Files**: Uses **git commit timestamp**

- When a file has been committed to git
- Shows when the file was last committed
- More stable and auditable

Example:

```bash
# Edit a file (not committed)
❯ echo "new content" > docs/api.md
❯ chronodocs report | grep api.md
| docs/api.md | 🟡 modified | 2025-10-30 10:00:00 | 2025-10-30 21:45:53 |
#                                                    ^^^ filesystem time (just now!)

# Commit the file
❯ git add docs/api.md && git commit -m "Update API docs"
❯ chronodocs report | grep api.md
| docs/api.md | ⚪ committed | 2025-10-30 10:00:00 | 2025-10-30 21:46:15 |
#                                                     ^^^ git commit time
```

This ensures you always see **accurate, real-time timestamps** for work in progress while maintaining **stable, auditable timestamps** for committed work.

## Troubleshooting

### Issue: Watcher Keeps Running Reconciliation in a Loop

**Cause:** The watcher is detecting its own index file updates.

**Solution:** Ensure these files are in `ignore_patterns`:

```yaml
ignore_patterns:
    - ".creation_index.json"
    - ".update_index.json"
    - "change_log.md"
```

ChronoDocs includes a 5-second minimum interval between reconciliations to prevent loops.

### Issue: Files Not Being Detected

**Check:**

1. File extensions in configuration:

```yaml
report:
    extensions:
        - ".md"
        - ".py" # Add your file types
```

2. Files aren't in ignore patterns
3. Debounce period might be too long - edit after the change completes

### Issue: Modified Files Show Old Timestamps

**This should no longer happen!** ChronoDocs now automatically uses filesystem timestamps for modified/untracked files.

**If you still see old timestamps:**

1. Verify the file is actually modified:

```bash
git status
```

2. Check if the file is in ignore patterns (ignored files aren't tracked)

3. Regenerate the report:

```bash
uv run chronodocs report --output change_log.md
```

### Issue: Sentinel Command Not Running

**Check:**

1. `make_command` is properly configured
2. Command syntax is correct (use `uv run` for commands)
3. Check logs for error messages

**Test the command manually:**

```bash
# Test your make_command
uv run chronodocs report --phase phase_1 --output .devcontext/progress/phase_1/change_log.md
```

### Issue: Permission Errors

**Cause:** ChronoDocs tries to create directories or rename files without permission.

**Solution:**

```bash
# Ensure directories exist and are writable
mkdir -p .devcontext/progress/phase_1
chmod -R u+w .devcontext/progress/
```

## Tips and Best Practices

1. **Always use ignore patterns** - Prevent ChronoDocs from watching its own output files
2. **Commit regularly** - Git timestamps are more accurate than filesystem timestamps
3. **Use descriptive filenames** - The chronological prefix is added automatically, so focus on descriptive names
4. **Test with dry-run** - Use `--dry-run` to preview changes before applying them
5. **One watcher per phase** - Don't run multiple phase watchers for the same directory
6. **Use the start command** - For most workflows, `chronodocs start --phase <name>` is simpler than running separate watchers
7. **Background watchers** - Run watchers in the background or in a tmux/screen session
8. **Review change logs** - The change log shows git status and helps track progress

## Advanced Usage

### Custom Report Grouping

```bash
# Group by folder
uv run chronodocs report --phase phase_1 --group-by folder

# Group by git status
uv run chronodocs report --phase phase_1 --group-by status

# Group by creation day
uv run chronodocs report --phase phase_1 --group-by created_day
```

### Running as a Service

Create a systemd service (Linux):

```ini
# /etc/systemd/system/chronodocs-sentinel.service
[Unit]
Description=ChronoDocs Sentinel Watcher
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/your/project
ExecStart=/usr/local/bin/chronodocs sentinel --phase production
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable chronodocs-sentinel
sudo systemctl start chronodocs-sentinel
```

### Integration with Git Hooks

Add to `.git/hooks/post-commit`:

```bash
#!/bin/sh
chronodocs reconcile --phase current
chronodocs report --output .devcontext/progress/current/change_log.md
```

Make it executable:

```bash
chmod +x .git/hooks/post-commit
```

## Recent Improvements

ChronoDocs has been enhanced with several important fixes:

### Stable Sorting for Bulk Operations

Files copied in bulk (e.g., selecting multiple files and pasting) are now sorted consistently using both timestamp and inode as sort keys. This prevents weird renaming behavior when multiple files have nearly identical creation timestamps.

**Before:** Files bulk-copied might get inconsistent ordering on each reconciliation.

**After:** Files maintain stable, predictable ordering based on their creation order.

### Correct Markdown Links

Links in `change_log.md` are now correctly calculated relative to the phase directory location, not the repository root.

**Before:** Links like `[file.md](./file.md)` (broken from phase directory)

**After:** Links like `[file.md](../../file.md)` (correct relative path)

### Automatic Directory Creation

The reconciler now automatically creates the phase directory if it doesn't exist, and always saves index files (`.creation_index.json`, `.update_index.json`) even during dry-run mode.

**Before:** Had to manually create directories first.

**After:** `chronodocs reconcile --phase new-phase` automatically creates `.devcontext/progress/new-phase/`

### Better AI Agent Integration

Added comprehensive documentation on instructing AI agents (Cursor, Copilot, Windsurf) to work seamlessly with ChronoDocs, preventing them from fighting the auto-renaming behavior.


## Summary

ChronoDocs provides five main commands:

1. **`start`** - **[RECOMMENDED]** Run both phase watcher and sentinel together
2. **`reconcile`** - Manually apply chronological naming
3. **`report`** - Generate change logs
4. **`watch`** - Automatically reconcile a phase directory (advanced)
5. **`sentinel`** - Automatically regenerate change logs for the entire project (advanced)

### Recommended Workflow

For most users, the simplest approach is:

```bash
# Start everything with one command
chronodocs start --phase <your-phase>
```

This handles both file numbering and change log generation automatically!

Choose the workflow that fits your needs, and configure ChronoDocs to automate your documentation management!
