This repo still stores its timeout as `timeout_ms` (milliseconds) in
settings.py, used by client.py and worker.py. Migrate it to a
`timeout_seconds` key (seconds, not milliseconds) everywhere: the config
default, and every place that reads the value. The test suite already
expects the new key and unit. Do not change the tests, and do not leave any
reference to `timeout_ms` anywhere in the repo.
