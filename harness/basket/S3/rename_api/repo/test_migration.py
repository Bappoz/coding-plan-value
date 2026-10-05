from pricing import calculate_discount
from checkout import total_after_discount
from reports import discount_report


def test_pricing_direct():
    assert calculate_discount(100, 10) == 90


def test_checkout_uses_new_name():
    assert total_after_discount(200, 25) == 150


def test_reports_uses_new_name():
    assert discount_report([(100, 10), (50, 0)]) == [90, 50]
