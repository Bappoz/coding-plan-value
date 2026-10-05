from settings import load_config


def poll_interval(overrides=None):
    config = load_config(overrides)
    return config["timeout_seconds"] / 2
