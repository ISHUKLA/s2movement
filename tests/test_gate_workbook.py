"""Exercise the gate dashboard and its live formulas on the frozen normalized inputs."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_slice import ROOT, _recalculate, _run_cli


@pytest.mark.parametrize("delta", ("-0.00010001", "-0.0001", "0.0001", "0.00010001"))
def test_r008_d3_reported_ratio_at_each_inclusive_boundary(
    tmp_path: Path, delta: str
) -> None:
    package = ROOT / "tests" / "fixtures" / "packages" / "1"
    key = json.loads((package / "expected.yaml").read_text())
    check = next(c for c in key["runs"][0]["comparisons"] if c["id"] == "closing_ratio")
    computed = Fraction(check["right"]["value"])
    value = Decimal(computed.numerator) / Decimal(computed.denominator) + Decimal(delta)
    change = {
        "period": "closing",
        "operation": "alter-cell",
        "table": "S.23.01.01.01",
        "row": "R0620",
        "column": "C0010",
        "value": str(value),
    }
    declaration = tmp_path / "change.json"
    declaration.write_text(json.dumps(change))
    pair = tmp_path / "pair"
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "tests/fixtures/bench_mutate.py"),
            str(package),
            str(pair),
            str(declaration),
        ],
        check=True,
    )
    result = tmp_path / "result"
    run = _run_cli(pair / "opening.xlsx", pair / "closing.xlsx", result)
    expected = "pass" if abs(Decimal(delta)) <= Decimal("0.0001") else "fail"
    assert run.returncode == (0 if expected == "pass" else 1), run.stderr
    summary = json.loads((result / "summary.json").read_text())
    measured = next(c for c in summary["comparisons"] if c["id"] == "closing_ratio")
    assert measured["status"] == expected
    assert Fraction(measured["signed_discrepancy"]["value"]) == Fraction(delta)
    assert Fraction(measured["tolerance"]["value"]) == Fraction(1, 10000)
    assert summary["bridges"][0]["status"] == "pass"
    assert any(
        d["dependency"] == "solvency_ratio" and d["status"] == "withheld"
        for d in summary["affected_detail"]
    ) == (expected == "fail")
    path = _recalculate(result / "reconciliation.xlsx", tmp_path / "recalculated")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        assert workbook.sheetnames[0] == "Summary"
        values = next(
            row for row in workbook["Summary"].values if row[0] == "closing_ratio"
        )
        assert values[1] == expected
        assert math.isclose(float(str(values[6])), float(delta), abs_tol=2e-15)
        assert float(str(values[7])) == 0.0001
    finally:
        workbook.close()


def test_r010_r021_all_bridge_outputs_recalculate_and_ratio_reacts(
    tmp_path: Path,
) -> None:
    package = ROOT / "tests/fixtures/packages/5"
    result = tmp_path / "result"
    cli = _run_cli(package / "opening.xlsx", package / "closing.xlsx", result)
    assert cli.returncode == 0, cli.stderr
    report = json.loads((result / "summary.json").read_text())
    path = result / "reconciliation.xlsx"
    calculated = _recalculate(path, tmp_path / "baseline")
    wb = load_workbook(calculated, data_only=True)
    try:
        assert len(report["bridges"]) == 9
        for bridge in report["bridges"]:
            for line in bridge["lines"]:
                value = line["result"]
                loc = value["excel"]
                observed = wb[loc["sheet"]][loc["cell"]].value
                wanted = Fraction(value["value"])
                if value["unit"]["kind"] == "money" or wanted == 0:
                    assert observed == wanted, (
                        bridge["id"],
                        line["id"],
                        observed,
                        wanted,
                    )
                else:
                    assert math.isclose(
                        float(str(observed)), float(wanted), rel_tol=1e-14
                    )
            assert bridge["residual_check"]["status"] == "pass"
        for schedule in report["schedules"]:
            for field in ("opening", "closing", "movement"):
                amount = schedule[field]
                loc = amount["excel"]
                assert wb[loc["sheet"]][loc["cell"]].value == Fraction(amount["value"])
    finally:
        wb.close()

    # Keep the two R-008 ratio operands consistent in a copy and edit only the
    # reported levels. D5's own-funds and interaction terms must both respond.
    change = load_workbook(path)
    try:
        raw = change["Raw_closing"]
        rows = {
            str(row[3].value): row[12]
            for row in raw.iter_rows(min_row=2)
            if row[2].value == "S.23.01.01.01" and row[4].value == "C0010"
        }
        eligible = int(str(rows["R0540"].value)) + 1_000_000
        scr = int(str(rows["R0580"].value))
        rows["R0540"].value = eligible
        inconsistent = tmp_path / "inconsistent.xlsx"
        change.save(inconsistent)
        rows["R0620"].value = float(round(Decimal(eligible) / Decimal(scr), 4))
        edited = tmp_path / "edited.xlsx"
        change.save(edited)
    finally:
        change.close()
    wb = load_workbook(_recalculate(edited, tmp_path / "updated"), data_only=True)
    try:
        ratio = next(b for b in report["bridges"] if b["id"] == "solvency_ratio")
        for line in ratio["lines"]:
            amount = line["result"]
            loc = amount["excel"]
            fresh = wb[loc["sheet"]][loc["cell"]].value
            previous = Fraction(amount["value"])
            if line["id"] == "own_funds":
                assert math.isclose(
                    float(str(fresh)), float(previous + 1), rel_tol=1e-14
                )
            elif line["id"] == "interaction":
                added = 100_000_000 * (Fraction(1, scr) - Fraction(1, 100_000_000))
                assert math.isclose(
                    float(str(fresh)), float(previous + added), rel_tol=1e-14
                )
            elif line["id"] == "residual":
                assert fresh == 0 and wb[loc["sheet"]]["D9"].value == "pass"
    finally:
        wb.close()

    # Editing only eligible funds changes the cached comparison to a live failure.
    wb = load_workbook(_recalculate(inconsistent, tmp_path / "failed"), data_only=True)
    try:
        ratio_rows = list(wb["solvency_ratio"].values)
        for line in ratio_rows:
            if line[0] in ("own_funds", "scr", "interaction", "residual"):
                assert line[3] == "withheld"
                assert "closing_ratio" in str(line[2])
                assert "opening_ratio" not in str(line[2])
        assert (
            next(row[3] for row in wb["headline_scr"].values if row[0] == "residual")
            == "pass"
        )
    finally:
        wb.close()
