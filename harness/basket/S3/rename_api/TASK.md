This repo still uses the old function name `calc_disc` in pricing.py,
checkout.py, and reports.py. Rename it to `calculate_discount` everywhere
(definition and all call sites) so the test suite, which already expects
the new name, passes. Do not change the tests, and do not leave any
reference to the old name `calc_disc` anywhere in the repo.
