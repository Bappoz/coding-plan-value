#!/usr/bin/env bash
# Build the paper. pdflatex -> bibtex -> pdflatex x2 (no latexmk on this box).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/figures.py > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
bibtex main > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex | tail -3
echo "pages: $(pdfinfo main.pdf 2>/dev/null | awk '/^Pages/{print $2}')"
