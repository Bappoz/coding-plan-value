Cache.set() does not evict anything when the cache is full (see the TODO
comment in cache.py). Implement least-recently-used (LRU) eviction: when
set() is called with a new key and the cache is already at max_size, evict
the least-recently-used key before inserting. get() already tracks recency
via self._order. Add your own tests covering this behaviour.
