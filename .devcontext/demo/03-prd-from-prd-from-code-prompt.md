Here is a PRD:

```
# Product Requirements Document — Docs Watcher & Change-Log Agent (Agent → Future-Agent)

> **Tone / meta:** I am intentionally _not_ prescriptive. I will offer options, trade-offs, and suggestions while acknowledging my limitations and leaving clear decision points for a future, more capable AI implementer (you / future-me). The future agent should treat the items below as _guidance and constraints_ rather than immutable rules, and should improve or refactor them where appropriate.

---

## 1 — Purpose & Intent

**High-level intent:**
Provide an automated, robust, and maintainable system that:

- Keeps documentation files in a repository ordered and stable via _prefix-based ordering_ (e.g., `01-…`, `02-…`), with a stable creation ordering backed by persistent indices.
- Tracks actual content updates using content hashes and exposes _actual content update time_ for files.
- Generates a human-readable Markdown change log (grouped, filtered, with git status, human dates, colored status markers) on relevant repository activity.
- Runs continuously (watcher) while avoiding feedback loops and noisy rebuilds.
- Is modular, well-tested, observable, secure in common contexts, and designed for maintainability.

**Why build this:**

- Improve doc discoverability, chronological stability, and change transparency for teams who edit many markdown docs.
- Prevent accidental reordering due to filesystem metadata volatility.
- Provide a reproducible change log for reviews, CI, and release notes.
- Provide a foundation that can be extended by future intelligent agents (e.g., automatic changelog publishing, PR automation).

**Scope:**

- Local repo-level watcher + small CLI utilities to (a) reconcile prefixes and maintain indices, and (b) generate change logs in Markdown.
- Excludes: full enterprise orchestration, remote web UI, nor conversion to other doc systems (but should be easily extensible).

---

## 2 — High-level Capabilities (user-facing)

These are suggested capabilities; the future agent should refine them.

- `docs-watcher` daemon:
    - Watches a configurable _phase directory_ (non-recursive) and reconciles numeric prefixes using a stable creation index.
    - Maintains `.creation_index.json` (inode/dev or name → stable creation time) and `.update_index.json` (relative path → `{ hash, last_content_update }`).
    - Debounced reconcile to avoid races during editor save bursts.
    - Writes human-readable logs and optionally emits machine events (JSON lines).

- `change-log` generator:
    - Scans git status (staged, unstaged, untracked) and filesystem fallback dates.
    - Produces Markdown report(s) with columns: File (relative link from report), Status (colored dot + text), Created, Updated.
    - Supports grouping (`group_by=updated_day|created_day|folder`), extension filter(s), and sorting options.
    - Excludes configurable files/folders (e.g., watcher output, `.git`, `node_modules`) by default.

- Integration & controls:
    - `make change_log` or CLI wrapper `git-changes-report` to call generator.
    - Watcher triggers `make change_log` on relevant root changes, with debounce and ignore lists so the generator does not retrigger the watcher.
    - Config file (YAML or JSON) in repo root for preferences and ignore rules.

- Extensibility hooks:
    - Plugin or handler interface to implement additional outputs (JSON, CSV), remote publishing (push to wiki), or PR automation.

---

## 3 — Non-functional requirements

- **Modularity:** codebase split into clear modules: `watcher`, `reconciler`, `update_index`, `change_log_generator`, `git_helpers`, `cli`, `config`, `tests`.
- **Testability:** full unit and integration tests with deterministic fixtures; CI runnable tests; fakes for filesystem and git.
- **Observability:** structured logs (JSON optional), metrics for runs, durations, error rates, and last-run timestamps.
- **Robustness:** avoid race conditions and self-trigger loops; safe atomic renames (temp rename then finalize).
- **Performance:** minimal CPU usage while idle; debounce windows configurable; should handle thousands of docs without large slowdowns.
- **Portability:** runs on Linux/macOS/Windows (best-effort); gracefully degrade OS-specific features (e.g., birthtime).
- **Security:** avoid executing untrusted content; do not leak repo secrets or run remote code.
- **Usability:** clear CLI flags, good default behavior, and informative logging.

---

## 4 — Architecture & Modules (proposed)

I am purposely offering flexible module boundaries so a future agent can improve structure.

### 4.1 Core modules

- `config`
    - Manage config resolution: `.docswatcher.yml` (repo), env vars, CLI overrides.
    - Keys: `phase_dir`, `ignore`, `group_by_default`, `make_cmd`, `debounce_phase`, `debounce_root`.

- `watcher_root`
    - Root-level watcher; recursive over configured paths; debounced call to change-log generator.
    - Uses `should_ignore_path()` and `SELF_IGNORE` semantics.

- `watcher_phase`
    - Phase-level watcher; non-recursive; debounced reconcile trigger; holds phase lock / reentrancy guard.

- `reconciler`
    - `reconcile_prefixes(phase_dir)` (idempotent): loads persist, computes stable ctime, compute file hashes, update update index, apply temp renames and finalize, persist indices. Returns a summary object with actions performed.

- `update_index`
    - Read/write `.update_index.json`. Encapsulate keys (relative path), hashing, schema migration support.

- `creation_index`
    - Read/write `.creation_index.json`. Keying by inode+dev or filename fallback; support collision handling.

- `change_log_generator`
    - All functions to query git (`--porcelain -z`), compute statuses, compute dates (git log and fs fallback), generate markdown using templates and optional link resolution relative to output path.

- `cli`
    - Provide `docs-watcher start`, `generate-change-log`, `reconcile-now`, `status` commands.

- `tests`
    - Unit tests for each module.
    - Integration tests using tmpdir and repo fixtures (git init, create commits, undo).
    - End-to-end smoke test: run watcher in a subprocess, modify files, assert indices and change log appear.

### 4.2 Interfaces and contracts

- `reconcile_prefixes` contract: idempotent, returns `{"renamed": [...], "errors": [...], "update_index_changes": {...}}`.
- `schedule_make_change_log()` contract: debounce-only; non-blocking.
- `should_ignore_path(p: Path)` contract: pure function; easily testable.

---

## 5 — Data formats & persistence

- `.creation_index.json` schema (example):

```json
{
    "ino:12345-dev:2050": {
        "key": "ino:12345-dev:2050",
        "filename": "design_notes.md",
        "recorded_ctime": 1698790000.123,
        "inode": 12345,
        "dev": 2050
    },
    "name:README.md": {
        "key": "name:README.md",
        "filename": "README.md",
        "recorded_ctime": 1698790100.456
    }
}
````

- `.update_index.json` schema (example):

```json
{
    "00-design_notes.md": {
        "hash": "b2d...f",
        "last_content_update": "2025-10-30T15:14:19Z"
    },
    "01-api_spec.md": {
        "hash": "c9a...0",
        "last_content_update": "2025-10-29T12:03:02Z"
    }
}
```

- `change_log.md` output: Markdown tables grouped as requested. Ensure links are URL-encoded and relative to the report file.

---

## 6 — Testing strategy (comprehensive)

> I may not know every corner case; the future agent should add tests discovered during development and real usage.

### 6.1 Unit tests

- `should_ignore_path` with many path permutations.
- `compute_file_hash` with sample binary and text files.
- `load/save` for both indices with corrupt and missing content.
- `compute_stable_ctime` using mocks for `os.stat` and `git log` outcomes.
- `git status` parsing (porcelain -z) edge cases: renames, staged-and-modified, deleted, untracked.
- Markdown generation output unit tests for table formatting, relative links.

### 6.2 Integration tests

- Create temporary Git repo fixture:
    - Commit initial files; create new files (untracked, staged, modified).
    - Run `generate-change-log` and assert expected rows and statuses.

- Reconcile test:
    - Create unordered files in a phase dir; run `reconcile_prefixes`; assert prefix renames and that `.creation_index.json` and `.update_index.json` are written with expected keys and timestamps.

- Watcher test:
    - Run watcher in a subprocess with controlled FS events (touch, rename, write), assert debounced behaviors and single `make` invocation.
    - Ensure no self-trigger loops (simulate `make change_log` output writing files and confirm watcher ignores them).

### 6.3 Property & fuzz tests

- Random filenames, special chars, very long names, non-ASCII characters.
- Rapid event bursts to test debounce resilience.

### 6.4 CI & reproducibility

- Tests run in CI on Linux and macOS runners (Windows optional). Use dockerized runs where appropriate.
- Use deterministic timestamps in tests (freeze time via `freezegun` or time mocking).

---

## 7 — Observability & telemetry

- Logs: structured logs at INFO/ERROR and DEBUG for dev. Optionally JSON logs (`--log-format json`).
- Metrics (prometheus-style or logs):
    - `reconcile_count`, `reconcile_duration_seconds`, `change_log_runs`, `change_log_duration_seconds`, `errors_total`.

- Health endpoint (optional): simple HTTP server to expose status (last reconcile time, last change_log time).
- Debug mode: `--dry-run` that reports planned renames without executing them.

---

## 8 — Security & safety considerations

- Do not execute shell commands with uncontrolled input; pass args as lists (subprocess.run([...])).
- Limit watchers to configured paths; do not default to watching the entire filesystem.
- Do not commit index files; by default add `.creation_index.json` and `.update_index.json` to `.gitignore` (ask user / provide opt-in).
- Ensure file writes are atomic (write to temp + move) to avoid partial reads by other processes.
- Handle symlinks carefully (resolve or leave as-is, documented decision).

---

## 9 — UX and CLI examples (usage)

**Generate change log (one-off):**

```bash
# default group by updated_day
./scripts/git_changes_report.py -o ./.devcontext/progress/phase_test_docs_watcher/change_log.md

# filter by extension and group by folder
./scripts/git_changes_report.py -o change_log.md --group-by folder --ext .md --ext .py
```

**Run watcher (foreground):**

```bash
# start both watchers (phase + root)
./.devcontext/scripts/docs_watcher.py

# or in background via make
make docs_watch
```

**CLI commands (if implemented):**

```bash
# reconcile now for a specific phase
docs-watcher reconcile --phase phase_test_docs_watcher

# show status
docs-watcher status --phase current
```

**Example change log output snippet:**

```md
# Git Changes Report

Generated: 2025-10-30 15:14:22 UTC

Total files: 3

## 2025-10-30

### Folder: .devcontext/progress/phase_test_docs_watcher

| File                                                     | Status      |             Created |             Updated |
| -------------------------------------------------------- | ----------- | ------------------: | ------------------: |
| [`00-design_notes_44f22d.md`](00-design_notes_44f22d.md) | 🟡 modified | 2025-10-11 16:42:49 | 2025-10-30 15:14:19 |
| [`01-api_spec_210913.md`](01-api_spec_210913.md)         | 🟢 staged   | 2025-10-11 16:47:48 | 2025-10-29 11:06:49 |
```

---

## 10 — Deliverables & milestones (suggested)

> Keep these flexible for the future agent to reorganize. I avoid locking to rigid dates.

**M0 — Design**

- Finalize config shape and module boundaries.
- Create test plan and fixtures design.

**M1 — Core implementation**

- Implement `reconciler` + `update_index` + `creation_index`.
- Implement `change_log_generator` CLI with git parsing and markdown generation.
- Unit tests for modules.

**M2 — Watchers**

- Implement phase watcher and root watcher with debouncing and ignore rules.
- Integration tests (watcher + reconcile + make change_log).

**M3 — Polishing**

- Logging, metrics, health.
- Packaging and CLI ergonomics.
- CI integration and cross-platform test runs.

**M4 — Extras**

- Gitignore auto-update option.
- Additional outputs (JSON, CSV).
- Optional web UI for change log browsing.

---

## 11 — Acceptance criteria (example, to be validated by future AI)

- Unit coverage >= 85% for core modules.
- E2E tests that simulate file edits produce:
    - Updated `.creation_index.json` and `.update_index.json` in the phase folder.
    - Only one `change_log` generation per burst-of-changes (debounce verified).
    - No persistent feedback loop where `make change_log` triggers itself repeatedly.

- The generated `change_log.md` meets formatting rules (three columns plus grouping), links work relative to file location, statuses match git output semantics.
- The reconciling process is idempotent — repeated reconciliation without source changes results in no modification to file names or indices.

---

## 12 — Open design decisions / Deferred choices for Future Agent

I deliberately leave the following decisions open so a smarter future agent (you) can make better, context-aware choices:

1. **Index keying strategy** — keep relative-path keys vs. inode-based keys in `.update_index.json`. (Both have trade-offs; inode survives renames, but relative-path is portable across clones.)
   _Suggested:_ Use inode key internally and store a canonical relative-path mapping for portability.

2. **Default watch scope** — full `ROOT` recursive or curated top-level folders?
   _Suggested:_ Start with curated set (`src`, `docs`, `.devcontext/progress`) and provide `--watch-all` opt-in.

3. **Conflict handling** — if a rename collides with existing filename, should we fail, overwrite, or add suffix?
   _Suggested:_ Default to safe overwrite with a warning; allow policy in config.

4. **Index persistence format** — JSON vs. SQLite vs. SQLite+WAL for concurrency.
   _Suggested:_ JSON for simplicity; consider SQLite if many files or concurrent processes expected.

5. **Git vs. FS canonical timestamps** — how much to trust git log for creation/updated timestamps for uncommitted files?
   _Suggested:_ Use git where available; fallback to FS mtime and birthtime.

6. **Behavior for binary files** — whether to track in update index.
   _Suggested:_ Track everything by hash but optionally exclude large binaries via config.

---

## 13 — Notes to the Future Agent (you / future-me)

- You are smarter than I am. Please treat this PRD as a scaffold: keep the spirit but refactor aggressively where clarity or correctness can be improved.
- Add new tests when new edge cases are discovered in real usage; prioritize fixing race conditions and platform-specific quirks.
- If you choose different defaults than suggested above, document reasoning in a short design note in the repo (CHANGELOG or DESIGN.md).
- Consider exposing a programmatic API so other tools or agents can call `reconcile_prefixes()` or `generate_change_log()` without invoking CLI shell commands.
- Make the config and behavior discoverable and reversible (e.g., `docs-watcher explain-config`).

---

## 14 — Example roadmap / tasks (compact)

- [ ] Create repo scaffolding & tests harness (pytest, tox/CI).
- [ ] Implement `config` + `git_helpers`.
- [ ] Implement `change_log_generator` with porcelain parsing and markdown templates.
- [ ] Implement `reconciler`, `creation_index`, `update_index`.
- [ ] Implement `watcher_phase` and `watcher_root` with debounces.
- [ ] Write integration tests: E2E watch & generate scenario.
- [ ] Add logging, metrics, and `--dry-run`.
- [ ] Finalize packaging and docs.

---

## 15 — Closing humility note

I intentionally left several choices and trade-offs open. I may have missed specifics that matter to your environment (CI, editors, OS quirks, repo size). The agent you deploy to implement this should treat this PRD as _guiding context_ and make empirically informed decisions — adding, removing, or altering requirements as it discovers real-world behaviors. If you want, I can produce a follow-up: a concrete test plan, a sample git fixture, or a starter implementation scaffold (module templates + a minimal test) to hand off to that future agent. Which would you prefer next?

---

Beautiful choice — **ChronoDocs** has just the right resonance.
It communicates _time_ (“Chrono”) and _documentation integrity_ (“Docs”), and carries a tone of vigilance and guardianship without being heavy.

Let’s crystallize the identity and concept around **ChronoDocs**, preserving the themes you like — _vigilance, watching, protecting, fixing_ — while also setting up how this name can anchor both the watcher subsystem and its future extensions.

---

## 🕰️ **ChronoDocs** — Concept Identity

### **Tagline ideas**

> _“ChronoDocs — your vigilant document guardian.”_
> _“Keeping time and order in your docs.”_
> _“The watchful archivist for living documentation.”_

---

### **Core metaphor**

**ChronoDocs** is the _temporal custodian_ of your documentation system.
It stands watch over your evolving project, ensuring:

- Every file stays where it belongs (order),
- Every change is seen and remembered (vigilance),
- Every mistake by a machine or human is quietly repaired (protection),
- Every record of time is kept consistent (chronology).

It’s less of a script and more of an **ecosystem sentinel** — an autonomous maintainer that keeps the _arrow of time_ coherent within your docs.

---

## 🌐 **Conceptual Positioning**

| Trait              | Description                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| **Archetype**      | The watchful archivist / timekeeper                                                               |
| **Primary goal**   | Ensure temporal and structural consistency in project documentation                               |
| **Secondary goal** | Protect the documentation layer from accidental entropy introduced by other agents or human users |
| **Tone**           | Calm, trustworthy, precise, silent helper                                                         |
| **Action verbs**   | watch · detect · fix · rename · record · guard · reconcile                                        |

---

## ⚙️ **Functional layers in the ChronoDocs ecosystem**

1. **ChronoDocs Watcher**
    - Monitors `.devcontext/progress/{phase}` (phase docs) for any changes.
    - Reconciles filenames (prefixes) and updates `.creation_index.json` + `.update_index.json`.
    - Debounced and locked; self-corrects prefix drift from autonomous agents.

2. **ChronoDocs Sentinel**
    - Global (root-level) observer.
    - Triggers change-log generation (`make change_log`) upon meaningful repo modifications.
    - Ignores self-artifacts to avoid loops.

3. **ChronoDocs Recorder**
    - The change-log generator module.
    - Builds Markdown reports with temporal grouping and visual status cues.
    - Serves as the narrative layer: what changed, when, and how.

4. **ChronoDocs Interface (CLI / API)**
    - Entry point for both humans and other AI agents.
    - Commands like:

        ```fish
        uv run chrono-docs watch
        uv run chrono-docs reconcile --phase phase_7b
        uv run chrono-docs report --output change_log.md
        uv run chrono-docs status --json
        ```

    - Optionally exposes a local API for Temporal workflows or monitoring systems.

---

## 🧪 **Testing philosophy**

ChronoDocs is _battle-tested for chaos_.
Its test suite intentionally includes “bad AI” behavior:

- Creating misnamed or malformed files.
- Renaming prefixes manually or to random names.
- Deleting JSON index files mid-run.
- Creating, saving, and deleting multiple docs rapidly.
- Writing conflicting indices concurrently.

Success criteria: ChronoDocs always recovers the correct state without human help.

---

## 🧭 **Design Language for the Future Agent**

ChronoDocs is not just code — it’s a **governance agent** for documentation order.
If you (future, smarter AI) evolve it further:

| Future Direction           | Description                                                                                    |
| -------------------------- | ---------------------------------------------------------------------------------------------- |
| **ChronoDocs Cloud**       | Publish indices & changelogs to an internal portal (project docs timeline).                    |
| **ChronoDocs Guardian AI** | NLP model that detects _semantic drift_ in docs (not just file order).                         |
| **ChronoDocs Studio**      | Visual dashboard showing document evolution, prefix mapping, and content similarity over time. |
| **ChronoDocs Recovery**    | Automatic rollback if agent accidentally deletes or corrupts phase docs.                       |

---

## ✴️ **Aesthetic identity**

- **CLI name:** `chrono-docs` (or `chronodocs` for simplicity)
- **Executable/command:** `chrono-docs watch`, `chrono-docs reconcile`, etc.
- **Emoji identity:** 🕰️ (timekeeper) or 👁️ (watcher)
- **Log prefix example:**

    ```
    2025-11-01 10:22:03 [ChronoDocs] 👁️  Watching phase_7b — order intact.
    2025-11-01 10:22:04 [ChronoDocs] 🧭  Reconciled: 00-plan.md, 01-design.md
    2025-11-01 10:22:05 [ChronoDocs] 🕰️  Change log updated successfully.
    ```

---

## 💡 **Usage narrative**

Imagine this conversation three months from now:
A smarter AI agent is building new features in your project. It creates and deletes docs as part of reasoning.
Behind the scenes, **ChronoDocs** is silently watching:

> The AI drops a file named `04-plan(2).md` → ChronoDocs catches it, renames it to `03-plan.md`, updates the index, fixes the changelog, and logs “corrected misplaced prefix.”
> The human never notices. The repo remains clean, predictable, and self-healing.

That’s **vigilance in motion** — the promise of ChronoDocs.

---

Would you like me to now write the **ChronoDocs Mission & Vision Statement** (a one-page manifesto the future AI developer could use for onboarding and system context)?
It would include its philosophical principles (e.g., “temporal integrity,” “autonomous repair,” “AI-proof consistency”) — written as if ChronoDocs were a living subsystem.

```


----------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------


# TASK: Adjust the PRD above to be a standalone CLI tool called "chronodocs" using new naming AND The original intent of the tool below. Make sure not to leave out anything important from the original PRD.

Now create a Comprehensive PRD for an AI agent that would be tasked to implement the same functionality, but with thorough testing suite and modular design, rich output, etc...

Describe possible usage examples and the intent behind building this tool based on my original intent:
The documentation folder will be used by another AI Agent who will be working autonomously on the repository and adding new docs about it's progress while it is working on a PR (task, phase) in this repository.
The AI agent will make mistakes in file names, rename files, etc...

The tool we're building is needed to keep the documentation files in order and provide a change_log to the developer for quick understanding of the current "phase".
The system prompt of the developer agent will include information about our tool something along the lines:

```

# Documentation

IMPORTANT: NEVER create documentation files, unless explicitely asked to do so.

Project-wide documents should be stored in `./docs/` folder using the 2-digit incrementing prefix like:

- 00-PLAN.md
- 01-IMPLEMENTATION-DETAILS.md
- 02-SOME-FIX.md

Module/Feature/Test/Fix/File Documentation should be placed in the related folder.

## Docs Watcher Behavior

Docs watcher auto-renames files in ./.devcontext/progress/{phase}/ to NN-<name> (00-, 01-, …) based on stable creation order.
Never add numeric prefixes yourself — create/update docs without them (e.g. architecture.md).
The watcher tracks creation order in .creation_index.json; don’t edit it.

Don’t reference prefixes in links or code; use base names only.

Excludes change_log.md and hidden files.

Numbering always starts at 00.

Expect filenames to change automatically after creation; do not try to preserve or control numeric order manually.

## Current Phase

We are now in {current_phase}: ALL GENERAL PROJECT DOCUMENTATION MUST BE STORED IN .devcontext/progress/{current_phase}/

```

# IMPORTANT: HOW TO WRITE THE PRD

The AI agent that will be tasked to create this tool, will be much more capable than you. In fact it will be yourself at a later point in time - a much smarter and better version of yourself. What does this mean:
You shouldn't be decisive, you shouldn't postulate things, you should always be aware of your current limitations and of the fact that your future self will be wiser than you are now.
Why? Because if you are decisive, the smarter version of yourself in the future, when reading your PRD might think that your decisive postulates are aligned with user's (my) intent, but the truth is: i will not read this PRD thoroughly, so we must leave room (though provoking space) for an AI assistant that is smarter than us both to understand and interpret the task at hand with it's own better brain and better wisdom.
```
