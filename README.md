# 🕰️ `chronodocs`

**The janitor for your AI slop.**

AI agents are great at generating docs — and very bad at organizing them.

`chronodocs` quietly cleans up after them: numbering files, tracking real changes, and generating changelogs so you can focus on shipping, not sorting markdown.

---

## 🧠 Why `chronodocs`?

When working with AI assistants (Claude, Cursor, Windsurf, etc.), your docs folder can turn into a landfill of half-thoughts and redundant drafts:

- Randomly named files (`final_v2_REALLY_FINAL.md`)
- Zero chronological order
- No clue what changed or why
- Impossible to follow the AI’s “thought process”

`chronodocs` fixes that mess by:

- 🕰️ **Auto-numbering** files (`00-`, `01-`, `02-`, etc.)
- 🔍 **Hash-based change tracking** — detects real edits, not just timestamp noise
- 🧾 **Auto-generated changelogs** — with git status integration
- 🧘 **Fully autonomous** — runs in the background, no manual cleanup required

Perfect for: **AI pair programming**, **agent-generated documentation**, **sprint histories**, and **autonomous development workflows**.

---

## ⚠️ Disclaimer

**Partially vibe-coded!**
`chronodocs` is co-developed with AI tools. I am using it daily and will do my best fixing bugs along the way. PRs welcome.

## ⚙️ Installation

Requires **Python 3.10+**

```bash
# Using uv (recommended)
uv tool install git+https://github.com/asuworks/chrono-docs

# Or with pip
pip install git+https://github.com/asuworks/chrono-docs
```

---

## 🚀 Quick Start

1. **Create a config file** (`.chronodocs.yml`) in your project root:

```yaml
phase_dir_template: ".devcontext/progress/{phase}"
watch_paths: ["."]
ignore_patterns: [".git/", "node_modules/", ".venv/"]
```

2. **Start the watcher** for your current phase:

```bash
chronodocs start --phase feature-development
```

This spins up two watchers:

- 🧩 **Phase watcher:** keeps your `.devcontext/progress/{phase}/` folder tidy
- 👀 **Sentinel watcher:** tracks the whole repo and logs changes to `change_log.md`

3. **Add files** to your phase directory:

```bash
echo "# Design Notes" > .devcontext/progress/feature-development/design.md
echo "# API Spec" > .devcontext/progress/feature-development/api.md
```

chronodocs instantly renames them:

- `00-design.md`
- `01-api.md`

✨ Clean. Ordered. Predictable.

---

## 🧭 Usage

### Common Commands

```bash
# Start both watchers (recommended for active development)
chronodocs start --phase my-phase

# One-time cleanup (no watching)
chronodocs reconcile --phase my-phase

# Preview renames without applying
chronodocs reconcile --phase my-phase --dry-run

# Generate a changelog report
chronodocs report --output changelog.md
```

### What Gets Created

| File                   | Purpose                       |
| ---------------------- | ----------------------------- |
| `.creation_index.json` | Tracks file creation order    |
| `.update_index.json`   | Hash map of content changes   |
| `change_log.md`        | Human-readable change history |

---

## 🧪 Playground Test

Want to see `chronodocs` in action? Use the included simulation script to watch it automatically organize chaotic file creation patterns.

### Steps

1. **Start the watcher** in one terminal:

```bash
chronodocs start --phase test-demo
```
This will initialize the `chronodocs` phase folder in `.devcontext/test-demo`

2. **Run the simulation** in another terminal:

```bash
# From the project root
python scripts/simulate_llm_activity.py
```

### What Happens

The script simulates typical "AI agent chaos":

- ✨ Creates files **without prefixes** (`design_notes_abc123.md`, `api_spec_def456.md`)
- 🤪 Creates a file with a **wrong prefix** (`99-old_prefix_example.md`)
- 🔄 **Renames files** mid-workflow (simulating agent refactoring)
- ⚡ Does it all **rapidly** to test debouncing

### Expected Results

Watch the phase directory transform in real-time:

```
Before:
  design_notes_abc123.md
  api_spec_def456.md
  99-old_prefix_example.md
  implementation_notes_ghi789.md

After (chronodocs auto-fixes):
  00-design_notes_abc123.md
  01-api_spec_def456.md
  02-old_prefix_example.md
  03-implementation_notes_ghi789.md
```

Files are renumbered in **creation order**, regardless of their original names or prefixes. Check `.creation_index.json` to see the tracked order.

**Bonus:** Run `chronodocs report` afterward to see all the changes logged in your changelog!

---

## 🤖 Teaching Your AI Assistant

To get the best results, give your AI agent a few house rules:

```markdown
# Documentation Rules

IMPORTANT: NEVER create documentation files unless explicitly asked.

All documentation should go in `.devcontext/progress/{phase}/`

## chronodocs Behavior

chronodocs automatically renames docs in `.devcontext/progress/{phase}/`
to `NN-<name>` (00-, 01-, 02-, etc.) based on when they were created.

**Never add numeric prefixes yourself.** Just create:

- ✅ `architecture.md`
- ❌ `00-architecture.md`

Don’t edit `.creation_index.json` or rely on prefix numbers in links.
chronodocs manages that automatically.

Numbering always starts at 00.

## Current Phase

We are now in `phase_xyz`:
ALL GENERAL PROJECT DOCUMENTATION MUST BE STORED IN `.devcontext/progress/phase_xyz/`
```

This teaches your AI:

- Where to put files
- To ignore prefixes
- To play nice with the watcher
- To stop fighting your directory structure

---

## 🧩 Configuration

Example `.chronodocs.yml`:

```yaml
phase_dir_template: ".devcontext/progress/{phase}"
watch_paths: ["src/", "docs/", ".devcontext/"]
ignore_patterns: [".git/", "*.tmp", "__pycache__/"]
debounce:
    phase: 2000 # Wait 2s after file changes
    root: 3000
report:
    group_by: "updated_day_then_folder"
    extensions: [".md", ".py"]
```

`chronodocs` watches your chaos and politely waits a few seconds before tidying up.

---

## 🛠️ Contributing

Contributions welcome!
`chronodocs` was built to scratch a very specific AI-dev itch. If it itches you too — scratches where it itches:

1. Fork the repo
2. Create a feature branch
3. Install pre-commit hooks:
    ```bash
    uv tool install pre-commit
    pre-commit install
    ```
4. Make your changes (hooks auto-format on commit)
5. Add tests for new functionality
6. Submit a pull request

## 🥋 Code Quality

**Pre-commit hooks** automatically run `ruff check --fix` and `ruff format` on every commit to maintain code quality.
