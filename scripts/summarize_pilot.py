"""Build the small, publishable pilot summary from the raw run logs.

Raw per-run JSONL under harness/data/ stays private (gitignored) — it's the
kind of material Section IX says should not be indiscriminately shared. This
script produces one aggregate, non-sensitive snapshot (no prompts, no
session ids, no vendor-internal fields) that IS meant to be checked in and
read by scripts/figures.py, so `just paper` stays reproducible for anyone
who has this repo without needing to have run the harness themselves.

Run with: python3 scripts/summarize_pilot.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))  # so `harness` is importable regardless of cwd

from harness.epoch_index import aggregate_epoch  # noqa: E402
from harness.schema import read_jsonl  # noqa: E402

DATA_DIR = ROOT / "harness" / "data" / "claude-code"
OUT_PATH = ROOT / "harness" / "data" / "pilot_2026-09_summary.json"

EPOCH = "2026-09"
ARMS = ["frozen", "as-delivered"]
REPS = 3
BOOTSTRAP_B = 10_000
BOOTSTRAP_SEED = 0


def paired_bootstrap_diff(by_task_frozen: dict, by_task_delivered: dict) -> dict:
    """Clustered-by-task bootstrap on the paired difference in c_hat
    (as-delivered minus frozen), matching the H2-style channel-contrast
    logic of harness/analysis.py, applied to this pilot's own 8 tasks."""
    tasks = sorted(set(by_task_frozen) & set(by_task_delivered))
    diffs = [
        by_task_delivered[t]["consumption"] - by_task_frozen[t]["consumption"]
        for t in tasks
        if by_task_frozen[t]["consumption"] is not None and by_task_delivered[t]["consumption"] is not None
    ]
    if not diffs:
        return {"n_tasks": 0}

    point = sum(diffs) / len(diffs)
    rng = random.Random(BOOTSTRAP_SEED)
    resamples = []
    for _ in range(BOOTSTRAP_B):
        sample = [rng.choice(diffs) for _ in diffs]
        resamples.append(sum(sample) / len(sample))
    resamples.sort()
    lo = resamples[int(0.025 * len(resamples))]
    hi = resamples[int(0.975 * len(resamples))]
    p_gt_zero = sum(1 for d in resamples if d <= 0) / len(resamples)  # one-sided: delivered costs more

    return {
        "n_tasks": len(diffs),
        "point": point,
        "ci95_lo": lo,
        "ci95_hi": hi,
        "one_sided_p_delivered_costs_more": p_gt_zero,
    }


def main() -> None:
    summary = {"epoch": EPOCH, "plan": "claude-code/subscription", "reps": REPS, "arms": {}}
    by_task_per_arm = {}
    for arm in ARMS:
        path = DATA_DIR / f"{EPOCH}-{arm}.jsonl"
        runs = read_jsonl(path)
        agg = aggregate_epoch(runs, arm=arm)
        per_task = {
            tid: {
                "stratum": info["stratum"],
                "solve_rate": info["solve_rate"],
                "consumption": info["consumption"],
            }
            for tid, info in agg.by_task.items()
        }
        by_task_per_arm[arm] = per_task
        # literal sum over every logged run's cost, reps included — the actual
        # money spent, distinct from c_hat (a stratum-weighted mean per attempt)
        raw_spend = sum(r["quota"]["consumed_nqu"] for r in runs if r["quota"]["consumed_nqu"] is not None)
        summary["arms"][arm] = {
            "s_hat": agg.s_hat,
            "c_hat": agg.c_hat,
            "c_unit": agg.c_unit,
            "n_tasks": agg.n_tasks,
            "n_runs": agg.n_runs,
            "raw_spend": raw_spend,
            "by_task": per_task,
        }

    summary["paired_bootstrap_c_delivered_minus_frozen"] = paired_bootstrap_diff(
        by_task_per_arm["frozen"], by_task_per_arm["as-delivered"],
    )

    probe_path = DATA_DIR / f"{EPOCH}-probe.jsonl"
    probes = [json.loads(l) for l in probe_path.read_text().splitlines()] if probe_path.exists() else []
    summary["probe"] = {
        "n_sessions": len(probes),
        "q_hat_per_session": [p["q_hat"] for p in probes],
        "wall_s_total": sum(p["wall_s"] for p in probes),
        "any_throttle": any(p["throttle_class"] for p in probes),
    }

    summary["cloud_canary"] = cloud_canary_summary()

    OUT_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT_PATH}")


CANARY_P0 = 0.95        # declared before looking at the series (see runner.cmd_canary)
CANARY_SLACK_K = 0.15
CANARY_ARL0 = 200.0
CANARY_TRIALS = 1000


def cloud_canary_summary() -> dict:
    """CUSUM over the scheduled cloud-routine b0 series. A separate channel from
    the local pilot (different harness, model pinned) — never merged into it."""
    from datetime import datetime, timezone

    from harness.cusum import CusumState, calibrate_threshold

    path = ROOT / "harness" / "data" / "claude-code-cloud" / f"{EPOCH}-canary.jsonl"
    cycles = sorted((json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()),
                    key=lambda c: c["t_unix"])
    h = calibrate_threshold(CANARY_P0, CANARY_SLACK_K, CANARY_ARL0, trials=CANARY_TRIALS)
    state = CusumState(p0=CANARY_P0, slack_k=CANARY_SLACK_K, threshold_h=h)
    for c in cycles:
        state.update(bool(c["solved"]))
    day = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "channel": "cloud-ccr, model pinned",
        "n_cycles": len(cycles),
        "n_solved": sum(1 for c in cycles if c["solved"]),
        "first_day": day(cycles[0]["t_unix"]),
        "last_day": day(cycles[-1]["t_unix"]),
        "p0": CANARY_P0,
        "slack_k": CANARY_SLACK_K,
        "target_arl0": CANARY_ARL0,
        "threshold_h": h,
        "alarms": state.alarms,
    }


if __name__ == "__main__":
    main()
