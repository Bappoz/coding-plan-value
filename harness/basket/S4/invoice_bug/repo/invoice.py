from discounts import apply_bulk_discount


def generate_invoice(order, tax_pct=8):
    amount = apply_bulk_discount(order)
    tax = amount * tax_pct / 100
    return round(amount + tax, 2)
