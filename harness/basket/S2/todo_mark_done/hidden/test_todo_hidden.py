import pytest

from todo import TodoList


def test_mark_done_updates_pending():
    t = TodoList()
    a = t.add("buy milk")
    b = t.add("write report")
    t.mark_done(a)
    assert t.get(a)["done"] is True
    assert b in t.pending()
    assert a not in t.pending()


def test_mark_done_unknown_id_raises():
    t = TodoList()
    with pytest.raises(KeyError):
        t.mark_done(999)
