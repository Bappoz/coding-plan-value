import pathlib


def test_no_leftover_timeout_ms():
    repo_root = pathlib.Path(__file__).parent
    checked = ["settings.py", "client.py", "worker.py"]
    hits = [f for f in checked if "timeout_ms" in (repo_root / f).read_text()]
    assert not hits, f"old key still referenced in: {hits}"
