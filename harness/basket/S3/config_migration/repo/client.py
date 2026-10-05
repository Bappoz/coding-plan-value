from settings import load_config


def request_timeout(overrides=None):
    config = load_config(overrides)
    return config["timeout_ms"] / 1000
