class Order:
    def __init__(self, items):
        self.items = items  # list of (name, unit_price, qty)

    def subtotal(self):
        return sum(price * qty for _, price, qty in self.items)
