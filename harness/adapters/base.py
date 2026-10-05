"""Vendor adapter interface. One adapter per client under test.

An adapter's only job is: given a task workdir and a harness arm, run the
client and return whatever the client actually exposes. It must never
fabricate a field the vendor doesn't report — leave it None and let
schema.py serialise it as null.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AdapterResult:
    oracle_pass: Optional[bool]
    steps: Optional[int]
    wall_s: float
    prefill: Optional[int]
    decode: Optional[int]
    reasoning: Optional[int]
    cache_read: Optional[int]
    meter_before: Optional[float]
    meter_after: Optional[float]
    consumed_nqu: Optional[float]
    quota_unit: Optional[str]
    model_advertised: Optional[str]
    model_fingerprint: Optional[str]
    model_routed: Optional[str]
    throttled: bool
    throttle_class: Optional[str]  # "hard_stop" | "queue" | "silent_downgrade" | None
    raw: dict


class Adapter(ABC):
    plan_id: str  # e.g. "claude-code/pro" — filled by subclass

    @abstractmethod
    def run_task(self, task_dir: Path, prompt: str, *, arm: str, timeout_s: int) -> AdapterResult:
        """Execute one task under the given harness arm ("frozen" | "as-delivered").

        task_dir: a throwaway copy of the task repo the client may edit freely.
        Must not raise on a normal failure (bug not fixed, timeout); only
        raise on a genuine harness error (client not installed, auth missing).
        """
        raise NotImplementedError

    def harness_commit(self, arm: str) -> str:
        """Identifier for what was frozen — CLI/build version, not the model."""
        raise NotImplementedError
