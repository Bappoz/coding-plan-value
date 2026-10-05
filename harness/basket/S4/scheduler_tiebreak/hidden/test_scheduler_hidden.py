from scheduler import Scheduler


def test_priority_still_wins_over_order():
    s = Scheduler()
    s.add(5, "low_priority_first")
    s.add(1, "high_priority_second")
    assert s.next_job() == "high_priority_second"
    assert s.next_job() == "low_priority_first"
