"""CLI smoke test: ingest fixtures then render a digest to a file."""
from pathlib import Path

from churn_radar.__main__ import main

REPO = Path(__file__).resolve().parent.parent


def test_cli_end_to_end(tmp_path: Path) -> None:
    db = tmp_path / "cli.db"
    out = tmp_path / "digest.md"
    assert main(["ingest", "--usage", str(REPO / "fixtures" / "usage.csv"),
                 "--tickets", str(REPO / "fixtures" / "tickets.csv"),
                 "--db", str(db)]) == 0
    assert main(["digest", "--db", str(db), "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("*Churn Signal Radar*")
    assert "Globex Inc" in text
    assert "_Save motion:_" in text
    assert "_Why:_" in text
