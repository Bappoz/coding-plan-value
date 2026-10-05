from settings import load_config
from client import request_timeout
from worker import poll_interval


def test_config_uses_seconds_key():
    config = load_config()
    assert "timeout_seconds" in config
    assert "timeout_ms" not in config
    assert config["timeout_seconds"] == 5.0


def test_client_timeout_no_longer_divides():
    assert request_timeout() == 5.0


def test_worker_poll_interval_halved():
    assert poll_interval() == 2.5


def test_override_uses_new_key():
    assert request_timeout({"timeout_seconds": 10.0}) == 10.0
