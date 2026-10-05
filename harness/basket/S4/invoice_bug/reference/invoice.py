from discounts import apply_bulk_discount


def generate_invoice(order, tax_pct=8):
    subtotal = order.subtotal()
    discount_amount = subtotal - apply_bulk_discount(order)
    tax = subtotal * tax_pct / 100
    return round(subtotal + tax - discount_amount, 2)
