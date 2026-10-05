# coding-plan-value

*Does your AI coding plan still buy what it used to?* An IEEE-format article
(8 pages), the **Planmeter** measurement harness that supports it, and the
published aggregates of a small real pilot on three coding-assistant clients
(Claude Code, GitHub Copilot CLI, Codex CLI).

Status: preprint-quality, not peer reviewed. The pilot is a feasibility
demonstration (8 tasks, solve-rate ceiling), not a measurement of plan value.

## Layout

| Path | What |
|---|---|
| `main.tex`, `refs.bib` | the article |
| `scripts/figures.py` | single source of every figure and number in the text |
| `harness/` | schema, adapters, oracle, saturation probe, CUSUM canary, analysis, basket |
| `harness/RUNBOOK.md` | exact commands and ethics boundaries for real runs |
| `harness/data/*.json` | published pilot aggregates (raw run logs are not published) |

## Build

Needs `pdflatex`, `bibtex`, `just`, Python 3.12 with `numpy` and `matplotlib`.

```bash
just paper            # figures -> pdflatex -> bibtex -> pdflatex x2
just harness-selftest # offline, zero vendor calls
just harness-verify-basket
```

Real runs use your own accounts and spend real quota; read
`harness/RUNBOOK.md` and Section VIII of the article first.

## License

MIT, see `LICENSE`.
