#!/usr/bin/env python3
r"""Generate every figure and every derived number used in main.tex.

Nothing in the paper is hand-typed: this script writes figures/derived.tex with
\newcommand definitions that main.tex \input's. Scenario parameters are declared
here (SCENARIO dict) and are explicitly synthetic -- they are illustrative inputs
to the model, not measurements of any vendor.
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from math import erf

FIG = pathlib.Path(__file__).resolve().parent.parent / "figures"
FIG.mkdir(exist_ok=True)
RNG = np.random.default_rng(20260904)


def _ncdf(z):
    return np.array([0.5 * (1 + erf(v / np.sqrt(2))) for v in np.atleast_1d(z)])

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8.5,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.4,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

COL = "#1f4e79"
ACC = "#b5482a"
NEU = "#6b7280"
DERIVED: dict[str, str] = {}


def emit(name: str, value, fmt: str = "{:.2f}") -> None:
    DERIVED[name] = value if isinstance(value, str) else fmt.format(value)


# --------------------------------------------------------------------------
# Declared synthetic scenario (Sec. VI). One year, one fixed-price plan.
# --------------------------------------------------------------------------
SCENARIO = {
    "dlnQ": -0.3567,   # entitlement: quota x0.70
    "dlns": +0.2231,   # capability:  solve rate x1.25
    "dlnc": +0.6931,   # consumption: quota per attempt x2.00
    "dlnP":  0.0,      # sticker price unchanged
    "dlne": -0.5108,   # energy per token x0.60 (serving efficiency gains)
    "dlntau": +0.9555, # tokens per attempt x2.60 (agentic loops + reasoning)
}

# --------------------------------------------------------------------------
# Fig. 2 -- concave test-time scaling forces cost-per-solve to rise
# --------------------------------------------------------------------------
GAMMA, TAU0, SMAX = 1.6, 150.0, 0.86  # Hill curve, tau in 10^3 tokens


def solve_rate(tau):
    return SMAX * tau**GAMMA / (tau**GAMMA + TAU0**GAMMA)


def elasticity(tau):
    return GAMMA * TAU0**GAMMA / (tau**GAMMA + TAU0**GAMMA)


tau = np.linspace(5, 900, 900)
s = solve_rate(tau)
cps = tau / s
tau_star = TAU0 * (GAMMA - 1) ** (1 / GAMMA)

fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.35))
ax[0].plot(tau, s, color=COL, lw=1.6)
ax[0].axvline(tau_star, color=ACC, ls="--", lw=1.0)
ax[0].set_xlabel(r"attempt budget $\tau$  [$10^3$ tokens]")
ax[0].set_ylabel(r"solve rate $s(\tau)$")
ax[0].set_title("(a) test-time scaling is concave")
ax[0].annotate(r"$\eta_{s,\tau}=1$", xy=(tau_star, solve_rate(tau_star)),
               xytext=(tau_star + 190, 0.30), color=ACC,
               arrowprops=dict(arrowstyle="->", color=ACC, lw=0.8))

ax[1].plot(tau, cps, color=COL, lw=1.6)
ax[1].axvline(tau_star, color=ACC, ls="--", lw=1.0)
ax[1].fill_between(tau, 0, cps, where=tau > tau_star, color=ACC, alpha=0.10)
ax[1].set_ylim(0, cps.max() * 1.05)
ax[1].set_xlabel(r"attempt budget $\tau$  [$10^3$ tokens]")
ax[1].set_ylabel(r"cost per solve $\tau/s(\tau)$")
ax[1].set_title("(b) unit cost of delivered work")
ax[1].annotate("every further capability gain\ncosts more per solved task",
               xy=(600, cps[np.argmin(np.abs(tau - 600))]), xytext=(250, 1250),
               color=ACC, arrowprops=dict(arrowstyle="->", color=ACC, lw=0.8))
fig.savefig(FIG / "fig_elasticity.pdf")
plt.close(fig)

emit("tauStar", tau_star, "{:.0f}")
emit("gammaHill", GAMMA, "{:.1f}")
emit("cpsRatio", cps[np.argmin(np.abs(tau - 600))] / cps.min(), "{:.1f}")

# --------------------------------------------------------------------------
# Fig. 3 -- iso-value map: where capability rises and value falls
# --------------------------------------------------------------------------
ds = np.linspace(0.0, 0.75, 320)
dc = np.linspace(0.0, 1.40, 320)
DS, DC = np.meshgrid(ds, dc)
DV = DS - DC + SCENARIO["dlnQ"]

fig, ax = plt.subplots(figsize=(3.4, 2.7))
levels = np.arange(-1.6, 0.9, 0.2)
cf = ax.contourf(DS, DC, DV, levels=levels, cmap="RdBu", alpha=0.85)
ax.contour(DS, DC, DV, levels=[0.0], colors="k", linewidths=1.2)
ax.plot(SCENARIO["dlns"], SCENARIO["dlnc"], "o", ms=5, color="k")
ax.annotate("scenario\n(Table II)", xy=(SCENARIO["dlns"], SCENARIO["dlnc"]),
            xytext=(0.36, 0.45), fontsize=7,
            arrowprops=dict(arrowstyle="->", lw=0.8))
ax.set_xlabel(r"$\Delta \ln s$  (capability)")
ax.set_ylabel(r"$\Delta \ln c$  (consumption)")
ax.set_title(r"$\Delta \ln V$ at $\Delta \ln Q = -0.36$, $\Delta \ln P = 0$")
cb = fig.colorbar(cf, ax=ax, pad=0.02)
cb.set_label(r"$\Delta \ln V$", fontsize=7)
cb.ax.tick_params(labelsize=6)
fig.savefig(FIG / "fig_isovalue.pdf")
plt.close(fig)

# --------------------------------------------------------------------------
# Fig. 4 -- additive decomposition of the twelve-month change in value
# --------------------------------------------------------------------------
chan = [
    (r"$\Delta \ln Q$" + "\nentitlement", SCENARIO["dlnQ"]),
    (r"$\Delta \ln s$" + "\ncapability", SCENARIO["dlns"]),
    (r"$-\Delta \ln c$" + "\nconsumption", -SCENARIO["dlnc"]),
    (r"$-\Delta \ln P$" + "\nprice", -SCENARIO["dlnP"]),
]
total = sum(v for _, v in chan)

fig, ax = plt.subplots(figsize=(3.4, 2.7))
run = 0.0
for i, (lab, v) in enumerate(chan):
    v = 0.0 if v == 0 else v
    ax.bar(i, v, bottom=run, width=0.62,
           color=(COL if v > 0 else (NEU if v == 0 else ACC)), alpha=0.9)
    ax.text(i, min(run, run + v) - 0.045, f"{v:+.2f}", ha="center",
            va="top", fontsize=6.5)
    run += v
ax.bar(len(chan), total, width=0.62, color="k", alpha=0.85)
ax.text(len(chan), total - 0.045, f"{total:+.2f}", ha="center", va="top",
        fontsize=6.5)
ax.axhline(0, color="k", lw=0.7)
ax.set_ylim(total - 0.22, 0.34)
ax.set_xticks(range(len(chan) + 1))
ax.set_xticklabels([lab for lab, _ in chan] + [r"$\Delta \ln V$" + "\nnet"],
                   fontsize=6.2)
ax.set_ylabel("log change over 12 months")
ax.set_title("value channels of a fixed-price plan")
fig.savefig(FIG / "fig_waterfall.pdf")
plt.close(fig)

emit("scenTotal", total, "{:+.2f}")
emit("scenRatio", 100 * np.exp(total), "{:.0f}")
emit("scenLoss", 100 * (1 - np.exp(total)), "{:.0f}")
emit("scenDelta", -total, "{:.2f}")
emit("scenHalfLife", np.log(2) / (-total) * 12, "{:.1f}")

# --------------------------------------------------------------------------
# Fig. 5 -- Jevons: per-token efficiency gains do not reach the task level
# --------------------------------------------------------------------------
months = np.linspace(0, 12, 13)
def traj(dln):
    return np.exp(dln * months / 12)

e_idx, tau_idx, s_idx = traj(SCENARIO["dlne"]), traj(SCENARIO["dlntau"]), traj(SCENARIO["dlns"])
eps_idx = tau_idx * e_idx / s_idx

fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.3))
ax[0].plot(months, e_idx, color=COL, lw=1.6, label=r"energy per token $e$")
ax[0].plot(months, tau_idx, color=ACC, lw=1.6, label=r"tokens per attempt $\tau$")
ax[0].plot(months, s_idx, color=NEU, lw=1.6, ls="--", label=r"solve rate $s$")
ax[0].axhline(1, color="k", lw=0.6)
ax[0].set_xlabel("month"); ax[0].set_ylabel("index (month 0 = 1)")
ax[0].set_title("(a) the three energy drivers"); ax[0].legend(frameon=False)

ax[1].plot(months, eps_idx, color="k", lw=1.8)
ax[1].axhline(1, color="k", lw=0.6, ls=":")
ax[1].fill_between(months, 1, eps_idx, where=eps_idx >= 1, color=ACC, alpha=0.15)
ax[1].set_xlabel("month")
ax[1].set_ylabel(r"energy per solved task, index")
ax[1].set_title("(b) rebound at the task level")
ax[1].annotate(f"{100*(eps_idx[-1]-1):+.0f}% after 12 months",
               xy=(12, eps_idx[-1]), xytext=(2.6, eps_idx[-1] * 0.975),
               fontsize=7.5, color=ACC)
fig.savefig(FIG / "fig_jevons.pdf")
plt.close(fig)

emit("epsChange", 100 * (eps_idx[-1] - 1), "{:+.0f}")
emit("eGain", 100 * (1 - np.exp(SCENARIO["dlne"])), "{:.0f}")
emit("tauGrowth", np.exp(SCENARIO["dlntau"]), "{:.1f}")
emit("jevonsSlack", SCENARIO["dlntau"] - SCENARIO["dlns"] + SCENARIO["dlne"], "{:+.2f}")

# --------------------------------------------------------------------------
# Fig. 6 -- statistical power of the index under a paired two-epoch design
# --------------------------------------------------------------------------
P_SOLVE, SIG_LOG, K_REPS, TRIALS = 0.45, 0.80, 3, 4000


def epoch_stat(n, p, cmul, rng, trials=TRIALS):
    """Log of the basket ratio estimator ln(s_hat / c_hat) for n tasks, K reps."""
    x = rng.random((trials, n, K_REPS)) < p
    u = cmul * np.exp(rng.normal(0, SIG_LOG, size=(trials, n, K_REPS)))
    s_hat = x.mean(axis=(1, 2)).clip(1e-6)
    c_hat = u.mean(axis=(1, 2))
    return np.log(s_hat / c_hat)


# delta-method variance of ln(s_hat/c_hat) per observation
VAR_S = (1 - P_SOLVE) / P_SOLVE                      # Var(s_hat)/s^2 per obs
VAR_C = np.exp(SIG_LOG**2) - 1.0                     # Var(c_hat)/c^2 per obs
VAR_UNIT = VAR_S + VAR_C
Z = 1.959963985 + 0.841621234                        # z_{1-a/2} + z_{power}


def n_analytic(ratio, power=0.80, k=K_REPS):
    """Basket size needed to resolve a value ratio, paired two-epoch design."""
    return 2.0 * VAR_UNIT * (Z / abs(np.log(ratio))) ** 2 / k


ns = np.array([10, 20, 40, 80, 160, 320, 640, 1280, 2560])
ratios = [0.90, 0.80, 0.70]
power = {r: [] for r in ratios}
for n in ns:
    base = epoch_stat(n, P_SOLVE, 1.0, RNG)
    null = epoch_stat(n, P_SOLVE, 1.0, RNG)
    crit = np.quantile(np.abs(null - base), 0.95)
    for r in ratios:
        alt = epoch_stat(n, P_SOLVE, 1.0 / r, RNG)   # value falls by factor r
        power[r].append(float(np.mean(np.abs(alt - base) > crit)))

fig, ax = plt.subplots(figsize=(3.4, 2.5))
grid = np.logspace(1, 3.5, 200)
for r, style, c in zip(ratios, ["o", "s", "^"], [COL, ACC, NEU]):
    ax.plot(ns, power[r], style, ms=3.4, color=c,
            label=f"{100*(1-r):.0f}% value loss")
    # analytic power curve for the same design
    se = np.sqrt(2 * VAR_UNIT / (grid * K_REPS))
    pw = 1 - _ncdf(1.959963985 - abs(np.log(r)) / se)
    ax.plot(grid, pw, color=c, lw=1.0, alpha=0.75)
ax.axhline(0.8, color="k", ls="--", lw=0.8)
ax.set_xscale("log")
ax.set_ylim(0, 1.02)
ax.set_xlabel(r"basket size $n$ (tasks, $k=3$ repetitions each)")
ax.set_ylabel(r"power at $\alpha = 0.05$")
ax.set_title("detecting a real change in plan value")
ax.legend(frameon=False, loc="lower right")
fig.savefig(FIG / "fig_power.pdf")
plt.close(fig)

emit("nReqTen", n_analytic(0.90), "{:.0f}")
emit("nReqTwenty", n_analytic(0.80), "{:.0f}")
emit("nReqThirty", n_analytic(0.70), "{:.0f}")
emit("nReqFifty", n_analytic(0.50), "{:.0f}")
emit("runsTen", n_analytic(0.90) * K_REPS * 2, "{:.0f}")
emit("kReps", str(K_REPS))
emit("pSolve", P_SOLVE, "{:.2f}")
emit("sigLog", SIG_LOG, "{:.1f}")
emit("varUnit", VAR_UNIT, "{:.2f}")

# --------------------------------------------------------------------------
# Fig. 7 -- the vendor's side: fat-tailed usage compresses the optimal quota
# --------------------------------------------------------------------------
PRICE, KAPPA, THETA, QC = 20.0, 6.0, 2.5, 8.0
ALPHA_C = 1.0 + THETA   # above this tail index an unbounded quota is optimal


def mean_capped(Q, alpha):
    """E[min(U, Q)] for U ~ Pareto(alpha, u_m = 1)."""
    return 1.0 + (1.0 - Q ** (1.0 - alpha)) / (alpha - 1.0)


def retention(Q):
    return Q**THETA / (Q**THETA + QC**THETA)


alphas = np.linspace(1.10, 2.50, 200)
Qgrid = np.logspace(0.005, 5.0, 8000)
Qstar = np.array([Qgrid[int(np.argmax(retention(Qgrid) *
                                      (PRICE - KAPPA * mean_capped(Qgrid, a))))]
                  for a in alphas])


def q_at(a):
    return float(Qstar[np.argmin(np.abs(alphas - a))])


rel = Qstar / q_at(2.5)

fig, ax = plt.subplots(figsize=(3.4, 2.5))
ax.plot(alphas, rel, color=COL, lw=1.8)
ax.plot([1.3], [q_at(1.3) / q_at(2.5)], "o", ms=4.5, color=ACC)
ax.set_xlabel(r"usage tail index $\alpha$   (smaller $=$ fatter tail)")
ax.set_ylabel(r"optimal quota $Q^\star(\alpha)/Q^\star(2.5)$")
ax.set_yscale("log")
ax.invert_xaxis()
ax.set_title("quota compression is a rational response")
ax.annotate(f"$\\times${q_at(1.3)/q_at(2.5):.3f} at $\\alpha=1.3$",
            xy=(1.3, q_at(1.3) / q_at(2.5)), xytext=(2.35, 0.03), fontsize=7,
            color=ACC, ha="left",
            arrowprops=dict(arrowstyle="->", color=ACC, lw=0.8,
                            connectionstyle="arc3,rad=-0.25"))
fig.savefig(FIG / "fig_vendor.pdf")
plt.close(fig)

emit("alphaC", ALPHA_C, "{:.1f}")
emit("thetaRet", THETA, "{:.1f}")
emit("alphaThin", 2.5, "{:.1f}")
emit("alphaFat", 1.3, "{:.1f}")
emit("QstarRel", q_at(1.3) / q_at(2.5), "{:.3f}")
emit("QstarDrop", 100 * (1 - q_at(1.3) / q_at(2.5)), "{:.0f}")
emit("kappaMarg", KAPPA, "{:.0f}")
emit("priceRef", PRICE, "{:.0f}")

# --------------------------------------------------------------------------
for k, v in [("dlnQ", "dlnQ"), ("dlns", "dlns"), ("dlnc", "dlnc"),
             ("dlnP", "dlnP"), ("dlne", "dlne"), ("dlntau", "dlntau")]:
    emit("scen" + k, SCENARIO[v], "{:+.4f}")
    emit("mult" + k, np.exp(SCENARIO[v]), "{:.2f}")
    emit("r" + k, SCENARIO[v], "{:+.2f}")

# --------------------------------------------------------------------------
# Real pilot run (Sec. V-G) -- NOT declared, read from a checked-in aggregate
# snapshot of an actual harness/ run against the author's own Claude Code
# subscription. See scripts/summarize_pilot.py for provenance; the raw
# per-run logs stay private under harness/data/, only this small aggregate
# is published.
# --------------------------------------------------------------------------
with open(pathlib.Path(__file__).resolve().parent.parent / "harness" / "data" / "pilot_2026-09_summary.json") as fh:
    PILOT = json.load(fh)

emit("pilotDate", "2026-09-05")
emit("pilotNTasks", PILOT["arms"]["frozen"]["n_tasks"], "{:d}")
emit("pilotReps", PILOT["reps"], "{:d}")
emit("pilotNRuns", PILOT["arms"]["frozen"]["n_runs"] + PILOT["arms"]["as-delivered"]["n_runs"], "{:d}")
emit("pilotSHatFrozen", 100 * PILOT["arms"]["frozen"]["s_hat"], "{:.0f}")
emit("pilotSHatDelivered", 100 * PILOT["arms"]["as-delivered"]["s_hat"], "{:.0f}")
emit("pilotCHatFrozen", PILOT["arms"]["frozen"]["c_hat"], "{:.3f}")
emit("pilotCHatDelivered", PILOT["arms"]["as-delivered"]["c_hat"], "{:.3f}")
emit("pilotCostTotal", PILOT["arms"]["frozen"]["raw_spend"] + PILOT["arms"]["as-delivered"]["raw_spend"], "{:.2f}")

_pb = PILOT["paired_bootstrap_c_delivered_minus_frozen"]
emit("pilotDiffPoint", _pb["point"], "{:+.3f}")
emit("pilotDiffLo", _pb["ci95_lo"], "{:+.3f}")
emit("pilotDiffHi", _pb["ci95_hi"], "{:+.3f}")
emit("pilotDiffP", _pb["one_sided_p_delivered_costs_more"], "{:.2f}")

_probe = PILOT["probe"]
emit("pilotProbeSessions", _probe["n_sessions"], "{:d}")
emit("pilotProbeQSum", sum(_probe["q_hat_per_session"]), "{:d}")
emit("pilotProbeMinutes", _probe["wall_s_total"] / 60, "{:.0f}")

# --------------------------------------------------------------------------
# Copilot adapter verification (Sec. V-H) -- no basket/epoch run yet, just
# the real calls used to confirm the field mapping in
# harness/adapters/copilot.py before any epoch is attempted against it.
# --------------------------------------------------------------------------
with open(pathlib.Path(__file__).resolve().parent.parent / "harness" / "data" / "copilot_adapter_verification_2026-09.json") as fh:
    COPILOT_VERIFY = json.load(fh)

emit("copilotVerifyDate", COPILOT_VERIFY["date"])
emit("copilotVerifyCalls", COPILOT_VERIFY["real_verification_calls"], "{:d}")
emit("copilotVerifyOraclePass", COPILOT_VERIFY["oracle_pass_count"], "{:d}")

# Codex adapter verification (Sec. V-H) -- same discipline as the Copilot block.
with open(pathlib.Path(__file__).resolve().parent.parent / "harness" / "data" / "codex_adapter_verification_2026-10.json") as fh:
    CODEX_VERIFY = json.load(fh)

emit("codexVerifyDate", CODEX_VERIFY["date"])
emit("codexVerifyRuns", CODEX_VERIFY["b0_runs"], "{:d}")
emit("codexVerifyPass", CODEX_VERIFY["b0_oracle_pass"], "{:d}")
emit("codexMeterWindowDays", CODEX_VERIFY["meter_window_minutes"] / (60 * 24), "{:.0f}")
emit("codexMeterRes", CODEX_VERIFY["meter_resolution_percent"], "{:.0f}")
emit("codexPostResetMeter", CODEX_VERIFY["post_reset_run"]["meter_percent"], "{:.0f}")

# Codex basket run (scripts/summarize_codex.py); consumption is tokens, not USD.
with open(pathlib.Path(__file__).resolve().parent.parent / "harness" / "data" / "pilot_codex_2026-10_summary.json") as fh:
    CODEX = json.load(fh)

_cf, _cd = CODEX["arms"]["frozen"], CODEX["arms"]["as-delivered"]
emit("codexReps", CODEX["reps"], "{:d}")
emit("codexNRuns", _cf["n_runs"] + _cd["n_runs"], "{:d}")
emit("codexModel", _cf["models"][0])
emit("codexSHatFrozen", 100 * _cf["s_hat"], "{:.0f}")
emit("codexSHatDelivered", 100 * _cd["s_hat"], "{:.0f}")
emit("codexCHatFrozenK", _cf["c_hat"] / 1e3, "{:.1f}")
emit("codexCHatDeliveredK", _cd["c_hat"] / 1e3, "{:.1f}")
_cb = CODEX["paired_bootstrap_c_delivered_minus_frozen"]
emit("codexDiffPoint", _cb["point"], "{:+.0f}")
emit("codexDiffLo", _cb["ci95_lo"], "{:+.0f}")
emit("codexDiffHi", _cb["ci95_hi"], "{:+.0f}")
emit("codexMeterStart", CODEX["meter"]["start"], "{:.0f}")
emit("codexMeterEnd", CODEX["meter"]["end"], "{:.0f}")
emit("codexTokMillions", (_cf["raw_tokens"] + _cd["raw_tokens"]) / 1e6, "{:.1f}")

_cp = CODEX["probe"]  # saturation probe run to the throttle
emit("codexProbeSessions", _cp["n_sessions"], "{:d}")
emit("codexProbeCycles", _cp["n_solved"], "{:d}")
emit("codexProbeHours", _cp["wall_hours"], "{:.0f}")
emit("codexProbeDutyDays", _cp["wall_hours_at_5pct_duty"] / 24, "{:.1f}")
emit("codexProbeAtFull", _cp["cycles_completed_after_meter_read_full"], "{:d}")
emit("codexProbeTokK", _cp["tokens_per_cycle_mean"] / 1e3, "{:.1f}")
emit("codexProbePerPoint", _cp["n_solved"] / (_cp["meter_end"] - _cp["meter_start"]), "{:.1f}")
emit("codexProbeQ", _cp["q_hat_b0_per_window"], "{:.0f}")

# Scheduled cloud-routine capability canary (Sec. V-H): a separate channel
# from the local pilot, summarised by scripts/summarize_pilot.py.
_cc = PILOT["cloud_canary"]
emit("canaryCycles", _cc["n_cycles"], "{:d}")
emit("canarySolved", _cc["n_solved"], "{:d}")
emit("canaryAlarms", _cc["alarms"], "{:d}")
emit("canaryFirstDay", _cc["first_day"])
emit("canaryLastDay", _cc["last_day"])
emit("canaryPzero", _cc["p0"], "{:.2f}")
emit("canaryArl", _cc["target_arl0"], "{:.0f}")

with open(FIG / "derived.tex", "w") as fh:
    fh.write("% GENERATED by scripts/figures.py -- do not edit by hand.\n")
    for k in sorted(DERIVED):
        fh.write(f"\\newcommand{{\\{k}}}{{{DERIVED[k]}}}\n")
with open(FIG / "derived.json", "w") as fh:
    json.dump(DERIVED, fh, indent=2, sort_keys=True)

print(json.dumps(DERIVED, indent=2, sort_keys=True))
