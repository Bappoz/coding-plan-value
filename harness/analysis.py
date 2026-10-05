"""Cross-epoch hypothesis tests H1-H5 (Table I, main.tex:785-807) and the
Benjamini-Hochberg correction main.tex:779-780 applies across them.

Each hypothesis is one-sided over a bootstrap distribution of a channel
contrast (e.g. Delta ln s between two epochs' frozen-arm runs). The bootstrap
distribution itself must come from `epoch_index.bootstrap_ci_ln_v`-style
clustered resampling over tasks — this module only consumes it, it does not
resample.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


def one_sided_pvalue(bootstrap_diffs: list[float], direction: Literal["gt", "lt"]) -> float:
    """P(H0) for a one-sided test against 0, from a bootstrap distribution of
    a contrast (e.g. resampled Delta ln s). direction="gt" tests whether the
    contrast is > 0 (H0: <= 0); "lt" tests whether it is < 0 (H0: >= 0).
    """
    n = len(bootstrap_diffs)
    if n == 0:
        raise ValueError("empty bootstrap distribution")
    if direction == "gt":
        wrong_side = sum(1 for d in bootstrap_diffs if d <= 0)
    else:
        wrong_side = sum(1 for d in bootstrap_diffs if d >= 0)
    return wrong_side / n


def benjamini_hochberg(pvalues: dict[str, float], q: float = 0.10) -> dict[str, bool]:
    """Standard BH step-up procedure. Returns {label: reject_H0} at FDR q.
    main.tex:779-780 sets q=0.10.
    """
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    reject = {label: False for label, _ in items}
    largest_k = 0
    for k, (label, p) in enumerate(items, start=1):
        if p <= (k / m) * q:
            largest_k = k
    for k, (label, _) in enumerate(items, start=1):
        if k <= largest_k:
            reject[label] = True
    return reject


@dataclass
class HypothesisResult:
    label: str        # "H1".."H5"
    channel: str       # e.g. "Delta ln s"
    pvalue: float
    reject_h0: bool     # after BH correction
    registered: bool = True  # False marks it exploratory (main.tex:781-783)


def evaluate_hypotheses(pvalues: dict[str, float], channels: dict[str, str], q: float = 0.10) -> list[HypothesisResult]:
    """pvalues and channels keyed by the same labels, e.g. {"H1": 0.03}."""
    rejections = benjamini_hochberg(pvalues, q=q)
    return [
        HypothesisResult(label=label, channel=channels[label], pvalue=p, reject_h0=rejections[label])
        for label, p in pvalues.items()
    ]
