"""Shared TASK.md parsing for the b0 calibration task — one place, so
runner.py and saturation_probe.py can't drift apart on what "the prompt" is.
"""
from __future__ import annotations

import re
from pathlib import Path


def load_b0_prompt(task_md: Path) -> str:
    """Extract the indented prompt block under '## Prompt (verbatim ...)',
    stopping before the next '## ' heading (so '## Bug' / '## Oracle' never
    leak into what's sent to the client under test).
    """
    text = task_md.read_text()
    m = re.search(r"## Prompt.*?\n\n(.*?)\n\n## ", text, re.S)
    if not m:
        raise ValueError(f"could not find a '## Prompt' block in {task_md}")
    lines = m.group(1).splitlines()
    dedented = [ln[4:] if ln.startswith("    ") else ln for ln in lines]
    return "\n".join(dedented).strip()
