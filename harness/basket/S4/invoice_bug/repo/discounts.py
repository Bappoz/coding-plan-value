def apply_bulk_discount(order, threshold_qty=10, flat_discount=15.0):
    total_qty = sum(qty for _, _, qty in order.items)
    if total_qty >= threshold_qty:
        return order.subtotal() - flat_discount
    return order.subtotal()
