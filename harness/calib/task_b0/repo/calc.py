def average(values):
    """Return the arithmetic mean of a non-empty list of numbers."""
    total = 0
    for v in values:
        total = total + v
    return total // len(values)
