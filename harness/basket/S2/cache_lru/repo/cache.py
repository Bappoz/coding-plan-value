class Cache:
    def __init__(self, max_size):
        self.max_size = max_size
        self._store = {}
        self._order = []  # tracks access order, oldest first

    def get(self, key):
        if key not in self._store:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._store[key]

    def set(self, key, value):
        if key not in self._store and len(self._store) >= self.max_size:
            # TODO: evict the least-recently-used key before inserting
            pass
        self._store[key] = value
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)
