import pathlib


def test_no_leftover_calc_disc():
    repo_root = pathlib.Path(__file__).parent
    checked = ["pricing.py", "checkout.py", "reports.py"]
    hits = [f for f in checked if "calc_disc" in (repo_root / f).read_text()]
    assert not hits, f"old name still referenced in: {hits}"
