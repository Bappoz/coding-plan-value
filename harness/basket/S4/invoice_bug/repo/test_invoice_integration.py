from order import Order
from invoice import generate_invoice


def test_bulk_order_invoice_matches_finance_policy():
    order = Order([("widget", 10.0, 12)])
    # finance policy: VAT is computed on the pre-discount subtotal; the flat
    # bulk discount is subtracted from the invoice AFTER tax, not before.
    assert generate_invoice(order) == 114.6
