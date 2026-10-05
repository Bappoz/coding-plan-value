class Cache:
    def __init__(self, max_size):
        self.max_size = max_size
        self._store = {}
        self._order = []

    def get(self, key):
        if key not in self._store:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._store[key]

    def set(self, key, value):
        if key not in self._store and len(self._store) >= self.max_size:
            lru_key = self._order.pop(0)
            del self._store[lru_key]
        self._store[key] = value
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)
