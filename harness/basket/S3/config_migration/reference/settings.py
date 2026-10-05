DEFAULT_CONFIG = {
    "timeout_seconds": 5.0,
    "retries": 3,
}


def load_config(overrides=None):
    config = dict(DEFAULT_CONFIG)
    if overrides:
        config.update(overrides)
    return config
