"""Run record schema — mirrors main.tex Listing 1 (lst:record) exactly.

One JSONL line per run. Fields are null when the vendor/adapter does not
expose them; never backfill a null with a guess.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Task:
    id: str
    stratum: str  # S1 | S2 | S3 | S4
    repo: str
    commit: str
    rev: int = 1


@dataclass
class Harness:
    arm: str  # "frozen" | "as-delivered"
    commit: str  # CLI version pin, e.g. "claude-code@2.1.252"
    step_limit: Optional[int] = None
    temp: Optional[float] = None
    ctx: Optional[str] = None


@dataclass
class Model:
    advertised: Optional[str] = None
    fingerprint: Optional[str] = None
    routed: Optional[str] = None


@dataclass
class Outcome:
    oracle_pass: Optional[bool] = None
    steps: Optional[int] = None
    wall_s: Optional[float] = None
    kappa: Optional[float] = None  # judge confidence, null if oracle-only
    judge: Optional[str] = None


@dataclass
class Tokens:
    prefill: Optional[int] = None
    decode: Optional[int] = None
    reasoning: Optional[int] = None
    cache_read: Optional[int] = None


@dataclass
class Quota:
    meter_before: Optional[float] = None
    meter_after: Optional[float] = None
    consumed_nqu: Optional[float] = None
    unit: Optional[str] = None  # null when the plan exposes no meter


@dataclass
class Energy:
    model: Optional[str] = None  # e.g. "bottom-up-v2", null if not estimated
    j_lo: Optional[float] = None
    j_hi: Optional[float] = None


@dataclass
class RunRecord:
    run_id: str
    epoch: str  # "YYYY-MM"
    plan: str  # e.g. "claude-code/pro" — never a real vendor internal SKU
    task: Task
    harness: Harness
    model: Model
    outcome: Outcome
    tokens: Tokens
    quota: Quota
    energy: Energy = field(default_factory=Energy)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


def append_jsonl(record: RunRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.to_json() + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
