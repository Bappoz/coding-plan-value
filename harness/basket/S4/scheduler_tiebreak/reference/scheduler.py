import heapq
import itertools


class Scheduler:
    def __init__(self):
        self._heap = []
        self._counter = itertools.count()

    def add(self, priority, name):
        heapq.heappush(self._heap, (priority, next(self._counter), name))

    def next_job(self):
        if not self._heap:
            return None
        return heapq.heappop(self._heap)[2]
