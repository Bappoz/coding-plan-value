from scheduler import Scheduler


def test_fifo_tiebreak_for_equal_priority():
    s = Scheduler()
    s.add(1, "zeta")
    s.add(1, "alpha")
    # both priority 1; "zeta" was added first, so it must come out first
    assert s.next_job() == "zeta"
    assert s.next_job() == "alpha"
