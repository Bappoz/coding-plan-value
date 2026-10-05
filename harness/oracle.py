"""Independent oracle. Adapters never decide correctness themselves — the
caller (runner.py) overlays any private hold-out test files onto the
workdir first (main.tex:649: "a private hold-out third of the basket is
never published"), then runs this, after the client under test is done and
can no longer touch the workdir.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def run_oracle(task_dir: Path, *, timeout_s: int = 120) -> Optional[bool]:
    if shutil.which("pytest") is None:
        return None
    proc = subprocess.run(
        ["pytest", "-q"], cwd=task_dir, capture_output=True, text=True, timeout=timeout_s,
    )
    return proc.returncode == 0


def overlay_hidden(task_dir: Path, hidden_dir: Path) -> None:
    """Copy a task's held-out oracle files into the workdir. No-op if the
    task has none (e.g. S1, where the visible test IS the oracle)."""
    if not hidden_dir.exists():
        return
    for src in hidden_dir.rglob("*"):
        if src.is_file():
            dest = task_dir / src.relative_to(hidden_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
