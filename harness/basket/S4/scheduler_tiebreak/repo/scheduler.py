import heapq


class Scheduler:
    def __init__(self):
        self._heap = []

    def add(self, priority, name):
        heapq.heappush(self._heap, (priority, name))

    def next_job(self):
        if not self._heap:
            return None
        return heapq.heappop(self._heap)[1]
