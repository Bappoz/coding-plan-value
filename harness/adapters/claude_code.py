"""Claude Code CLI adapter.

Field mapping verified against a real `--output-format json` run on
2026-09-05 (mise-shimmed claude@2.1.252). Notes from that run:
  - stdout is NOT pure JSON: the mise shim prepends a banner line
    ("mise ~/.config/mise/config.toml tools: ..."). `_parse_result` locates
    the first '{' and parses from there.
  - there is no top-level "model" field; the model actually used is a key of
    "modelUsage" (e.g. {"claude-sonnet-5": {...}}).
  - "reasoning" tokens live at usage.output_tokens_details.thinking_tokens,
    not a top-level usage field.
  - usage.input_tokens is small (uncached prompt delta only); real prefill
    volume is input_tokens + cache_creation_input_tokens.
  - no numeric quota meter is exposed for a subscription plan, but
    total_cost_usd (list-price-equivalent) IS reported every run and is
    used here as the consumption proxy, labelled accordingly — never
    presented as the literal account meter.

Throttle detection is still a heuristic over stdout/stderr text plus
is_error/api_error_status, and still needs refining against a real
rate-limit response the first time one is observed — Algorithm 1 in
main.tex expects this to be vendor-specific and empirical, and the 2026-09-05
run never got throttled.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from .base import Adapter, AdapterResult

CLI_VERSION_PIN = "claude-code@2.1.252"  # from `claude -v`; re-pin via mise if it drifts
FROZEN_MODEL = "claude-sonnet-5"  # full model name, not an alias, so it can't silently roll forward

_THROTTLE_MARKERS = (
    "rate limit",
    "usage limit",
    "quota",
    "429",
    "please try again later",
)


class ClaudeCodeAdapter(Adapter):
    plan_id = "claude-code/subscription"  # set the actual tier (pro/max) at call site, never a made-up SKU

    def harness_commit(self, arm: str) -> str:
        return CLI_VERSION_PIN

    def run_task(self, task_dir: Path, prompt: str, *, arm: str, timeout_s: int) -> AdapterResult:
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "json",
            "--add-dir", str(task_dir),
            "--permission-mode", "bypassPermissions",  # task_dir is a disposable copy — see runner.py
        ]
        if arm == "frozen":
            cmd += ["--model", FROZEN_MODEL]
        # as-delivered: no --model override, whatever the account's default routing is

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

        result = self._parse_result(proc.stdout)
        # oracle_pass is deliberately left None here — the adapter's job ends
        # at "what did the client report". runner.py overlays any held-out
        # oracle files and computes oracle_pass itself, once the client can
        # no longer touch the workdir.

        blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
        is_error = bool(result.get("is_error")) if isinstance(result, dict) else False
        api_error_status = result.get("api_error_status") if isinstance(result, dict) else None
        throttled = (
            api_error_status == 429
            or (is_error and any(m in blob.lower() for m in _THROTTLE_MARKERS))
        )

        usage = result.get("usage", {}) if isinstance(result, dict) else {}
        thinking = usage.get("output_tokens_details", {}).get("thinking_tokens") if usage else None
        input_tokens = usage.get("input_tokens")
        cache_creation = usage.get("cache_creation_input_tokens")
        prefill = (input_tokens or 0) + (cache_creation or 0) if (input_tokens is not None or cache_creation is not None) else None

        model_usage = result.get("modelUsage", {}) if isinstance(result, dict) else {}
        model_advertised = next(iter(model_usage), None)

        total_cost_usd = result.get("total_cost_usd") if isinstance(result, dict) else None

        return AdapterResult(
            oracle_pass=None,
            steps=result.get("num_turns") if isinstance(result, dict) else None,
            wall_s=wall_s,
            prefill=prefill,
            decode=usage.get("output_tokens"),
            reasoning=thinking,
            cache_read=usage.get("cache_read_input_tokens"),
            meter_before=None,  # subscription plans expose no numeric meter via CLI/API
            meter_after=None,
            consumed_nqu=total_cost_usd,  # list-price-equivalent, not the literal account meter — see quota_unit
            quota_unit="usd_list_price_equivalent" if total_cost_usd is not None else None,
            model_advertised=model_advertised,
            model_fingerprint=None,
            model_routed=None,
            throttled=throttled,
            throttle_class="hard_stop" if throttled else None,
            raw=result if isinstance(result, dict) else {"stdout": proc.stdout, "stderr": proc.stderr},
        )

    @staticmethod
    def _parse_result(stdout: str) -> dict:
        start = stdout.find("{")
        if start == -1:
            return {"parse_error": True, "stdout": stdout}
        try:
            return json.loads(stdout[start:])
        except json.JSONDecodeError:
            return {"parse_error": True, "stdout": stdout}
