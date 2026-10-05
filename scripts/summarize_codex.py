"""Publishable aggregate of the Codex basket run (raw JSONL stays private).

Same discipline as summarize_pilot.py, whose paired bootstrap it reuses.
Consumption here is the reported token total (the adapter's consumed_nqu,
unit tokens_total_reported), not USD; the quota meter (percent of the
rolling window) is summarised as first-before / last-after over the whole
basket, because at ~1% resolution it cannot resolve a single run.

Run with: python3 scripts/summarize_codex.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from harness.epoch_index import aggregate_epoch  # noqa: E402
from harness.schema import read_jsonl  # noqa: E402
from summarize_pilot import paired_bootstrap_diff  # noqa: E402

DATA_DIR = ROOT / "harness" / "data" / "codex"
OUT_PATH = ROOT / "harness" / "data" / "pilot_codex_2026-10_summary.json"
EPOCH = "2026-10"
ARMS = ["frozen", "as-delivered"]
REPS = 3


def main() -> None:
    summary: dict = {"epoch": EPOCH, "plan": "codex/subscription", "reps": REPS, "arms": {}}
    per_arm: dict = {}
    all_runs: list[dict] = []
    for arm in ARMS:
        runs = read_jsonl(DATA_DIR / f"{EPOCH}-{arm}.jsonl")
        all_runs += runs
        agg = aggregate_epoch(runs, arm=arm)
        per_arm[arm] = {
            tid: {"stratum": i["stratum"], "solve_rate": i["solve_rate"], "consumption": i["consumption"]}
            for tid, i in agg.by_task.items()
        }
        summary["arms"][arm] = {
            "s_hat": agg.s_hat,
            "c_hat": agg.c_hat,
            "c_unit": agg.c_unit,
            "n_tasks": agg.n_tasks,
            "n_runs": agg.n_runs,
            "raw_tokens": sum(r["quota"]["consumed_nqu"] for r in runs if r["quota"]["consumed_nqu"] is not None),
            "models": sorted({r["model"]["advertised"] for r in runs if r["model"]["advertised"]}),
            "by_task": per_arm[arm],
        }
    summary["paired_bootstrap_c_delivered_minus_frozen"] = paired_bootstrap_diff(
        per_arm["frozen"], per_arm["as-delivered"],
    )
    # frozen ran first, then as-delivered: the meter reading is one monotone series
    summary["meter"] = {
        "unit": "percent_of_primary_window",
        "start": all_runs[0]["quota"]["meter_before"],
        "end": all_runs[-1]["quota"]["meter_after"],
        "n_runs": len(all_runs),
    }
    summary["probe"] = probe_summary()
    OUT_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT_PATH}")


def probe_summary() -> dict:
    """Saturation probe run to the throttle (sequential, rho=1). Only a boolean
    for the vendor message is kept: the text carries account-specific URLs and a
    reset time, which stay in the private raw log."""
    from harness.cusum import CusumState, calibrate_threshold

    cycles = sorted(read_jsonl(DATA_DIR / f"{EPOCH}-canary.jsonl"), key=lambda c: c["t_unix"])
    sessions = read_jsonl(DATA_DIR / f"{EPOCH}-probe.jsonl")
    done = [c for c in cycles if c["solved"] is not None]
    stop = cycles[-1]
    meter_start, meter_end = cycles[0]["meter_after"], stop["meter_after"]
    first_full = next((i for i, c in enumerate(cycles) if c["meter_after"] >= 100), None)
    wall_h = sum(s["wall_s"] for s in sessions) / 3600
    h = calibrate_threshold(0.95, 0.15, 200.0, trials=1000)
    state = CusumState(p0=0.95, slack_k=0.15, threshold_h=h)
    for c in done:
        state.update(bool(c["solved"]))
    return {
        "n_sessions": len(sessions),
        "n_cycles_completed": len(done),
        "n_solved": sum(1 for c in done if c["solved"]),
        "throttle_class": sessions[-1]["throttle_class"],
        "stop_message_matched_marker": "usage limit" in (stop.get("error_excerpt") or "").lower(),
        "meter_start": meter_start,
        "meter_end": meter_end,
        "cycles_completed_after_meter_read_full": (
            len([c for c in cycles[first_full:] if c["solved"] is not None]) if first_full is not None else 0
        ),
        "tokens_per_cycle_mean": sum(c["consumed_nqu"] for c in done) / len(done),
        "models": sorted({c["model"] for c in cycles if c["model"]}),
        "wall_hours": wall_h,
        "wall_hours_at_5pct_duty": wall_h / 0.05,
        "q_hat_b0_per_window": len(done) / (meter_end - meter_start) * 100,
        "cusum_alarms": state.alarms,
    }


if __name__ == "__main__":
    main()
