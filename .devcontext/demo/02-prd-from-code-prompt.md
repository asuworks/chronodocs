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
Why? Because if you are decisive, the smarter version of yourself in the future, when reading your PRD might think that your decisive postulates are aligned with user's (my) intent, but the truth is: i will not read this PRD thoroughly, so we must leave room (thought provoking space) for an AI assistant that is smarter than us both to understand and interpret the task at hand with it's own better brain and better wisdom.
Be humble.
