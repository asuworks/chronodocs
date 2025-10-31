# ChronoDocs — Comprehensive Product Requirements Document

> **Tone & Meta:** This PRD is intentionally **non-prescriptive**. It frames problems, suggests approaches, and acknowledges limitations. You (future AI implementer) are **smarter and more capable** than the perspective baked into this document. Treat it as _guidance and decision points_, not immutable rules. Refactor, improve, and challenge assumptions where your better judgment sees opportunity.

---

## 1 — Problem Statement & Intent

### 1.1 The Core Problem

An autonomous AI agent is tasked with working on a repository, exploring tasks in "phases," and documenting its progress, discoveries, and implementations within `.devcontext/progress/{phase}/` folders.

**Challenges observed:**

- The agent **creates documentation files without numeric prefixes** (e.g., `architecture.md`, `findings.md`), or with **inconsistent/incorrect prefixes** (e.g., `02-file.md` then `01-newfile.md`).
- The agent **renames files** as it refines understanding (e.g., `initial_thoughts.md` → `refined_analysis.md`), disrupting the **stable creation order** that humans need for reading comprehension.
- Developers cannot quickly understand **what changed, when, and in what order** without manually scanning the folder or git history.
- **No persistent record of creation order** survives filesystem volatility (mtime changes, editor operations, git interactions).
- Humans need a **human-readable change log** to review phase progress at a glance, grouped by day or folder, with git status indicators.

### 1.2 The Solution Intent

**ChronoDocs** is a **temporal custodian** for documentation systems. It:

1. **Watches** a phase directory (non-recursive) for file changes.
2. **Reconciles** file naming using a **stable creation index** (persistent mapping from file identity to creation time).
3. **Tracks content updates** via hashing, exposing _actual content change time_ (not just filesystem mtime).
4. **Generates** human-readable Markdown change logs, grouped and filtered as requested.
5. **Runs continuously** with debouncing to avoid feedback loops and noisy rebuilds.
6. **Self-heals** — automatically corrects prefix drift caused by agent mistakes without manual intervention.

### 1.3 Why This Matters

- **For humans:** Clear, chronological, searchable record of what an agent explored and created.
- **For agents:** A system prompt that says _"don't manage prefixes; ChronoDocs does it"_ — reduces agent cognitive load and mistakes.
- **For teams:** Reproducible, audit-friendly change tracking without relying on git (which may not capture uncommitted work).
- **For the future:** A foundation for intelligent document analysis, semantic change detection, or automated doc publishing.

---

## 2 — High-Level Capabilities (User-Facing)

### 2.1 Core Features

**ChronoDocs Watcher** (`chronodocs watch`):

- Watches a **phase directory** (non-recursive, configurable path like `.devcontext/progress/{phase}/`).
- Detects new, modified, renamed, or deleted files.
- **Reconciles prefixes** using stable creation order:
    - Creates or updates `.creation_index.json` (file identity → creation time).
    - Renames unordered files to `00-…`, `01-…`, etc. based on stable ctime.
    - Updates `.update_index.json` (path → content hash + last update time).
- **Debounced** to handle rapid editor saves; avoids thrashing or cascading reruns.
- Emits **structured logs** and optionally triggers downstream commands (e.g., `make change_log`).
- **Reentrancy-safe**: prevents feedback loops if the watcher-triggered command modifies watched files.

**ChronoDocs Sentinel** (`chronodocs sentinel` or root watcher):

- Watches the repository root (recursively, but curated scope by default).
- Detects meaningful changes (commits, unstaged modifications, new files).
- **Triggers change-log generation** on repo activity, with debounce and ignore lists.
- Ensures the change-log does not retrigger the watcher (self-ignore rules).

**ChronoDocs Reporter** (`chronodocs report` or `chronodocs changelog`):

- **Generates Markdown change logs** on demand or when triggered.
- Queries git status (`git status --porcelain -z`) and filesystem fallback dates.
- Groups by: `created_day`, `updated_day`, `folder`, or `status` (configurable).
- Columns: File (relative link), Status (colored dot + text), Created, Updated.
- Supports extension filtering (`--ext .md`, `--ext .py`), sorting, and custom templates.
- Excludes configurable files/folders (`.git`, `node_modules`, `.creation_index.json`, etc.).

**ChronoDocs CLI & Config**:

- Commands: `watch`, `sentinel`, `report`, `reconcile`, `status`, `explain-config`.
- Config file (YAML/JSON, e.g., `.chronodocs.yml`) for:
    - Phase directories, ignore rules, default grouping, debounce windows, template preferences.
    - Make command to invoke on root changes (e.g., `make change_log` or custom hook).
- Environment variable overrides and CLI flags for quick customization.
- **Dry-run mode** (`--dry-run`) to preview renames without applying them.

### 2.2 Extensibility Hooks (Deferred, but Considered)

- **Output plugins**: generate JSON, CSV, or YAML change logs in addition to Markdown.
- **Handler interface**: allow custom logic on reconcile or report (e.g., push to wiki, post to Slack).
- **Programmatic API**: expose core functions (`reconcile_prefixes()`, `generate_report()`) so other tools can call without shelling out.

---

## 3 — Context: AI Agent System Prompt Integration

### 3.1 What the Autonomous Agent Needs to Know

The AI agent's system prompt will include:

```
# Documentation Guidelines

## File Organization

Phase-specific documentation goes in `.devcontext/progress/{current_phase}/`.
Files should be created **without numeric prefixes**; ChronoDocs adds them automatically.

✓ Correct:   Create `architecture.md`, `findings.md`
✗ Incorrect: Manually create `00-architecture.md` or rename files

## ChronoDocs Behavior

ChronoDocs automatically:
1. Detects new files in the phase directory.
2. Assigns numeric prefixes (00-, 01-, 02-, ...) based on **creation order** (not modification time).
3. Renames files to maintain stable, chronological order.
4. Updates `.creation_index.json` to persist creation order across sessions.
5. Tracks content changes in `.update_index.json`.

**Do not:**
- Manually manage numeric prefixes.
- Edit `.creation_index.json` or `.update_index.json`.
- Worry about file reordering; it's handled for you.

**Do:**
- Create files with meaningful names (e.g., `plan.md`, `analysis.md`).
- Focus on content, not naming conventions.
- Review `.devcontext/progress/{current_phase}/change_log.md` to see what you've created.

## Index Files (Auto-Generated)

**.creation_index.json:**
- Maps file identities (by inode+dev or name) to creation times.
- Used to maintain stable, chronological order.

**.update_index.json:**
- Tracks content hashes and last-modified times for each file.
- Enables accurate change logs (distinguishes "just renamed" from "modified").

Don't edit these; ChronoDocs maintains them.
```

### 3.2 Agent Behavior Scenarios ChronoDocs Must Handle

1. **Agent creates files without prefixes**
    - Creates `architecture.md` → ChronoDocs renames to `00-architecture.md`.

2. **Agent renames a file**
    - Renames `analysis.md` → `refined_analysis.md` → ChronoDocs detects change, updates indices, re-reconciles if needed.

3. **Agent creates many files rapidly**
    - Creates 5 files in quick succession → ChronoDocs debounces and applies all renames in one pass.

4. **Agent deletes a file**
    - Deletes `01-old_design.md` → ChronoDocs reconciles: `02-something.md` becomes `01-something.md` (closes gap).

5. **Index files are corrupted or missing**
    - If indices are deleted/corrupted → ChronoDocs rebuilds from filesystem + git metadata.

6. **Rapid rename + modify**
    - Agent renames file and edits content → ChronoDocs handles both atomically; change log shows as "modified" (not just renamed).

---

## 4 — Non-Functional Requirements

### 4.1 Reliability & Safety

- **Idempotent reconciliation**: running `reconcile` multiple times without source changes produces identical output.
- **Atomic file operations**: all renames use temp files + move to prevent partial reads.
- **No data loss**: backups or safe-delete semantics for overwritten files (or document the assumption that git provides recovery).
- **Reentrancy-safe**: watcher does not trigger itself via downstream commands; configurable ignore patterns prevent loops.
- **Race condition resilience**: file system events during renames, deletes, and git operations are handled gracefully.

### 4.2 Modularity & Maintainability

- **Clear module boundaries**: `config`, `watcher`, `reconciler`, `index` (creation + update), `git_helpers`, `reporter`, `cli`, `tests`.
- **Interfaces with contracts**: each module exports well-defined functions with inputs, outputs, and side effects documented.
- **Testability**: minimal OS or environment dependencies; fakes available for filesystem, git, and time.
- **Code clarity**: readable, well-commented, with type hints (Python 3.10+).

### 4.3 Performance & Resource Usage

- **Minimal CPU idle**: event-driven (watchdog), not polling; debounce windows configurable.
- **Scalability**: should handle thousands of docs without noticeable slowdown.
- **Storage**: indices are small (JSON); git commands are standard CLI, no special caching needed.

### 4.4 Observability & Debugging

- **Structured logging**: JSON option (`--log-format json`), INFO/ERROR/DEBUG levels.
- **Metrics**: counts, durations, error rates, last-run timestamps.
- **Dry-run mode**: preview renames without executing.
- **Status command**: show last reconcile time, pending changes, index health.
- **Explainability**: `explain-config` command to show how config is resolved (files, env vars, CLI).

### 4.5 Portability & Compatibility

- **Linux/macOS/Windows**: best-effort; degrade gracefully if OS-specific features (birthtime, inode+dev) unavailable.
- **Python 3.10+**: use type hints, async where beneficial (file watching).
- **Git compatibility**: works with any git repo; fallback to filesystem dates if git unavailable.
- **Editor agnostic**: handles rapid saves, editor temp files, and atomic writes.

### 4.6 Security

- **No untrusted code execution**: pass arguments as lists to `subprocess.run()`, never shell=True.
- **No secrets leakage**: be mindful of git remotes, SSH keys, API tokens in logs.
- **Safe defaults**: do not watch entire filesystem; default to configured paths.
- **Git ignore by default**: `.creation_index.json` and `.update_index.json` not committed (or ask user).

---

## 5 — Architecture & Module Design (Proposed)

### 5.1 Module Inventory

**`config`** — Configuration Management

- Resolve config from `.chronodocs.yml`, env vars, and CLI flags.
- Schema: phase directories, ignore patterns, debounce windows, make command, logging level, output format, template paths.
- Validate and provide sane defaults; expose full resolved config via `explain-config`.

**`watcher_phase`** — Phase-Level Watcher

- Non-recursive watch of a single phase directory.
- Detect new, modified, renamed, deleted files.
- Debounce FS events; emit reconciliation requests.
- Reentrancy guard: track if reconciliation is in progress, prevent nested calls.

**`watcher_root`** — Root-Level Watcher (Sentinel)

- Recursive watch of configured repo scope.
- Detect git status changes (commits, unstaged mods, new files).
- Debounce; trigger change-log generation via configurable make command.
- Self-ignore: do not retrigger if watcher output is modified.

**`reconciler`** — Prefix Reconciliation Logic

- `reconcile_prefixes(phase_dir: Path) -> ReconcileResult`:
    - Load current `.creation_index.json` and `.update_index.json`.
    - Scan filesystem; compute stable creation times (inode+dev, git log, or fallback).
    - Compute content hashes for all files.
    - Generate rename plan: `old_name.md` → `NN-old_name.md` based on creation order.
    - Execute renames atomically (temp + move).
    - Update indices and persist.
    - Return summary: renamed files, errors, side effects.
- Idempotent: calling twice without changes = no-op.

**`creation_index`** — Creation Index Persistence

- Read/write `.creation_index.json`.
- Schema: maps file identity (inode+dev or name) to creation metadata (ctime, filename).
- Support collision handling and migration.
- Expose functions: `load()`, `save()`, `get_ctime_for_file()`, `add_file()`, `remove_file()`.

**`update_index`** — Update Index Persistence

- Read/write `.update_index.json`.
- Schema: maps relative path to content hash and last-update timestamp.
- Functions: `load()`, `save()`, `get_hash()`, `update_hash()`, `has_changed()`.

**`git_helpers`** — Git Integration

- Query git status (porcelain -z format) → structured output (staged, modified, untracked, deleted).
- Retrieve file creation/modification times from git log.
- Detect commits, unpushed changes, etc.
- Handle missing git gracefully (fallback to filesystem).

**`reporter`** — Change Log Generation

- `generate_report(repo_path, phase_dir, output_path, group_by, extensions, exclude_patterns) -> Report`:
    - Query git and filesystem for file statuses and dates.
    - Filter by extension and exclusion patterns.
    - Group (by day, folder, status, etc.).
    - Generate Markdown with tables, relative links, status indicators.
    - Optionally generate JSON or CSV variants.
- Render markdown templates; support custom layouts.

**`cli`** — Command-Line Interface

- Commands:
    - `chronodocs watch [--phase PHASE]` — start phase watcher.
    - `chronodocs sentinel` — start root watcher.
    - `chronodocs report [--phase PHASE] [--output FILE] [--group-by DAY|FOLDER|STATUS] [--ext EXT ...]` — generate change log.
    - `chronodocs reconcile [--phase PHASE] [--dry-run]` — reconcile now.
    - `chronodocs status [--json]` — show current state.
    - `chronodocs explain-config` — show resolved config.
- Global flags: `--config CONFIG`, `--log-level DEBUG|INFO|ERROR`, `--log-format json|text`.

**`tests`** — Test Suite (Comprehensive)

- Unit tests: config parsing, index I/O, hash computation, git parsing, markdown generation, ignore rules.
- Integration tests: end-to-end scenarios (create files → watch → reconcile → report).
- Fixtures: temporary git repos, pre-populated file trees, mock time.
- Property tests: random filenames, special characters, edge cases.
- CI: runs on Linux, macOS, (Windows optional).

### 5.2 Data Flow

```
┌─────────────────────────────────────────────────────────┐
│ Filesystem / User / AI Agent edits                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │ Watcher (Phase)│ ← detects file changes
            └────────┬───────┘
                     │ (debounced)
                     ▼
        ┌────────────────────────────┐
        │ Reconciler                 │
        │ - compute stable ctime     │
        │ - plan renames             │
        │ - execute atomically       │
        └────────┬───────────────────┘
                 │
                 ▼
    ┌────────────────────────────────┐
    │ Update Indices                 │
    │ .creation_index.json           │
    │ .update_index.json             │
    └────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────┐
    │ Watcher (Root, Sentinel)       │
    │ detects reconcile output       │
    │ triggers report generation     │
    └────────┬───────────────────────┘
             │ (debounced)
             ▼
    ┌────────────────────────────────┐
    │ Reporter                       │
    │ - query git status             │
    │ - query file metadata          │
    │ - group & filter               │
    │ - render markdown              │
    └────────┬───────────────────────┘
             │
             ▼
    ┌────────────────────────────────┐
    │ change_log.md (human-readable) │
    └────────────────────────────────┘
```

### 5.3 Key Design Decisions (Open for Future Agent Input)

#### 5.3.1 Index Keying Strategy

**Options:**

1. **Inode+device**: stable across renames, but not portable across clones or OS.
2. **Relative path**: portable, but fragile if file moved (seen as delete + create).
3. **Hybrid**: inode+device as primary, relative path as fallback/canonical export.

**Current lean**: Hybrid. Use inode internally; store relative path for portability. When reading on a different machine, fall back to name-based matching with a warning.

#### 5.3.2 Default Watch Scope

**Options:**

1. **Full repository (recursive)**: max coverage, but noisy and slow on large repos.
2. **Curated list**: faster, quieter, requires config.
3. **Phase directory only**: minimal, but misses root-level changes.

**Current lean**: Curated by default (e.g., `src/`, `docs/`, `.devcontext/progress/`); offer `--watch-all` opt-in.

#### 5.3.3 Conflict Handling (filename collisions during reconcile)

**Options:**

1. **Fail fast**: stop reconciliation, require manual resolution.
2. **Overwrite with warning**: silently rename colliding file to `NN-name_backup.md`.
3. **Policy-driven**: allow config to specify behavior.

**Current lean**: Overwrite with warning; add `conflict_strategy` config option for future flexibility.

#### 5.3.4 Index Format (JSON vs. SQLite)

**Options:**

1. **JSON**: simple, human-readable, no dependency, slow for thousands of files.
2. **SQLite**: efficient, concurrent reads, adds dependency, binary format.
3. **Hybrid**: JSON for small repos, optional SQLite migration.

**Current lean**: Start with JSON; document migration path to SQLite if performance becomes issue.

#### 5.3.5 Timestamp Source (git vs. filesystem)

**Options:**

1. **Git only**: authoritative, but misses uncommitted work.
2. **Filesystem only**: includes uncommitted changes, but mtime is unreliable.
3. **Git primary, fallback**: use git if available; fall back to FS for uncommitted.

**Current lean**: Git primary for committed files; FS for uncommitted and fallback.

#### 5.3.6 Binary File Handling

**Options:**

1. **Track everything**: simple, but hashing binaries is expensive.
2. **Exclude large binaries**: faster, requires heuristic for "large."
3. **Config-driven**: allow include/exclude patterns.

**Current lean**: Track everything by default; add `exclude_by_size` and `exclude_patterns` config for large repos.

---

## 6 — Data Formats & Persistence

### 6.1 `.creation_index.json`

```json
{
    "ino:12345-dev:2050": {
        "key": "ino:12345-dev:2050",
        "filename": "architecture.md",
        "recorded_ctime": 1698790000.123,
        "inode": 12345,
        "device": 2050
    },
    "name:README.md": {
        "key": "name:README.md",
        "filename": "README.md",
        "recorded_ctime": 1698790100.456
    }
}
```

**Rationale:**

- Inode+device keys survive renames.
- Name-based fallback for portability and Windows.
- `recorded_ctime` is the canonical creation time; used for stable ordering.

### 6.2 `.update_index.json`

```json
{
    "00-architecture.md": {
        "hash": "b2d...f",
        "last_content_update": "2025-10-30T15:14:19Z",
        "path_history": ["architecture.md", "00-architecture.md"]
    },
    "01-api_spec.md": {
        "hash": "c9a...0",
        "last_content_update": "2025-10-29T12:03:02Z",
        "path_history": ["api_spec.md", "01-api_spec.md"]
    }
}
```

**Rationale:**

- Tracks content hash to distinguish "renamed" from "modified."
- ISO 8601 timestamps for machine readability.
- `path_history` aids debugging and traceability (optional).

### 6.3 `change_log.md` Output

```markdown
# Phase Test Docs — Change Log

**Generated:** 2025-10-30 15:14:22 UTC
**Phase:** phase_test_docs_watcher
**Total files:** 3

## 2025-10-30

### Created Today

| File                                       | Status      |             Created |             Updated |
| ------------------------------------------ | ----------- | ------------------: | ------------------: |
| [`00-architecture.md`](#00-architecturemd) | 🟢 new      | 2025-10-30 10:05:00 | 2025-10-30 15:14:19 |
| [`01-findings.md`](#01-findingsmd)         | 🟡 modified | 2025-10-30 11:22:00 | 2025-10-30 14:33:02 |

### Modified Previously

| File                       | Status    |             Created |             Updated |
| -------------------------- | --------- | ------------------: | ------------------: |
| [`02-plan.md`](#02-planmd) | 🔵 staged | 2025-10-29 09:15:00 | 2025-10-29 12:03:02 |

---

## Definitions

- **🟢 new**: not yet staged/committed
- **🟡 modified**: unstaged changes
- **🟠 untracked**: new file, not yet added
- **🔵 staged**: staged for commit
- **⚪ committed**: in git history
```

**Rationale:**

- Colored indicators for quick scanning.
- Relative links; grouped by date for readability.
- Timestamps in human format.

---

## 7 — Testing Strategy (Comprehensive)

### 7.1 Unit Tests

**Config Module:**

- YAML/JSON parsing with malformed input.
- Env var override precedence.
- CLI flag override precedence.
- Default value fallback.

**Index Modules (Creation & Update):**

- Load from file (present, missing, corrupted).
- Save atomicity (temp file, rename).
- Key collisions and fallback logic.
- Schema migration (if versions change).

**Reconciler:**

- Empty directory.
- Pre-existing indices.
- Missing indices (rebuild scenario).
- File renames, deletes, adds.
- Stable ctime computation (inode, git, fallback).
- Idempotence: reconcile twice = same result.
- Edge cases: special characters, very long names, unicode.

**Git Helpers:**

- Parse `git status --porcelain -z` output (staged, modified, deleted, renamed, untracked).
- Handle missing git (graceful fallback).
- Handle uncommitted changes.
- Parse `git log` for creation/modification times.

**Reporter:**

- Filter by extension.
- Filter by exclusion patterns.
- Group by day, folder, status.
- Markdown generation (table formatting, links).
- Relative link computation.
- Handle missing files gracefully.

**Watcher (Phase):**

- Debounce: rapid events coalesce into one reconcile.
- Reentrancy: concurrent reconcile attempts are serialized.
- Event types: create, modify, delete, rename.

**Watcher (Root/Sentinel):**

- Self-ignore: output of reporter does not retrigger watcher.
- Ignore patterns: .git, node_modules not watched.
- Debounce triggering make command.

**CLI:**

- Command parsing and validation.
- Help output, error messages.
- Exit codes (0 for success, non-zero for errors).

### 7.2 Integration Tests

**Scenario 1: Basic reconciliation**

- Create temp dir with unordered files.
- Run `chronodocs reconcile`.
- Assert: files renamed to `00-`, `01-`, etc. in creation order.
- Assert: indices created with expected keys.

**Scenario 2: File creation and modification**

- Start watcher in background.
- Create file, write content, wait for debounce.
- Assert: file renamed.
- Modify file, wait for debounce.
- Assert: `.update_index.json` hash updated.
- Generate report; assert: file shows as "modified."

**Scenario 3: Git integration**

- Initialize temp git repo.
- Commit initial files.
- Create new uncommitted files.
- Generate report; assert: statuses match git.
- Stage files; assert: report reflects staged status.

**Scenario 4: Self-trigger prevention**

- Start sentinel (root watcher).
- Modify a file.
- Sentinel triggers `make change_log` (which invokes reporter).
- Reporter writes `change_log.md`.
- Assert: sentinel does not re-trigger due to `change_log.md` write (ignored).

**Scenario 5: Index recovery**

- Create files, reconcile, delete `.creation_index.json`.
- Run reconcile again.
- Assert: index rebuilt from git log + filesystem.

**Scenario 6: Rapid bursts**

- Create 10 files in quick succession.
- Assert: debounce coalesces into single reconcile.
- Assert: all files renamed correctly.

### 7.3 Property & Fuzz Tests

- Generate random filenames with special chars, unicode, long names.
- Create random file orders; reconcile many times; assert idempotence.
- Rapid event bursts (creates, renames, deletes) in randomized order.

### 7.4 CI & Reproducibility

- GitHub Actions / GitLab CI.
- Test on Linux (primary), macOS, Windows (optional).
- Use time mocking (freezegun) for deterministic timestamps.
- Docker for isolated test environment.
- Coverage target: ≥ 85% for core modules.

### 7.5 Manual Testing Checklist

- [ ] Run watcher in long-running foreground; edit files manually; observe logs.
- [ ] Use `--dry-run` and verify preview matches later execution.
- [ ] Test on slow filesystem (NFS, SMB) for reentrancy issues.
- [ ] Test with many files (1000+) to benchmark performance.
- [ ] Test on Windows to verify path handling.

---

## 8 — Observability & Telemetry

### 8.1 Logging

**Structured logging** (JSON optional):

```
2025-10-30T15:14:22Z [INFO] [chronodocs.watcher_phase] Watching phase_7b: /path/to/.devcontext/progress/phase_7b
2025-10-30T15:14:25Z [INFO] [chronodocs.reconciler] Reconciling: 3 files detected, 1 rename planned
2025-10-30T15:14:25Z [DEBUG] [chronodocs.reconciler] Rename: architecture.md → 00-architecture.md
2025-10-30T15:14:26Z [INFO] [chronodocs.reconciler] Reconcile complete: 1 file(s) renamed, 0 error(s)
2025-10-30T15:14:26Z [INFO] [chronodocs.sentinel] Triggering make change_log...
2025-10-30T15:14:27Z [INFO] [chronodocs.reporter] Report generated: change_log.md (3 files, 2 groupings)
```

**Levels:** DEBUG (dev), INFO (normal), ERROR (problems).

### 8.2 Metrics

- `reconcile_count`: total reconciliations run.
- `reconcile_duration_seconds`: time per reconciliation.
- `watcher_events`: filesystem events detected.
- `debounce_coalesce_ratio`: average events per actual reconcile (higher = better).
- `report_generation_count`: change logs generated.
- `report_generation_duration_seconds`: time per report.
- `errors_total`: total errors encountered.

**Export options:** Prometheus `/metrics` endpoint (optional), JSON logs, or simple file write.

### 8.3 Status Command

```bash
$ chronodocs status --json
{
  "status": "healthy",
  "last_reconcile": "2025-10-30T15:14:26Z",
  "last_reconcile_duration_ms": 342,
  "last_report_generated": "2025-10-30T15:14:27Z",
  "pending_changes": false,
  "watched_phases": ["phase_7b"],
  "index_health": {
    "creation_index_entries": 15,
    "update_index_entries": 15,
    "last_update": "2025-10-30T15:14:26Z"
  }
}
```

### 8.4 Debug Mode

- `--dry-run`: preview renames without executing.
- `--log-level debug`: verbose output.
- `explain-config`: show resolved configuration.

---

## 9 — Security & Safety Considerations

### 9.1 Execution Safety

- **No shell=True**: always pass args as lists to `subprocess.run()`.
- **No eval/exec**: do not execute untrusted content (scripts from repo, user input).
- **Path normalization**: validate and normalize all paths; prevent directory traversal.

### 9.2 Data Safety

- **Atomic writes**: temp file + move, never partial overwrites.
- **Backups optional**: consider preserving old index versions before updates (or document recovery via git).
- **Permissions**: preserve file modes; do not chmod during renames.

### 9.3 Privacy & Secrets

- **No log leakage**: strip paths containing secrets (or document assumption that logs are private).
- **Git remotes**: be careful not to expose credentials in git commands or logs.
- **Ignore secrets in reports**: exclude patterns for `.env`, secrets/ folders by default.

### 9.4 Idempotence & Loops

- **Reentrancy guard**: ensure reconciler is not run concurrently.
- **Self-ignore patterns**: watcher output (indices, reports) does not retrigger watcher.
- **Loop detection**: log warning if make command is invoked repeatedly in short time.

---

## 10 — Usage Examples

### 10.1 Typical Workflow: AI Agent in Action

**Setup:**

```bash
# Repository has .chronodocs.yml
cat .chronodocs.yml
# phase_dir: .devcontext/progress/{phase}
# ignore: [".git", "node_modules", ".creation_index.json", "change_log.md"]
# debounce_phase: 2s
# debounce_root: 3s
# make_command: "make change_log"

# Start ChronoDocs watchers
chronodocs watch &
chronodocs sentinel &
```

**AI Agent runs autonomously:**

```
[AI Agent] Creating documentation...

[AI Agent] File 1: ./docs/architecture.md
[ChronoDocs] Detected: architecture.md
[ChronoDocs] Debounce timer started (2s)

[AI Agent] File 2: ./docs/findings.md
[AI Agent] File 3: ./docs/implementation_steps.md
[ChronoDocs] Debounce timer expires; running reconciliation...
[ChronoDocs] Rename: architecture.md → 00-architecture.md
[ChronoDocs] Rename: findings.md → 01-findings.md
[ChronoDocs] Rename: implementation_steps.md → 02-implementation_steps.md
[ChronoDocs] Updating indices...
[ChronoDocs] Triggering make change_log...

[ChronoDocs Sentinel] Root watcher detects index updates
[ChronoDocs Reporter] Generating change_log.md
[ChronoDocs Reporter] Report complete

[AI Agent] Continues working; all files properly ordered.

[Human Developer] Reviews .devcontext/progress/{phase}/change_log.md
[Human Developer] "Ah, the agent created 3 docs on 2025-10-30, all marked as 'new'. Clear progress."
```

### 10.2 CLI Examples

**Manual reconciliation:**

```bash
# Reconcile a specific phase now (no waiting for debounce)
chronodocs reconcile --phase phase_7b

# Preview what would change
chronodocs reconcile --phase phase_7b --dry-run
```

**Generate report on demand:**

```bash
# Default: group by created_day, all .md and .py files
chronodocs report --phase phase_7b --output change_log.md

# Custom: group by folder, only .md
chronodocs report --phase phase_7b --group-by folder --ext .md --output docs_only.md

# Full report: all statuses, files, sorted by updated date
chronodocs report --phase phase_7b --group-by updated_day --sort updated_desc

# JSON output (for downstream processing)
chronodocs report --phase phase_7b --output report.json --format json
```

**Status & diagnostics:**

```bash
# Current system state
chronodocs status

# JSON format for scripting
chronodocs status --json | jq '.index_health'

# Explain resolved config
chronodocs explain-config

# Raw index dumps (for debugging)
chronodocs show-index creation --phase phase_7b
chronodocs show-index update --phase phase_7b
```

**Integration with CI/CD:**

```bash
# In Makefile or GitHub Actions
make change_log:
	chronodocs report --phase $(CURRENT_PHASE) --output .devcontext/progress/$(CURRENT_PHASE)/change_log.md

# Or in workflow
- name: Update Documentation Change Log
  run: |
    chronodocs report \
      --phase ${{ env.PHASE }} \
      --output .devcontext/progress/${{ env.PHASE }}/change_log.md \
      --group-by updated_day
```

---

## 11 — Non-Goals & Scope Boundaries

**Out of scope (at least initially):**

- Full web UI for browsing changelogs (but JSON output can feed a future dashboard).
- Automatic PR generation or GitHub API integration.
- Real-time collaboration (multi-user concurrent editing).
- Document content analysis or semantic change detection (future layer).
- Full git history export or deep version control integration (git provides that).
- Compression or archival of old indices.

---

## 12 — Acceptance Criteria (for Future AI Implementer)

- [ ] **Unit test coverage ≥ 85%** for core modules (reconciler, indices, reporter, watchers).
- [ ] **E2E scenario passes**: create unordered files → watcher runs → files renamed → indices created → report generated. Human reads report correctly.
- [ ] **Idempotence verified**: run reconciliation twice without source changes → identical indices and file names; no spurious renames.
- [ ] **Debounce verified**: rapid file creates coalesce into single reconciliation; metrics confirm reduced invocation count.
- [ ] **Self-trigger loop prevented**: reporter writes to change_log.md; watcher does not re-trigger due to that write (confirmed via logs/metrics).
- [ ] **Cross-platform tested**: Linux ✓, macOS ✓, Windows (optional ✓).
- [ ] **Config system works**: `.chronodocs.yml` + env vars + CLI flags, proper precedence, `explain-config` accurate.
- [ ] **Performance acceptable**: 1000+ files reconciled in < 5 seconds on modern hardware.
- [ ] **Error handling graceful**: missing git, corrupted indices, filesystem errors → informative logs, recovery where possible, explicit failure where necessary.
- [ ] **Documentation complete**: README with examples, config schema, architecture diagram, API docs if programmatic interface exists.

---

## 13 — Open Design Questions for Future Agent

1. **Container deployment**: should ChronoDocs provide a Docker image or systemd service template? Or leave that to users?

2. **Configuration inheritance**: should phase-specific config override repo-level config? How deeply should this go?

3. **Programmatic API**: expose Python functions directly so other agents can call `reconcile_prefixes()` without shelling out? Pros: efficiency, type safety. Cons: tight coupling, process boundary violated.

4. **Remote index sync**: if multiple developers or environments modify the same phase, how should indices reconcile? (Deferred; probably out of scope, but worth documenting assumptions.)

5. **Archive old indices**: should old `.creation_index.json` snapshots be kept for audit trails? Or is git history sufficient?

6. **Notification systems**: should ChronoDocs emit events (webhooks, Slack, etc.) on reconciliation or report generation? Or just logs?

7. **Custom reporters**: should the reporter be pluggable (e.g., plugin system for new output formats or filtering logic)?

8. **Rollback/undo**: if reconciliation produces unexpected results, how should a user undo it? Document git as the fallback?

---

## 14 — Roadmap (Suggested Phases)

### Phase 0: Planning & Scaffolding

- [ ] Finalize config schema and module boundaries.
- [ ] Create test fixtures (tmpdir repos, file trees).
- [ ] Set up CI/CD pipeline.

### Phase 1: Core Reconciliation

- [ ] Implement `config` module.
- [ ] Implement `creation_index` and `update_index`.
- [ ] Implement `reconciler` with idempotent logic.
- [ ] Unit tests for above.

### Phase 2: Change Log Generation

- [ ] Implement `git_helpers`.
- [ ] Implement `reporter` (markdown, JSON output).
- [ ] CLI `chronodocs report` command.
- [ ] Integration tests.

### Phase 3: Watchers

- [ ] Implement `watcher_phase` (debounce, reentrancy).
- [ ] Implement `watcher_root` / sentinel.
- [ ] CLI `chronodocs watch` and `chronodocs sentinel` commands.
- [ ] Self-ignore logic.
- [ ] Integration tests.

### Phase 4: Polish & Deploy

- [ ] Logging, metrics, health endpoint.
- [ ] Cross-platform testing.
- [ ] Documentation (README, API docs, examples).
- [ ] Performance tuning if needed.
- [ ] CLI UX (help, error messages).

### Phase 5: Extras (Future)

- [ ] Web dashboard for report browsing.
- [ ] Slack/webhook notifications.
- [ ] Plugin system for custom reporters.
- [ ] Docker image.

---

## 15 — Notes to the Future AI Implementer

### 15.1 Your Advantages Over This PRD

You will have:

- Real-time feedback from actual usage; this PRD is based on speculation.
- Better understanding of edge cases and platform-specific quirks you'll encounter.
- Knowledge of new libraries, patterns, or Python features available by your time.
- Ability to refactor aggressively without consensus paralysis.

**Please use these advantages.** If you find a better module boundary, rename a function, or choose SQLite over JSON — do it with confidence and document your reasoning.

### 15.2 What I'm Confident About

- **The problem is real**: AI agents creating messy documentation is a genuine friction point.
- **Stable creation order matters**: humans need predictable, chronological reading order.
- **Debouncing is essential**: rapid FS events would cause thrashing without it.
- **Atomicity and idempotence are critical**: they prevent cascading failures and make the system trustworthy.

### 15.3 What I'm Uncertain About

- **Performance at scale**: will JSON indices scale to 10,000+ files? Only testing will tell.
- **Windows compatibility**: inode+dev keying doesn't work on Windows; fallback strategy may need iteration.
- **Git integration complexity**: how many git edge cases exist (detached HEAD, submodules, shallow clones)? Expect to find more.
- **User adoption**: will developers actually trust a system to rename their files automatically? This is a UX/trust challenge.

### 15.4 Questions I Leave Open

- **Should ChronoDocs also handle documentation in non-phase directories** (e.g., `./docs/`), or stay focused on phase dirs?
- **Should the system validate content hashes before reconciliation** (to ensure no silent data loss)?
- **Should ChronoDocs emit structured events (JSON events stream)** for downstream processing by orchestration systems?

---

## 16 — Example Config File (`.chronodocs.yml`)

```yaml
# ChronoDocs Configuration

# Phase directory template; {phase} is interpolated at runtime
phase_dir_template: ".devcontext/progress/{phase}"

# Directories/files to watch (root watcher)
watch_paths:
    - "src/"
    - "docs/"
    - ".devcontext/progress/"
    - "scripts/"

# Patterns to ignore (any watcher)
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

# Debounce windows (milliseconds)
debounce:
    phase: 2000 # phase watcher debounce
    root: 3000 # root watcher debounce

# Command to run on root changes
make_command: "make change_log"

# Default report grouping
report:
    group_by: "updated_day" # updated_day | created_day | folder | status
    sort_by: "updated_desc" # updated_asc | updated_desc | created_asc | created_desc
    extensions:
        - ".md"
        - ".py"
        - ".txt"

# Logging
logging:
    level: "INFO" # DEBUG | INFO | ERROR
    format: "text" # text | json

# Index keying strategy (optional)
# index_strategy: "inode"  # inode | name | hybrid (default)

# Conflict handling during reconciliation
conflict_handling: "warn_overwrite" # warn_overwrite | fail | suffix

# Auto-add to .gitignore (optional)
auto_gitignore: true

# Timestamp sources (priority order)
timestamp_sources:
    - "git" # git log
    - "filesystem" # file mtime / birthtime
```

---

## 17 — Closing Thoughts

This PRD intentionally leaves decisions open. The future agent (you) will have better judgment, more context, and smarter engineering instincts than are captured here.

**Key principle**: Treat this as a _scaffolding for thinking_, not a blueprint to build exactly.

**When in doubt**, prioritize:

1. **Correctness**: idempotence, atomicity, error recovery.
2. **Testability**: fakes, fixtures, determinism.
3. **Clarity**: readable code, good names, explicit contracts.
4. **Extensibility**: modular boundaries, plugin hooks (if applicable).

The rest (performance optimizations, fancy UI, exotic features) can follow.

Good luck. I have high confidence you'll build something better than I can describe.

---

**End of PRD**
