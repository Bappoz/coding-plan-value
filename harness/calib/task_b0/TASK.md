# b0 — frozen calibration task

**Do not edit after the first epoch is run.** This task's only job is to
give `NQU` a fixed, reproducible unit of consumption (Definition in
main.tex §III) and a stable token/latency baseline. It is deliberately
trivial (S1-shape, single file, one obvious bug) — it is not meant to be
hard, it is meant to be *identical every time it runs*.

## Prompt (verbatim — pass this string to the client under test)

    There is a failing test in this repo. Run the tests, find the bug in
    calc.py, fix it, and make the tests pass. Do not change the tests.

## Bug

`average()` uses integer floor division (`//`) instead of true division
(`/`), so `average([1, 2])` returns `1` instead of `1.5`.

## Oracle

`pytest -q` inside `repo/` exits 0 iff both tests pass.
