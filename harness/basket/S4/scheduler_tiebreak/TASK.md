Scheduler must dispatch jobs by priority (lower number = higher priority),
and among jobs with the SAME priority, in the order they were added (FIFO).
There is a failing integration test (test_scheduler_integration.py) showing
a case where two equal-priority jobs come out in the wrong order. Find the
root cause and fix it, making the test pass. Do not change the test.
