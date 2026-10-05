"""Epoch index computation — Algorithm 2, main.tex:751-775.

Reads run records already logged by runner.py (Listing 1 schema), never
generates them. Stratum weights are the basket weights declared in
main.tex:634-643 (S1 .30 / S2 .35 / S3 .20 / S4 .15) — a basket-construction
choice, not a measured quantity.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .schema import read_jsonl

STRATUM_WEIGHT = {"S1": 0.30, "S2": 0.35, "S3": 0.20, "S4": 0.15}


@dataclass
class EpochAggregate:
    s_hat: float          # weighted mean solve rate
    c_hat: float          # weighted mean consumption per attempt (NQU, or token-count proxy if NQU is null)
    c_unit: str            # "nqu" | "tokens_proxy" — always report which
    n_tasks: int
    n_runs: int
    by_task: dict          # task_id -> {"stratum": ..., "solve_rate": ..., "consumption": ...}


def _task_consumption(run: dict) -> Optional[float]:
    q = run["quota"]
    if q.get("consumed_nqu") is not None:
        return q["consumed_nqu"]
    tok = run["tokens"]
    parts = [tok.get("prefill"), tok.get("decode"), tok.get("reasoning")]
    if all(p is None for p in parts):
        return None
    # cache_read deliberately excluded — main.tex:675-678 warns pooling it in
    # with fresh tokens looks like a capability gain when it's a cache effect.
    return sum(p for p in parts if p is not None)


def aggregate_epoch(runs: list[dict], *, arm: str) -> EpochAggregate:
    arm_runs = [r for r in runs if r["harness"]["arm"] == arm]
    by_task_runs: dict[str, list[dict]] = defaultdict(list)
    stratum_of: dict[str, str] = {}
    for r in arm_runs:
        tid = r["task"]["id"]
        by_task_runs[tid].append(r)
        stratum_of[tid] = r["task"]["stratum"]

    by_task = {}
    for tid, rs in by_task_runs.items():
        solved = [1.0 if r["outcome"]["oracle_pass"] else 0.0 for r in rs if r["outcome"]["oracle_pass"] is not None]
        cons = [c for c in (_task_consumption(r) for r in rs) if c is not None]
        by_task[tid] = {
            "stratum": stratum_of[tid],
            "solve_rate": sum(solved) / len(solved) if solved else None,
            "consumption": sum(cons) / len(cons) if cons else None,
        }

    s_hat = _weighted_stratum_mean(by_task, "solve_rate")
    c_hat = _weighted_stratum_mean(by_task, "consumption")
    has_nqu = any(r["quota"].get("consumed_nqu") is not None for r in arm_runs)

    return EpochAggregate(
        s_hat=s_hat, c_hat=c_hat,
        c_unit="nqu" if has_nqu else "tokens_proxy",
        n_tasks=len(by_task), n_runs=len(arm_runs), by_task=by_task,
    )


def _weighted_stratum_mean(by_task: dict, field: str) -> Optional[float]:
    per_stratum: dict[str, list[float]] = defaultdict(list)
    for info in by_task.values():
        if info[field] is not None:
            per_stratum[info["stratum"]].append(info[field])
    total_w = 0.0
    acc = 0.0
    for stratum, vals in per_stratum.items():
        if stratum not in STRATUM_WEIGHT or not vals:
            continue
        w = STRATUM_WEIGHT[stratum]
        acc += w * (sum(vals) / len(vals))
        total_w += w
    if total_w == 0:
        return None
    return acc / total_w  # renormalised if a stratum has no data yet


def value_index(agg: EpochAggregate, q_hat: float, price: float) -> Optional[float]:
    """V_hat = Q_hat * s_hat / (c_hat * P), Equation in main.tex Section III."""
    if agg.s_hat is None or agg.c_hat in (None, 0):
        return None
    return q_hat * agg.s_hat / (agg.c_hat * price)


def bootstrap_ci_ln_v(
    by_task: dict, q_hat: float, price: float, *, b: int = 10_000, seed: int = 0,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Clustered bootstrap over tasks (not runs) for a CI on ln(V_hat) —
    main.tex:768-769, citing efron1994bootstrap. Returns (point, lo95, hi95).
    """
    task_ids = list(by_task.keys())
    valid = [t for t in task_ids if by_task[t]["solve_rate"] is not None and by_task[t]["consumption"]]
    if not valid:
        return None, None, None

    rng = random.Random(seed)
    point_agg = _resample_value(by_task, valid, q_hat, price)
    samples = []
    for _ in range(b):
        resample = [rng.choice(valid) for _ in valid]
        v = _resample_value(by_task, resample, q_hat, price)
        if v is not None and v > 0:
            samples.append(math.log(v))
    if not samples:
        return math.log(point_agg) if point_agg else None, None, None
    samples.sort()
    lo = samples[int(0.025 * len(samples))]
    hi = samples[int(0.975 * len(samples))]
    return (math.log(point_agg) if point_agg else None), lo, hi


def _resample_value(by_task: dict, task_ids: list[str], q_hat: float, price: float) -> Optional[float]:
    per_stratum_s: dict[str, list[float]] = defaultdict(list)
    per_stratum_c: dict[str, list[float]] = defaultdict(list)
    for tid in task_ids:
        info = by_task[tid]
        per_stratum_s[info["stratum"]].append(info["solve_rate"])
        per_stratum_c[info["stratum"]].append(info["consumption"])

    def weighted(per_stratum):
        total_w, acc = 0.0, 0.0
        for stratum, vals in per_stratum.items():
            if stratum not in STRATUM_WEIGHT:
                continue
            w = STRATUM_WEIGHT[stratum]
            acc += w * (sum(vals) / len(vals))
            total_w += w
        return acc / total_w if total_w else None

    s_hat, c_hat = weighted(per_stratum_s), weighted(per_stratum_c)
    if s_hat is None or not c_hat:
        return None
    return q_hat * s_hat / (c_hat * price)


def laspeyres_paasche_fisher(
    v_frozen_t0: Optional[float],
    v_frozen_t: Optional[float],
    v_delivered_t: Optional[float],
    v_delivered_t0: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """L(t), Pa(t), F(t) — main.tex:410-424 (Eq. after "Substitution bias").

    L(t) = V(h_t0, t) / V(h_t0, t0)   -- frozen harness, run now vs. run at t0
    Pa(t) = V(h_t, t)  / V(h_t, t0)   -- as-delivered harness, run now vs. run
                                          against the t0 endpoint (needs it to
                                          still be reachable)
    F(t) = sqrt(L(t) * Pa(t))

    All four V's are separately measured epoch values (from aggregate_epoch +
    value_index at different epochs/arms), never derived from one another.
    Proposition 2: if the t0 endpoint has been withdrawn, v_delivered_t0 (and
    often v_frozen_t0 too, once the base epoch itself becomes unrunnable) is
    unmeasurable — pass None and this correctly drops Pa and F, returning
    only L.
    """
    laspeyres = v_frozen_t / v_frozen_t0 if v_frozen_t0 not in (None, 0) and v_frozen_t is not None else None
    paasche = v_delivered_t / v_delivered_t0 if v_delivered_t0 not in (None, 0) and v_delivered_t is not None else None
    fisher = math.sqrt(laspeyres * paasche) if laspeyres is not None and paasche is not None else None
    return laspeyres, paasche, fisher


def debasement_rate(fisher_or_laspeyres: float, years_elapsed: float) -> float:
    """delta = -ln(F) / (t - t0), main.tex:772."""
    return -math.log(fisher_or_laspeyres) / years_elapsed
