"""CLI entrypoint. Usage: `python -m harness.runner <command> ...`.

See RUNBOOK.md for the order these are meant to be run in — selfcheck comes
first, always, before anything here is trusted.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path

from .adapters import REGISTRY
from .calib.loader import load_b0_prompt
from .oracle import overlay_hidden, run_oracle
from .saturation_probe import run_probe
from .schema import Harness, Model, Outcome, Quota, RunRecord, Task, Tokens, append_jsonl

ROOT = Path(__file__).parent
CALIB_DIR = ROOT / "calib" / "task_b0"
BASKET_DIR = ROOT / "basket"  # does not exist yet — see RUNBOOK.md "authoring the basket"
DATA_DIR = ROOT / "data"


def cmd_selfcheck(args: argparse.Namespace) -> None:
    """One run of b0, raw and unfiltered. Read the printed JSON before you
    trust anything the adapter parses out of it — see claude_code.py's
    module docstring."""
    adapter_cls = REGISTRY[args.plan]
    adapter = adapter_cls()
    prompt = load_b0_prompt(CALIB_DIR / "TASK.md")

    with tempfile.TemporaryDirectory() as tmp:
        task_dir = Path(tmp) / "repo"
        shutil.copytree(CALIB_DIR / "repo", task_dir)
        result = adapter.run_task(task_dir, prompt, arm=args.arm, timeout_s=args.timeout)
        overlay_hidden(task_dir, CALIB_DIR / "hidden")  # b0 has none; kept for symmetry with basket tasks
        result.oracle_pass = run_oracle(task_dir)

    print("--- raw ---")
    print(json.dumps(result.raw, indent=2)[:4000])
    print("--- parsed AdapterResult ---")
    print(result)
    print(
        "\nIf the field paths in claude_code.py._parse_result / run_task don't "
        "match what you see above, fix them now — nothing downstream re-checks this."
    )


def cmd_probe(args: argparse.Namespace) -> None:
    adapter_cls = REGISTRY[args.plan]
    adapter = adapter_cls()
    epoch = date.today().isoformat()[:7]
    plan_dir = DATA_DIR / args.plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    canary_path = plan_dir / f"{epoch}-canary.jsonl"

    def persist(c) -> None:  # per-cycle b0 outcomes for the CUSUM canary, written as they happen
        with canary_path.open("a") as f:
            f.write(json.dumps({"arm": args.arm, **c.__dict__}) + "\n")
        print(f"cycle solved={c.solved} meter={c.meter_after} wall={c.wall_s:.0f}s", flush=True)

    result = run_probe(
        adapter, arm=args.arm, epoch_budget_s=args.budget_s,
        duty_cycle_rho=args.rho, max_runs=args.max_runs, timeout_s=args.timeout,
        on_cycle=persist,
    )
    print({k: v for k, v in result.__dict__.items() if k != "cycles"})

    agg = {k: v for k, v in result.__dict__.items() if k != "cycles"}
    with (plan_dir / f"{epoch}-probe.jsonl").open("a") as f:
        f.write(json.dumps({"arm": args.arm, **agg}) + "\n")




def cmd_run_basket(args: argparse.Namespace) -> None:
    if not BASKET_DIR.exists():
        sys.exit(
            f"{BASKET_DIR} does not exist yet. The calibration task (b0) is "
            "wired up and testable now; the S1-S4 basket itself still needs "
            "authoring — see RUNBOOK.md 'authoring the basket'."
        )
    adapter_cls = REGISTRY[args.plan]
    adapter = adapter_cls()
    epoch = date.today().isoformat()[:7]
    out_path = DATA_DIR / args.plan / f"{epoch}-{args.arm}.jsonl"

    only = set(args.only.split(",")) if args.only else None

    for stratum_dir in sorted(BASKET_DIR.iterdir()):
        for task_dir_src in sorted(stratum_dir.iterdir()):
            task_id = task_dir_src.name
            if only is not None and f"{stratum_dir.name}/{task_id}" not in only:
                continue
            prompt = (task_dir_src / "TASK.md").read_text()
            for rep in range(args.rep_start, args.rep_start + args.reps):
                with tempfile.TemporaryDirectory() as tmp:
                    task_dir = Path(tmp) / "repo"
                    shutil.copytree(task_dir_src / "repo", task_dir)
                    result = adapter.run_task(task_dir, prompt, arm=args.arm, timeout_s=args.timeout)
                    overlay_hidden(task_dir, task_dir_src / "hidden")
                    result.oracle_pass = run_oracle(task_dir)

                record = RunRecord(
                    run_id=str(uuid.uuid4()),
                    epoch=epoch,
                    plan=adapter.plan_id,
                    task=Task(id=task_id, stratum=stratum_dir.name, repo="local-basket", commit="n/a", rev=rep),
                    harness=Harness(arm=args.arm, commit=adapter.harness_commit(args.arm)),
                    model=Model(advertised=result.model_advertised, fingerprint=result.model_fingerprint, routed=result.model_routed),
                    outcome=Outcome(oracle_pass=result.oracle_pass, steps=result.steps, wall_s=result.wall_s),
                    tokens=Tokens(prefill=result.prefill, decode=result.decode, reasoning=result.reasoning, cache_read=result.cache_read),
                    quota=Quota(meter_before=result.meter_before, meter_after=result.meter_after, consumed_nqu=result.consumed_nqu, unit=result.quota_unit),
                )
                append_jsonl(record, out_path)
                print(f"{task_id} rep{rep}: oracle_pass={result.oracle_pass} throttled={result.throttled}")
                if result.throttled:
                    print("throttled — stopping this basket run early")
                    return


def cmd_canary(args: argparse.Namespace) -> None:
    """Feed every logged b0 cycle (across all probe sessions to date) through
    the CUSUM canary — main.tex:738-749. `--p0` must be a value you declare
    before looking at the drift, not fit to the same series being tested;
    see cusum.py's docstring on calibrate_threshold."""
    from .cusum import CusumState, calibrate_threshold

    plan_dir = DATA_DIR / args.plan
    cycle_files = sorted(plan_dir.glob("*-canary.jsonl")) if plan_dir.exists() else []
    cycles = [
        json.loads(line)
        for path in cycle_files
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if not cycles:
        sys.exit(f"no canary cycles logged under {plan_dir}/*-canary.jsonl yet — run `probe` first.")
    cycles.sort(key=lambda c: c["t_unix"])

    if not 0.0 < args.p0 < 1.0:
        # p0=1 means "never fails": the null can't raise a false alarm, so the
        # Monte Carlo ARL0 calibration never terminates. Declare a p0 < 1.
        sys.exit(f"--p0 must be in (0, 1), got {args.p0}")
    threshold_h = calibrate_threshold(args.p0, args.slack_k, args.target_arl0, trials=args.trials)
    print(f"p0={args.p0} slack_k={args.slack_k} target_arl0={args.target_arl0} -> threshold_h={threshold_h:.3f}")

    state = CusumState(p0=args.p0, slack_k=args.slack_k, threshold_h=threshold_h)
    for c in cycles:
        if c["solved"] is None:
            print(f"t={c['t_unix']:.0f} arm={c['arm']} solved=None (throttled before oracle read) — skipped")
            continue
        fired = state.update(bool(c["solved"]))
        flag = " <-- ALARM" if fired else ""
        print(f"t={c['t_unix']:.0f} arm={c['arm']} solved={c['solved']} s={state.s:.3f}{flag}")

    print(f"\n{state.n} cycles fed, {state.alarms} alarm(s).")


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m harness.runner")
    sub = p.add_subparsers(dest="command", required=True)

    p_self = sub.add_parser("selfcheck", help="one raw run of b0 — do this first")
    p_self.add_argument("--plan", choices=list(REGISTRY), default="claude-code")
    p_self.add_argument("--arm", choices=["frozen", "as-delivered"], default="frozen")
    p_self.add_argument("--timeout", type=int, default=300)
    p_self.set_defaults(func=cmd_selfcheck)

    p_probe = sub.add_parser("probe", help="entitlement saturation probe (Algorithm 1)")
    p_probe.add_argument("--plan", choices=list(REGISTRY), default="claude-code")
    p_probe.add_argument("--arm", choices=["frozen", "as-delivered"], default="as-delivered")
    p_probe.add_argument("--budget-s", type=float, default=3600.0)
    p_probe.add_argument("--rho", type=float, default=0.05, help="duty cycle, fraction of time busy")
    p_probe.add_argument("--max-runs", type=int, default=200)
    p_probe.add_argument("--timeout", type=int, default=300)
    p_probe.set_defaults(func=cmd_probe)

    p_basket = sub.add_parser("run-basket", help="run the full S1-S4 basket for one arm/epoch")
    p_basket.add_argument("--plan", choices=list(REGISTRY), default="claude-code")
    p_basket.add_argument("--arm", choices=["frozen", "as-delivered"], required=True)
    p_basket.add_argument("--reps", type=int, default=3)
    p_basket.add_argument("--rep-start", type=int, default=1, help="first rep number, for extending an existing epoch without duplicating earlier reps")
    p_basket.add_argument("--only", default=None, help="comma-separated stratum/task_id list, e.g. S1/palindrome,S4/invoice_bug")
    p_basket.add_argument("--timeout", type=int, default=600)
    p_basket.set_defaults(func=cmd_run_basket)

    p_canary = sub.add_parser("canary", help="run the CUSUM drift canary over logged b0 cycles")
    p_canary.add_argument("--plan", choices=list(REGISTRY), default="claude-code")
    p_canary.add_argument("--p0", type=float, required=True, help="declared in-control b0 solve rate, fixed before observing drift")
    p_canary.add_argument("--slack-k", type=float, default=0.15)
    p_canary.add_argument("--target-arl0", type=float, default=200.0)
    p_canary.add_argument("--trials", type=int, default=1000, help="Monte Carlo trials per bisection step when calibrating the threshold")
    p_canary.set_defaults(func=cmd_canary)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
