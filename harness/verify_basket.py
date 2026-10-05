"""Offline basket verification. Zero vendor calls.

For every task in basket/<stratum>/<id>/, checks two things using the exact
oracle machinery runner.py uses (overlay_hidden + run_oracle):
  1. the buggy repo/ as shipped fails the oracle (the bug is real and
     reproducible — nothing here is a task that already passes)
  2. repo/ + reference/ (the intended fix) overlaid on top passes the oracle
     (the task is actually solvable and the oracle correctly recognises the
     fix)

Run with: python -m harness.verify_basket
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from .oracle import overlay_hidden, run_oracle

BASKET_DIR = Path(__file__).parent / "basket"


def check_task(task_dir: Path) -> tuple[bool, bool]:
    """Returns (buggy_fails, reference_passes)."""
    hidden_dir = task_dir / "hidden"
    reference_dir = task_dir / "reference"

    with tempfile.TemporaryDirectory() as tmp:
        buggy = Path(tmp) / "repo"
        shutil.copytree(task_dir / "repo", buggy)
        overlay_hidden(buggy, hidden_dir)
        buggy_pass = run_oracle(buggy)

    with tempfile.TemporaryDirectory() as tmp:
        fixed = Path(tmp) / "repo"
        shutil.copytree(task_dir / "repo", fixed)
        overlay_hidden(fixed, hidden_dir)
        if reference_dir.exists():
            for f in reference_dir.iterdir():
                shutil.copy2(f, fixed / f.name)
        fixed_pass = run_oracle(fixed)

    return (buggy_pass is False), (fixed_pass is True)


def main() -> None:
    if not BASKET_DIR.exists():
        sys.exit(f"{BASKET_DIR} does not exist")

    all_ok = True
    for stratum_dir in sorted(BASKET_DIR.iterdir()):
        if not stratum_dir.is_dir():
            continue
        for task_dir in sorted(stratum_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            task_id = f"{stratum_dir.name}/{task_dir.name}"
            buggy_fails, ref_passes = check_task(task_dir)
            status = "ok" if (buggy_fails and ref_passes) else "FAIL"
            if status == "FAIL":
                all_ok = False
            print(f"{task_id}: buggy_fails={buggy_fails} reference_passes={ref_passes} [{status}]")

    if not all_ok:
        sys.exit(1)
    print("\nall basket tasks verified: bug reproducible, fix recognised")


if __name__ == "__main__":
    main()
