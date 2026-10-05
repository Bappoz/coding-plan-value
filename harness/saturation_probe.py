"""Entitlement saturation probe — Algorithm 1, main.tex:706-726.

Drives an owned, paid account to its throttle boundary on the frozen
calibration task, at a low duty cycle. Section IX (ethics) constraints are
load-bearing here, not decorative:
  - only ever run against an account the experimenter owns and pays for
  - never bypass a throttle, CAPTCHA, or auth control
  - respect the duty-cycle sleep between runs — it exists to keep load low,
    not to speed up the probe
"""
from __future__ import annotations

import random
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .adapters.base import Adapter
from .calib.loader import load_b0_prompt
from .oracle import run_oracle

CALIB_DIR = Path(__file__).parent / "calib" / "task_b0"


@dataclass
class CanaryCycle:
    """One b0 outcome, timestamped, for feeding a CUSUM canary (main.tex:738-749).

    Not part of Listing 1 (lst:record) — this is harness-internal telemetry
    for the drift canary, not a basket run record.
    """
    t_unix: float
    solved: Optional[bool]  # None only if the cycle was throttled before an oracle read was possible
    consumed_nqu: Optional[float]
    wall_s: float
    meter_after: Optional[float] = None
    model: Optional[str] = None
    error_excerpt: Optional[str] = None  # set only on throttled / no-usage cycles: what the vendor actually said


@dataclass
class ProbeResult:
    q_hat: int  # in NQU by construction (Definition, main.tex:319)
    throttle_class: Optional[str]  # "hard_stop" | "queue" | "silent_downgrade" | None (epoch exhausted first)
    runs: int
    wall_s: float
    cycles: list  # list[CanaryCycle], kept untyped here to stay a plain dataclass field


def _failure_excerpt(raw: dict) -> Optional[str]:
    msgs = [
        str(e.get("message") or e.get("error"))
        for e in (raw.get("events") or [])
        if e.get("type") in ("error", "turn.failed")
    ]
    return " | ".join(msgs)[:600] if msgs else None


def run_probe(
    adapter: Adapter,
    *,
    arm: str,
    epoch_budget_s: float,
    duty_cycle_rho: float,  # fraction of wall-clock time allowed to be "busy"; e.g. 0.05
    max_runs: int,
    timeout_s: int = 300,
    on_cycle: Optional[Callable[[CanaryCycle], None]] = None,  # persist each cycle as it happens: a long probe must survive a crash
) -> ProbeResult:
    prompt = load_b0_prompt(CALIB_DIR / "TASK.md")
    t_start = time.monotonic()
    j = 0
    throttle_class: Optional[str] = None
    cycles: list[CanaryCycle] = []
    no_usage_streak = 0

    while j < max_runs and (time.monotonic() - t_start) < epoch_budget_s:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "repo"
            shutil.copytree(CALIB_DIR / "repo", task_dir)
            run_t0 = time.monotonic()
            result = adapter.run_task(task_dir, prompt, arm=arm, timeout_s=timeout_s)
            run_wall = time.monotonic() - run_t0
            solved = None if result.throttled else run_oracle(task_dir)

        j += 1
        failed = result.throttled or result.consumed_nqu is None
        cycle = CanaryCycle(
            t_unix=time.time(),
            solved=solved,
            consumed_nqu=result.consumed_nqu,
            wall_s=run_wall,
            meter_after=result.meter_after,
            model=result.model_advertised,
            error_excerpt=_failure_excerpt(result.raw) if failed else None,
        )
        cycles.append(cycle)
        if on_cycle:
            on_cycle(cycle)
        if result.throttled:
            throttle_class = result.throttle_class or "hard_stop"
            break
        # throttle markers are unverified heuristics: two runs in a row with no
        # usage reported means something is rejecting us — stop, don't hammer it.
        no_usage_streak = no_usage_streak + 1 if result.consumed_nqu is None else 0
        if no_usage_streak >= 2:
            throttle_class = "unclassified_failure"
            break

        # duty cycle: sleep so busy-time / (busy-time + sleep) <= rho, at a randomised offset
        # so probes don't cluster at the same time of day (main.tex:734-736).
        sleep_s = run_wall * (1.0 / duty_cycle_rho - 1.0)
        time.sleep(sleep_s * random.uniform(0.8, 1.2))

    return ProbeResult(
        q_hat=j,
        throttle_class=throttle_class,
        runs=j,
        wall_s=time.monotonic() - t_start,
        cycles=cycles,
    )
