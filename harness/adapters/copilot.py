"""GitHub Copilot CLI adapter.

Field mapping verified against real `copilot --output-format json` runs on
2026-09-06 (mise-shimmed copilot@1.0.82; `copilot --version` self-reports
1.0.83 — same mise-banner-vs-real-version split as claude_code.py, pin the
self-reported one). Notes from those runs:
  - stdout is JSONL (one JSON object per line), not one JSON blob. The first
    line is the mise shim banner and is not valid JSON; `_parse_events`
    silently skips any line that doesn't parse, which handles that banner
    the same way claude_code.py's `stdout.find("{")` does for a single blob.
  - the chosen/served model lives at `session.auto_mode_resolved.data.chosenModel`
    (also echoed per-message at `assistant.message.data.model`); there is no
    top-level "model" field on the run as a whole.
  - no prompt/output/cache token counts are exposed anywhere in the stream.
    `session.usage_checkpoint.data` only has `totalNanoAiu` (an opaque
    internal compute-cost unit, semantics undocumented — not mapped to
    anything here), `totalPremiumRequests`, `modelCacheState`, and
    `promptCacheBreakState`. (A relayed transcript from a separate Copilot
    CLI session claimed this event also carries `prompt_tokens`/
    `cache_read` fields — a real local run here shows it does not; this
    module trusts only the verified-here shape, not the relayed one.)
  - the terminal `result` event is NOT shaped like the other events: its
    fields (`exitCode`, `sessionId`, `usage`) sit directly on the event, with
    no "data" wrapper. (The same relayed transcript also claimed `result`
    DOES nest under "data" — also not what a real local run produced.)
  - consequently prefill/decode/reasoning/cache_read are all None for this
    adapter — not a parsing gap, this vendor's CLI genuinely does not report
    token-level counts, only the request-level premium-request count below.
  - `steps` isn't a direct field either; derived here by counting
    `assistant.turn_end` events, which is real observed structure, not a
    guess.
  - unlike Claude Code's subscription (no numeric meter at all), Copilot's
    plans meter in "premium requests" — `result.usage.premiumRequests`
    (mirrored in `session.usage_checkpoint.data.totalPremiumRequests`) is a
    real native quota unit, not a cost proxy. consumed_nqu / quota_unit
    reflect that distinction.

Confirmed (not just unresolved): FROZEN_MODEL cannot be set on this account.
Every literal tried against --model was rejected ("Model \"X\" from --model
flag is not available"), and the interactive `/model` picker confirms why —
every listed model shows as "Unavailable", including "gpt-5.6-luna" itself,
the exact model auto-routing actually serves requests with. So this is an
account/plan-level restriction on manual model selection (typical of
Copilot Business/Enterprise policy, or a lower individual tier), not a wrong
flag or a bug here — auto routing can reach a model that explicit selection
cannot. Until model selection is enabled on the account (an account/org
setting, not a code fix), FROZEN_MODEL stays None and the "frozen" arm
silently falls back to auto routing — same as "as-delivered" — which means
frozen-vs-as-delivered contrasts are NOT meaningful for this adapter.
Confirm this before running any real epoch with plan="copilot".

Throttle detection is an unverified heuristic, same caveat as
claude_code.py: no real rate-limit response has been observed yet.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from .base import Adapter, AdapterResult

CLI_VERSION_PIN = "github-copilot-cli@1.0.83"  # from `copilot --version`; re-pin via mise if it drifts
FROZEN_MODEL = None  # see module docstring — no confirmed selectable literal yet

_THROTTLE_MARKERS = (
    "rate limit",
    "usage limit",
    "quota",
    "429",
    "please try again later",
)


class CopilotAdapter(Adapter):
    plan_id = "copilot/subscription"

    def harness_commit(self, arm: str) -> str:
        return CLI_VERSION_PIN

    def run_task(self, task_dir: Path, prompt: str, *, arm: str, timeout_s: int) -> AdapterResult:
        cmd = [
            "copilot", "-p", prompt,
            "--output-format", "json",
            "--allow-all-tools",  # required for non-interactive mode
            "-C", str(task_dir),
        ]
        if arm == "frozen" and FROZEN_MODEL:
            cmd += ["--model", FROZEN_MODEL]
        # as-delivered (and frozen, until FROZEN_MODEL is resolved): no --model
        # override, whatever the account's auto routing picks.

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=task_dir, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            wall_s = time.monotonic() - t0
            return AdapterResult(
                oracle_pass=None, steps=None, wall_s=wall_s,
                prefill=None, decode=None, reasoning=None, cache_read=None,
                meter_before=None, meter_after=None, consumed_nqu=None, quota_unit=None,
                model_advertised=None, model_fingerprint=None, model_routed=None,
                throttled=False, throttle_class=None,
                raw={"error": "timeout", "stdout": (e.stdout or b"").decode(errors="replace")},
            )
        wall_s = time.monotonic() - t0

        events = self._parse_events(proc.stdout)
        # oracle_pass is deliberately left None — runner.py overlays any
        # held-out oracle files and computes it once the client can no
        # longer touch the workdir (harness/oracle.py).

        model_advertised = None
        usage_checkpoint: dict = {}
        result_event: dict = {}
        turn_ends = 0
        for ev in events:
            t = ev.get("type")
            if t == "session.auto_mode_resolved":
                model_advertised = ev.get("data", {}).get("chosenModel", model_advertised)
            elif t == "session.usage_checkpoint":
                usage_checkpoint = ev.get("data", {})  # last one wins if more than one
            elif t == "result":
                result_event = ev  # NOT nested under "data" — see module docstring
            elif t == "assistant.turn_end":
                turn_ends += 1

        exit_code = result_event.get("exitCode")
        result_usage = result_event.get("usage", {})
        premium_requests = result_usage.get("premiumRequests", usage_checkpoint.get("totalPremiumRequests"))

        blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
        is_error = exit_code is not None and exit_code != 0
        throttled = is_error and any(m in blob.lower() for m in _THROTTLE_MARKERS)

        return AdapterResult(
            oracle_pass=None,
            steps=turn_ends or None,
            wall_s=wall_s,
            prefill=None,  # not exposed anywhere in the stream — see module docstring
            decode=None,
            reasoning=None,
            cache_read=None,
            meter_before=None,  # subscription plans expose no before/after reading via CLI
            meter_after=None,
            consumed_nqu=premium_requests,
            quota_unit="copilot_premium_request" if premium_requests is not None else None,
            model_advertised=model_advertised,
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
                continue  # e.g. the mise shim banner line — not part of the JSONL stream
        return events
