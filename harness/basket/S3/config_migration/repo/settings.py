DEFAULT_CONFIG = {
    "timeout_ms": 5000,
    "retries": 3,
}


def load_config(overrides=None):
    config = dict(DEFAULT_CONFIG)
    if overrides:
        config.update(overrides)
    return config
