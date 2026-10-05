Customer complaint: "For bulk orders (10+ units) my invoice total looks
wrong. Our finance policy is that VAT is computed on the pre-discount
subtotal, and only then is the bulk discount subtracted from the taxed
amount — but the numbers I'm seeing don't match that."

There is a failing integration test (test_invoice_integration.py) that
reproduces the discrepancy with a concrete example. Find the root cause —
it isn't necessarily in the file you'd first guess — fix it, and make the
test pass. Do not change the test.
