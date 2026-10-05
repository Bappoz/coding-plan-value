"""Offline smoke test for the pure-logic modules (schema, cusum, epoch_index,
analysis) against synthetic data. Makes ZERO calls to any vendor CLI/API —
safe to run any time, including with zero remaining plan quota.

This does not test adapters/claude_code.py (that needs a real, budgeted
call — see RUNBOOK.md "selfcheck"). Run with:
    python -m harness.selftest
"""
from __future__ import annotations

import math
import random
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from .analysis import benjamini_hochberg, evaluate_hypotheses, one_sided_pvalue
from .cusum import CusumState, calibrate_threshold
from .epoch_index import aggregate_epoch, bootstrap_ci_ln_v, laspeyres_paasche_fisher, value_index
from .schema import Harness, Model, Outcome, Quota, RunRecord, Task, Tokens, append_jsonl, read_jsonl


def synthetic_runs(epoch: str, arm: str, n_per_task: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    strata = {"S1": 6, "S2": 5, "S3": 3, "S4": 2}  # tasks per stratum, synthetic basket size
    runs = []
    for stratum, n_tasks in strata.items():
        for ti in range(n_tasks):
            task_id = f"{stratum}-{ti}"
            base_p = {"S1": 0.9, "S2": 0.7, "S3": 0.5, "S4": 0.3}[stratum]
            for rep in range(n_per_task):
                solved = rng.random() < base_p
                consumed = rng.uniform(0.5, 3.0) * {"S1": 1, "S2": 2, "S3": 4, "S4": 6}[stratum]
                runs.append({
                    "run_id": str(uuid.uuid4()), "epoch": epoch, "plan": "synthetic/test",
                    "task": {"id": task_id, "stratum": stratum, "repo": "n/a", "commit": "n/a", "rev": rep},
                    "harness": {"arm": arm, "commit": "synthetic"},
                    "model": {"advertised": None, "fingerprint": None, "routed": None},
                    "outcome": {"oracle_pass": solved, "steps": rng.randint(1, 20), "wall_s": rng.uniform(5, 60), "kappa": None, "judge": None},
                    "tokens": {"prefill": None, "decode": None, "reasoning": None, "cache_read": None},
                    "quota": {"meter_before": None, "meter_after": None, "consumed_nqu": consumed, "unit": "synthetic"},
                    "energy": {"model": None, "j_lo": None, "j_hi": None},
                })
    return runs


def test_schema_roundtrip() -> None:
    rec = RunRecord(
        run_id="r1", epoch="2026-09", plan="synthetic/test",
        task=Task(id="S1-0", stratum="S1", repo="n/a", commit="n/a"),
        harness=Harness(arm="frozen", commit="synthetic"),
        model=Model(), outcome=Outcome(oracle_pass=True, steps=3, wall_s=12.0),
        tokens=Tokens(), quota=Quota(consumed_nqu=1.0, unit="synthetic"),
    )
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "run.jsonl"
        append_jsonl(rec, path)
        loaded = read_jsonl(path)
    assert len(loaded) == 1
    assert loaded[0]["outcome"]["oracle_pass"] is True
    assert loaded[0]["quota"]["consumed_nqu"] == 1.0
    print("schema roundtrip: ok")


def test_aggregate_and_value() -> None:
    runs_t0 = synthetic_runs("2026-01", "frozen", n_per_task=4, seed=1)
    runs_t = synthetic_runs("2026-09", "frozen", n_per_task=4, seed=2)  # different seed = drift

    agg_t0 = aggregate_epoch(runs_t0, arm="frozen")
    agg_t = aggregate_epoch(runs_t, arm="frozen")
    assert agg_t0.s_hat is not None and agg_t0.c_hat is not None
    print(f"t0: s_hat={agg_t0.s_hat:.3f} c_hat={agg_t0.c_hat:.3f} n_tasks={agg_t0.n_tasks}")
    print(f"t : s_hat={agg_t.s_hat:.3f} c_hat={agg_t.c_hat:.3f} n_tasks={agg_t.n_tasks}")

    q_hat, price = 500.0, 20.0  # declared/synthetic, never a real vendor number
    v_t0 = value_index(agg_t0, q_hat, price)
    v_t = value_index(agg_t, q_hat, price)
    assert v_t0 and v_t
    print(f"V(t0)={v_t0:.4f} V(t)={v_t:.4f} ratio={v_t / v_t0:.4f}")

    point, lo, hi = bootstrap_ci_ln_v(agg_t.by_task, q_hat, price, b=2000, seed=3)
    assert point is not None and lo is not None and hi is not None and lo <= point <= hi
    print(f"ln V(t) bootstrap: point={point:.4f} 95% CI=[{lo:.4f},{hi:.4f}]")

    L, Pa, F = laspeyres_paasche_fisher(v_t0, v_t, v_t, None)  # simulate deprecated t0 endpoint for as-delivered
    assert L is not None and Pa is None and F is None
    print(f"L={L:.4f}, Pa={Pa}, F={F} (Pa/F correctly None under deprecation)")


def test_cusum() -> None:
    h = calibrate_threshold(p0=0.8, slack_k=0.1, target_arl0=200, trials=500, seed=0)
    assert h > 0
    state = CusumState(p0=0.8, slack_k=0.1, threshold_h=h)
    rng = random.Random(7)
    fired_at = None
    for n in range(1, 300):
        p = 0.8 if n < 150 else 0.4  # step change at n=150
        alarmed = state.update(rng.random() < p)
        if alarmed and fired_at is None:
            fired_at = n
    print(f"cusum calibrated h={h:.3f}, first alarm after the shift-in at n={fired_at}")
    assert fired_at is not None and fired_at >= 150, "canary should not alarm before the shift"


def test_bh() -> None:
    pvals = {"H1": 0.001, "H2": 0.04, "H3": 0.2, "H4": 0.03, "H5": 0.5}
    rej = benjamini_hochberg(pvals, q=0.10)
    results = evaluate_hypotheses(pvals, {k: k for k in pvals}, q=0.10)
    print("BH rejections:", rej)
    assert rej["H1"] is True
    assert rej["H5"] is False
    assert one_sided_pvalue([0.1, 0.2, -0.05, 0.3], direction="gt") == 0.25
    print("benjamini-hochberg: ok")


def test_probe_stops_instead_of_hammering() -> None:
    """The probe must stop on a classified throttle, and on two consecutive
    no-usage failures (unverified throttle markers), and persist every cycle."""
    from .adapters.base import Adapter, AdapterResult
    from .saturation_probe import run_probe

    def res(consumed, throttled=False, raw=None):
        return AdapterResult(
            oracle_pass=None, steps=None, wall_s=0.0, prefill=None, decode=None, reasoning=None,
            cache_read=None, meter_before=None, meter_after=None, consumed_nqu=consumed, quota_unit=None,
            model_advertised=None, model_fingerprint=None, model_routed=None, throttled=throttled,
            throttle_class="hard_stop" if throttled else None, raw=raw or {},
        )

    class Scripted(Adapter):
        plan_id = "fake"
        def __init__(self, script): self.script, self.calls = list(script), 0
        def run_task(self, task_dir, prompt, *, arm, timeout_s):
            self.calls += 1
            return self.script.pop(0)

    seen = []
    a = Scripted([res(1.0), res(1.0), res(None, True, {"events": [{"type": "error", "message": "usage limit"}]}), res(1.0)])
    out = run_probe(a, arm="as-delivered", epoch_budget_s=60, duty_cycle_rho=1.0, max_runs=10, on_cycle=seen.append)
    assert out.throttle_class == "hard_stop" and a.calls == 3 and len(seen) == 3
    assert seen[-1].error_excerpt == "usage limit"

    b = Scripted([res(1.0), res(None), res(None), res(1.0)])
    out = run_probe(b, arm="as-delivered", epoch_budget_s=60, duty_cycle_rho=1.0, max_runs=10)
    assert out.throttle_class == "unclassified_failure" and b.calls == 3
    print("probe stop guards: ok")


if __name__ == "__main__":
    test_schema_roundtrip()
    test_aggregate_and_value()
    test_cusum()
    test_bh()
    test_probe_stops_instead_of_hammering()
    print("\nall offline selftests passed")
