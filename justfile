default: paper

# figuras + números derivados -> figures/*.pdf, figures/derived.tex
figures:
    python3 scripts/figures.py

# build completo (figuras -> pdflatex -> bibtex -> pdflatex x2)
paper:
    bash scripts/build.sh

# só o LaTeX, sem regerar figuras
tex:
    pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null && \
    bibtex main >/dev/null && \
    pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null && \
    pdflatex -interaction=nonstopmode -halt-on-error main.tex | tail -2

# avisos que importam (overfull, refs indefinidas, citações faltando)
lint:
    @grep -nE "Overfull|undefined|LaTeX Warning: (Citation|Reference)" main.log || echo "clean"

view:
    xdg-open main.pdf

clean:
    rm -f main.aux main.bbl main.blg main.log main.out main.pdf

# --- Planmeter harness (harness/) — see harness/RUNBOOK.md ---

# pure-logic modules against synthetic data, zero vendor calls
harness-selftest:
    python3 -m harness.selftest

# one real call: verify claude_code.py's JSON field paths before trusting them
harness-selfcheck plan="claude-code" arm="frozen":
    python3 -m harness.runner selfcheck --plan {{plan}} --arm {{arm}}

# entitlement saturation probe (Algorithm 1) — low duty cycle by default
harness-probe plan="claude-code" arm="as-delivered":
    python3 -m harness.runner probe --plan {{plan}} --arm {{arm}}

# offline: every basket task's bug is reproducible and its fix is recognised
harness-verify-basket:
    python3 -m harness.verify_basket

# rebuild the published pilot snapshot from the (private) raw JSONL logs
summarize-pilot:
    python3 scripts/summarize_pilot.py

# publishable aggregate of the Codex basket run (tokens, not USD)
summarize-codex:
    python3 scripts/summarize_codex.py

# feed every logged b0 cycle through the CUSUM drift canary (Section V-H)
harness-canary plan="claude-code" p0="0.95":
    python3 -m harness.runner canary --plan {{plan}} --p0 {{p0}}
