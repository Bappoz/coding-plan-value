from order import Order
from invoice import generate_invoice


def test_small_order_no_discount():
    order = Order([("gadget", 20.0, 2)])  # below the bulk threshold
    assert generate_invoice(order) == 43.2
