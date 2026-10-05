from pricing import calculate_discount


def discount_report(items):
    return [calculate_discount(p, pct) for p, pct in items]
