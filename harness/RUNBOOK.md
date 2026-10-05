# Planmeter harness — runbook

Companion tooling for Section V of `main.tex`. This runs the protocol
against your own Claude Code subscription, on your own account, at low duty
cycle.

**Status (2026-09-05):** step 1 (selfcheck) done, parser verified against
real output. Step 3 (probe) run twice (900s + 1800s budget, rho=0.05):
`q_hat` 2 and 4, no throttle in either — `_THROTTLE_MARKERS` still
unverified against a real throttle response; still a lower bound, not a
saturation estimate. Step 4 (basket): 8 tasks authored and offline-verified
(`just harness-verify-basket`). Step 5 (epoch): both arms run at `k=3`
reps — 48 real runs total, aggregated via `scripts/summarize_pilot.py` into
`data/pilot_2026-09_summary.json` (checked in; raw JSONL stays local). The
paired bootstrap on the arm cost contrast (`n=8` tasks) is reported in
main.tex Section V-H — CI straddles zero, as Appendix A predicts at this
sample size. Steps 2, 6-7 still unexecuted; the basket is still a pilot,
not the ~15-25-task epoch a real run needs.

## 0. Preconditions (Section IX, main.tex:1005-1021)

- Own account, own money. Never someone else's plan.
- Never bypass a throttle, CAPTCHA, or auth control.
- Low duty cycle, randomised timing — `--rho` in `probe`, default 0.05 (5%
  busy). Don't raise it to go faster.
- Register the basket, weights, arms, and analysis script *before* the first
  epoch. Anything changed after is exploratory, not confirmatory
  (main.tex:781-783).

## 1. Selfcheck — do this before anything else

```
python -m harness.runner selfcheck --plan claude-code --arm frozen
```

This burns exactly one real call. Read the printed raw JSON and compare it
against the field paths in `adapters/claude_code.py::run_task` /
`_parse_result` (`usage.input_tokens`, `usage.output_tokens`,
`usage.cache_read_input_tokens`, `num_turns`). If a field is named
differently in your installed CLI version, **fix the adapter now** — every
other command trusts this parser blindly.

Also confirm `_THROTTLE_MARKERS` in the same file actually match what a real
rate-limit response looks like, once you see one (during the probe, below).

## 2. Offline selftest (no tokens spent, run any time)

```
python -m harness.selftest
```

Exercises schema round-trip, epoch aggregation, the clustered bootstrap,
CUSUM, and Benjamini-Hochberg against synthetic data. If this fails, the bug
is in the harness, not in a vendor response — fix it before spending a real
call on it.

## 3. Entitlement saturation probe (Algorithm 1)

```
python -m harness.runner probe --plan claude-code --arm as-delivered \
  --budget-s 3600 --rho 0.05 --max-runs 200
```

Run this at a time you're not otherwise using the plan, since it drives the
account toward its throttle. Repeat at a few randomised times of day across
the epoch — a single run gives one $\hat Q$ point, not a distribution. The
aggregate result lands in `data/<plan>/<yyyy-mm>-probe.jsonl`.

Every b0 cycle inside the probe is now also oracle-checked and logged
individually to `data/<plan>/<yyyy-mm>-canary.jsonl` (timestamp, solved,
consumed_nqu, wall_s) — this is the feed for the CUSUM canary below. Probe
sessions run *before* this was added have only the aggregate line, no
per-cycle history.

## 3b. Capability-drift canary (CUSUM)

```
python -m harness.runner canary --plan claude-code --p0 0.95
```

Reads every `*-canary.jsonl` file for the plan, orders by timestamp, and
feeds the b0 outcomes through a one-sided CUSUM (`harness/cusum.py`,
main.tex:738-749). `--p0` is the *declared* in-control solve rate — set it
once, from a baseline you trust, before looking at later data; do not fit it
to the same series you're testing for drift (see `calibrate_threshold`'s
docstring). `--p0` must be strictly inside (0,1): `p0=1.0` ("never fails") makes the
false-alarm null impossible and the ARL0 calibration never terminates, so the
command rejects it. Every b0 cycle logged so far has solved; declare something
like 0.95 (tolerates rare failures) rather than reading 1.0 off a short streak. A
single probe session's handful of cycles is far short of a meaningful ARL0 — this
command is only useful once cycles accumulate across many sessions over
time, per the "repeat at a few randomised times of day" note above.

## 4. Authoring the basket

A pilot basket exists: `basket/S1/{palindrome,merge_intervals}`,
`basket/S2/{cache_lru,todo_mark_done}`, `basket/S3/rename_api`,
`basket/S4/invoice_bug` — 6 tasks. S2-S4 ship a `hidden/` directory (a
private held-out oracle test, overlaid onto the workdir only after the
client is done — the agent never sees it, matching the private-hold-out
control in main.tex:649); S1 ships its regression test directly in `repo/`
since the visible test IS the oracle there.

Every task also ships a `reference/` fix, used only by
`just harness-verify-basket` (zero vendor calls) to confirm the bug is
really reproducible and the fix is really recognised by the oracle before
any real run touches it. Run this after adding or editing any task.

6 tasks is a pilot, not the ~15-25 a real epoch wants for the power analysis
in Appendix A — add more under the same `{repo/,hidden/,reference/,TASK.md}`
shape when ready; `run-basket` and `verify_basket` both pick up new tasks
automatically.

## 5. Running an epoch, once the basket exists

```
python -m harness.runner run-basket --plan claude-code --arm frozen --reps 3
python -m harness.runner run-basket --plan claude-code --arm as-delivered --reps 3
```

Then aggregate with `epoch_index.aggregate_epoch` / `value_index` /
`bootstrap_ci_ln_v`, and compare two epochs with `laspeyres_paasche_fisher`.
`P` (the price) is never hardcoded here — pass the archived public price for
that epoch yourself; this codebase does not print or store a real vendor
price anywhere (project `CLAUDE.md` rule).

## 6. Other clients

Codex (`adapters/codex.py`) is implemented and verified firsthand against real
`codex exec --json` runs on 2026-10-02 — field mapping and provenance are in that
file's docstring. Gotchas found the hard way: the subprocess needs
`stdin=DEVNULL` (codex otherwise blocks forever on "Reading additional input from
stdin..."); both arms pass `--ignore-user-config`; the model name and the quota
meter (`rate_limits.primary.used_percent`, ~1% resolution, 10080-min window on the
tested account) are only in the session rollout file under `~/.codex/sessions`, so
the adapter runs non-ephemeral and leaves one small session file per run (clean
with `codex archive`/`codex delete`). Frozen arm pins `-m gpt-6.1-sol` and is real.
Basket run 2026-10-03: 8 tasks x 3 reps x 2 arms = 48 runs, 48/48 solved, no throttle,
meter 1% -> 4%; aggregate via `just summarize-codex` (arms are identical while the
vendor default equals the pinned model — the contrast only has signal once it changes).
Saturation probe to the throttle, 2026-10-03/04 (`probe --plan codex --rho 1.0`, six
~2h sessions, 10.1 h): 1678 b0 cycles all solved, then a hard stop — an `error` +
`turn.failed` pair "You've hit your usage limit ... try again at <date>", matched by
the `usage limit` marker (verified for Codex only; Claude Code/Copilot markers are
still guesses). The meter read 100.0 for 8 completed cycles before the stop. rho=1.0
is a deliberate departure from the 5% default (at 5% this took ~8 days > the 7-day
window) and exhausts the weekly quota until reset: only do it on purpose. The probe
now persists every cycle as it happens and stops after 2 consecutive no-usage failures.
Per-run consumption is the reported token total; the meter is too coarse to move
within one run.

Copilot (`adapters/copilot.py`) is implemented and verified against real
`copilot --output-format json` runs on 2026-09-06 (`just harness-selfcheck
plan=copilot arm=as-delivered`) — see that file's module docstring for the
exact field mapping and provenance. Confirmed gap: `FROZEN_MODEL` is `None`
because this account has manual model selection disabled — the interactive
`/model` picker lists every model, including the one auto-routing actually
uses, as "Unavailable" (a Copilot plan/policy setting, not a code issue) —
so the "frozen" arm falls back to auto routing exactly like "as-delivered"
— **do not run a frozen-vs-as-delivered contrast against plan=copilot**, it
would not measure anything, unless model selection gets enabled on the
account. Copilot
also exposes no token-level counts at all (prefill/decode/reasoning/
cache_read are always None for this adapter) but does expose a real native
quota unit — `premium requests` — unlike Claude Code's subscription, which
exposes no meter at all and falls back to a USD-list-price-equivalent proxy.

## 7. If you find a real discrepancy

Responsible disclosure per main.tex:1013-1018: notify the vendor with the
run records, give a fixed embargo, and only then publish the method and the
aggregate index — never material that would help someone abuse the service.
