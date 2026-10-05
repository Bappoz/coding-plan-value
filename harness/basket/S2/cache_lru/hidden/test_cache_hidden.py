from cache import Cache


def test_evicts_least_recently_used():
    c = Cache(max_size=2)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")  # "a" becomes most-recently-used
    c.set("c", 3)  # should evict "b", not "a"
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_no_eviction_below_capacity():
    c = Cache(max_size=3)
    c.set("x", 1)
    c.set("y", 2)
    assert c.get("x") == 1
    assert c.get("y") == 2
