"""OpenAI Codex CLI adapter.

Field mapping verified firsthand against real `codex exec --json` runs on
2026-10-02 (codex-cli 0.159.2, ChatGPT-account login). Nothing here comes
from a relayed transcript — see copilot.py's docstring for why that matters.
Observed:
  - stdout is JSONL; the mise shim banner is the first line and is not JSON
    (`_parse_events` skips any line that doesn't parse).
  - `codex exec` waits on "Reading additional input from stdin..." when
    stdin is an open pipe, and never returns. The subprocess MUST get
    stdin=DEVNULL (found by hanging a backgrounded run).
  - token counts are on `turn.completed.usage`: input_tokens (INCLUDES
    cached_input_tokens — rollout `total_tokens` == input + output),
    cached_input_tokens, cache_write_input_tokens, output_tokens,
    reasoning_output_tokens. prefill = input - cached, cache_read = cached.
  - the stdout stream does NOT name the model, and has no quota meter. Both
    live in the session rollout file, ~/.codex/sessions/YYYY/MM/DD/
    rollout-<ts>-<thread_id>.jsonl: `turn_context.payload.model` and
    `event_msg/token_count.payload.rate_limits.primary.used_percent`
    (+ window_minutes; 10080 = weekly on the tested account). This is a real
    numeric meter, unlike Claude Code's subscription, but it is quantised to
    ~1%: it stayed at 1.0 across a four-model-call run of ~84k tokens, so a
    single b0 run cannot move it. meter_before/meter_after are therefore
    reported as read (before = first token_count of the session, i.e. after
    the first model call — a lower bound), and consumed_nqu uses the token
    total instead, labelled as such. The adapter runs NON-ephemeral because
    --ephemeral writes no rollout file; the cost is one small session file
    per run accumulating under ~/.codex/sessions (`codex archive`/`delete`).
  - `-m gpt-6.1-sol` is accepted (frozen arm can pin a model, unlike
    copilot.py). A bogus model fails on stdout as `turn.failed` carrying an
    HTTP-400 JSON string, not a nonzero-only exit.
  - both arms pass --ignore-user-config so ~/.codex/config.toml (which pins
    model/effort on this machine) can't make "as-delivered" secretly frozen.
    As-delivered = no -m, vendor default. Frozen adds -m and an explicit
    reasoning effort.
  - `steps` has no direct counter; derived as the number of completed
    command_execution + file_change items.

Throttle detection matches `error`/`turn.failed` text against
_THROTTLE_MARKERS. Verified once against a real limit (2026-10-04, weekly
window exhausted by the saturation probe): the client returns an `error` +
`turn.failed` pair whose message is "You've hit your usage limit ... try again
at <date>", matched by the "usage limit" marker. Observed that the meter
read 100.0 for several completed runs BEFORE this happened, so the meter
alone cannot be used to predict the stop. The other markers remain guesses.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from .base import Adapter, AdapterResult

CLI_VERSION_PIN = "codex-cli@0.159.2"  # from `codex --version`
FROZEN_MODEL = "gpt-6.1-sol"
FROZEN_EFFORT = "medium"

_THROTTLE_MARKERS = (
    "rate limit",
    "usage limit",
    "quota",
    "429",
    "please try again later",
)


class CodexAdapter(Adapter):
    plan_id = "codex/subscription"

    def harness_commit(self, arm: str) -> str:
        return CLI_VERSION_PIN

    def run_task(self, task_dir: Path, prompt: str, *, arm: str, timeout_s: int) -> AdapterResult:
        cmd = [
            "codex", "exec", "--json",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--sandbox", "workspace-write",  # task_dir is a disposable copy — see runner.py
            "-C", str(task_dir),
        ]
        if arm == "frozen":
            cmd += ["-m", FROZEN_MODEL, "-c", f'model_reasoning_effort="{FROZEN_EFFORT}"']
        cmd.append(prompt)

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=task_dir, capture_output=True, text=True, timeout=timeout_s,
                stdin=subprocess.DEVNULL,  # else codex blocks on "Reading additional input from stdin..."
            )
        except subprocess.TimeoutExpired as e:
            wall_s = time.monotonic() - t0
            return AdapterResult(
                oracle_pass=None, steps=None, wall_s=wall_s,
                prefill=None, decode=None, reasoning=None, cache_read=None,
                meter_before=None, meter_after=None, consumed_nqu=None, quota_unit=None,
                model_advertised=None, model_fingerprint=None, model_routed=None,
                throttled=False, throttle_class=None,
                raw={"error": "timeout", "stdout": (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")},
            )
        wall_s = time.monotonic() - t0

        events = self._parse_events(proc.stdout)
        # oracle_pass stays None — runner.py runs the (possibly held-out) oracle.

        thread_id: Optional[str] = None
        input_t = cached = output_t = reasoning_t = 0
        saw_usage = False
        steps = 0
        failure_text = ""
        for ev in events:
            t = ev.get("type")
            if t == "thread.started":
                thread_id = ev.get("thread_id")
            elif t == "turn.completed":
                u = ev.get("usage", {})
                saw_usage = True
                input_t += u.get("input_tokens", 0)
                cached += u.get("cached_input_tokens", 0)
                output_t += u.get("output_tokens", 0)
                reasoning_t += u.get("reasoning_output_tokens", 0)
            elif t == "item.completed" and ev.get("item", {}).get("type") in ("command_execution", "file_change"):
                steps += 1
            elif t in ("turn.failed", "error"):
                failure_text += " " + str(ev.get("message") or ev.get("error") or "")

        model, meter_before, meter_after = self._read_rollout(thread_id)

        blob = failure_text.lower()
        throttled = bool(failure_text) and any(m in blob for m in _THROTTLE_MARKERS)

        return AdapterResult(
            oracle_pass=None,
            steps=steps or None,
            wall_s=wall_s,
            prefill=(input_t - cached) if saw_usage else None,
            decode=output_t if saw_usage else None,
            reasoning=reasoning_t if saw_usage else None,
            cache_read=cached if saw_usage else None,
            meter_before=meter_before,  # percent of the primary rate-limit window, ~1% resolution
            meter_after=meter_after,
            consumed_nqu=float(input_t + output_t) if saw_usage else None,
            quota_unit="tokens_total_reported" if saw_usage else None,
            model_advertised=model,
            model_fingerprint=None,
            model_routed=None,
            throttled=throttled,
            throttle_class="hard_stop" if throttled else None,
            raw={"events": events} if events else {"stdout": proc.stdout, "stderr": proc.stderr},
        )

    @staticmethod
    def _parse_events(stdout: str) -> list[dict]:
        events = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # e.g. the mise shim banner
        return events

    @staticmethod
    def _read_rollout(thread_id: Optional[str]) -> tuple[Optional[str], Optional[float], Optional[float]]:
        """(model, meter_before, meter_after) from the session rollout file, or Nones."""
        if not thread_id:
            return None, None, None
        sessions = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"
        files = list(sessions.glob(f"**/rollout-*-{thread_id}.jsonl"))
        if not files:
            return None, None, None
        model: Optional[str] = None
        used: list[float] = []
        with files[0].open(encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                p = ev.get("payload") or {}
                if ev.get("type") == "turn_context" and model is None:
                    model = p.get("model")
                elif ev.get("type") == "event_msg" and p.get("type") == "token_count":
                    pct = ((p.get("rate_limits") or {}).get("primary") or {}).get("used_percent")
                    if pct is not None:
                        used.append(float(pct))
        return model, (used[0] if used else None), (used[-1] if used else None)
