#!/usr/bin/env python3
"""
simulate_llm_agent_for_docs_watcher.py

A small script that simulates an LLM agent adding/renaming files in the current phase folder so you can observe docs_watcher behavior.

Usage:
    python ./.devcontext/scripts/simulate_llm_agent_for_docs_watcher.py
"""

import time
from pathlib import Path
import uuid
import logging

ROOT = Path(__file__).resolve().parents[1]

PROGRESS_ROOT = ROOT / ".devcontext"
CURRENT_PHASE_FILE = "test-demo"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def get_phase_dir():
    try:
        phase = CURRENT_PHASE_FILE
    except Exception:
        phase = "current"
    path = PROGRESS_ROOT / phase
    path.mkdir(parents=True, exist_ok=True)
    return path


def touch(path: Path, content: str = ""):
    path.write_text(content)
    logging.info("Created: %s", path.name)


def main():
    d = get_phase_dir()
    logging.info("Simulating LLM actions in %s", d)
    # 1) create a file without prefix
    f1 = d / f"design_notes_{uuid.uuid4().hex[:6]}.md"
    touch(f1, "# design notes\n\ninitial")
    time.sleep(1.1)

    # 2) create another file without prefix
    f2 = d / f"api_spec_{uuid.uuid4().hex[:6]}.md"
    touch(f2, "openapi: 3.0.0\ninfo:\n  title: API")
    time.sleep(1.1)

    # 3) create a file with an incorrect prefix (e.g., 99-)
    f3 = d / "99-old_prefix_example.md"
    touch(f3, "This file should be re-prefixed by watcher.")
    time.sleep(1.1)

    # 4) create another unprefixed file quickly
    f4 = d / f"implementation_notes_{uuid.uuid4().hex[:6]}.md"
    touch(f4, "implementation detail")
    time.sleep(1.1)

    # 5) rename one file (simulate LLM renaming)
    new_name = d / f"renamed_by_agent_{uuid.uuid4().hex[:6]}.md"
    try:
        f2.rename(new_name)
        logging.info("Renamed %s -> %s", f2.name, new_name.name)
    except Exception as e:
        logging.error("Rename failed: %s", e)

    logging.info("Simulation complete. Let the watcher reconcile prefixes.")


if __name__ == "__main__":
    main()
