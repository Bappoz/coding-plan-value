class TodoList:
    def __init__(self):
        self._items = {}
        self._next_id = 1

    def add(self, text):
        item_id = self._next_id
        self._items[item_id] = {"text": text, "done": False}
        self._next_id += 1
        return item_id

    def get(self, item_id):
        return self._items.get(item_id)

    def pending(self):
        return [i for i, item in self._items.items() if not item["done"]]

    def mark_done(self, item_id):
        if item_id not in self._items:
            raise KeyError(item_id)
        self._items[item_id]["done"] = True
