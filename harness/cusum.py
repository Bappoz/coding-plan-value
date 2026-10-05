"""One-sided CUSUM drift canary — main.tex:738-749 (cites page1954cusum).

Detects a *decrease* in the canary solve rate. Implementation choice: a
linear (Shewhart-style) CUSUM directly on the Bernoulli outcome, target
p0, slack k, reset-on-alarm — a standard, if not likelihood-optimal,
instance of Page's test. A log-likelihood-ratio CUSUM is a drop-in
replacement for `CusumState.update` if a reviewer wants the optimal
version; the paper does not claim this is that version.

This is a *signal*, not identification: report the alarm and covariates
(latency, response-format fingerprint) alongside it, never a claim about
which model served the request (main.tex:745-749).
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class CusumState:
    p0: float           # in-control (historical) canary solve rate
    slack_k: float       # allowance, probability units; a common choice is |p0 - p1| / 2
    threshold_h: float   # alarm fires when the running statistic exceeds this
    s: float = 0.0
    n: int = 0
    alarms: int = 0

    def update(self, solved: bool) -> bool:
        """Feed one canary outcome. Returns True iff this observation raises an alarm."""
        x = 1.0 if solved else 0.0
        self.s = max(0.0, self.s + (self.p0 - self.slack_k) - x)
        self.n += 1
        fired = self.s > self.threshold_h
        if fired:
            self.alarms += 1
            self.s = 0.0  # Page-CUSUM restart after an alarm
        return fired


def calibrate_threshold(
    p0: float, slack_k: float, target_arl0: float,
    trials: int = 20000, seed: int = 0, max_run: int = 100_000,
) -> float:
    """Monte Carlo calibration of threshold_h to a target in-control ARL0
    (mean runs between false alarms under the null that the rate stays at
    p0). A declared simulation used only to pick the alarm threshold before
    the study starts — never a substitute for running the real canary.
    """
    rng = random.Random(seed)
    lo, hi = 0.0, 20.0
    for _ in range(40):
        h = (lo + hi) / 2
        arl = _simulate_arl0(p0, slack_k, h, trials, rng, max_run)
        if arl < target_arl0:
            lo = h
        else:
            hi = h
    return hi


def _simulate_arl0(p0: float, slack_k: float, h: float, trials: int, rng: random.Random, max_run: int) -> float:
    total = 0
    for _ in range(trials):
        s = 0.0
        n = 0
        while True:
            n += 1
            x = 1.0 if rng.random() < p0 else 0.0
            s = max(0.0, s + (p0 - slack_k) - x)
            if s > h or n >= max_run:
                total += n
                break
    return total / trials
