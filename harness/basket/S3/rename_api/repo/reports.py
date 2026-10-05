from pricing import calc_disc


def discount_report(items):
    return [calc_disc(p, pct) for p, pct in items]
