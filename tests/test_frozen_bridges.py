"""R-009–R-022, R-032. Score the signed bridge amounts from the frozen answer keys."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from s2movement.engine import analyze
from s2movement.normalized import load_ledger
from s2movement.output import summary_data

PACKAGES = Path(__file__).parent / "fixtures" / "packages"


@pytest.mark.parametrize("case", ["1", "2a", "2b", "3", "4", "5"])
def test_R011_R012_R016_R017_R019_R020_R021_frozen_bridge_lines(case: str) -> None:
    package = PACKAGES / case
    expected = json.loads((package / "expected.yaml").read_text(encoding="utf-8"))
    for run in expected["runs"]:
        confirmations = (
            package / "confirmations.json" if run["id"] == "02a-confirmed" else None
        )
        ledger = load_ledger(
            package / "opening.xlsx",
            package / "closing.xlsx",
            confirmation_path=confirmations,
        )
        summary = summary_data(analyze(ledger))
        bridges = {item["id"]: item for item in summary["bridges"]}
        assert set(bridges) == {item["id"] for item in run["bridges"]}
        for expected_bridge in run["bridges"]:
            bridge = bridges[expected_bridge["id"]]
            residual = bridge["residual_check"]
            assert residual["status"] == expected_bridge["residual_status"]
            if expected_bridge["tolerance"] is not None:
                assert Fraction(residual["tolerance"]["value"]) == Fraction(
                    expected_bridge["tolerance"]
                )
            lines = {item["id"]: item["result"] for item in bridge["lines"]}
            assert set(lines) == {item["id"] for item in expected_bridge["lines"]}
            for item in expected_bridge["lines"]:
                amount = lines[item["id"]]
                location = (run["id"], bridge["id"], item["id"])
                assert amount["status"] == item["status"], location
                if item["status"] == "value":
                    assert Fraction(amount["value"]) == Fraction(item["value"]), (
                        location
                    )
                    assert amount["citations"], location
                else:
                    assert amount["value"] is None, location
                    assert amount["period"] == item["period"], location
                    assert amount["missing_template"] == item["missing_template"], (
                        location
                    )
