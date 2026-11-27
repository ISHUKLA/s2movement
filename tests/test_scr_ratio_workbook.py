"""R-010/R-019–R-021 exercise the CLI and real LibreOffice recalculation."""

from __future__ import annotations

import json
import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook
from test_slice import _formula_results, _recalculate, _run_cli
from test_tp_bridges import PACKAGES
from test_tp_workbook import change


@pytest.fixture(autouse=True)
def benchmark_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(PACKAGES.parent))


def _mutated_ratio_pair(tmp_path: Path, e1: int, s1: int) -> Path:
    base = PACKAGES / "1"
    for period, eligible, scr in (("opening", 114, 48), ("closing", e1, s1)):
        for row, value in (
            ("R0540", eligible),
            ("R0580", scr),
            ("R0620", str(round(Decimal(eligible) / Decimal(scr), 4))),
        ):
            variant = tmp_path / f"{period}-{row}"
            change(
                base,
                variant,
                {
                    "operation": "alter-cell",
                    "period": period,
                    "table": "S.23.01.01.01",
                    "row": row,
                    "column": "C0010",
                    "value": value,
                },
            )
            base = variant
    return base


def _ratio_lines(report: dict[str, Any]) -> dict[str, Any]:
    return {
        line["id"]: line
        for bridge in report["bridges"]
        if bridge["id"] == "solvency_ratio"
        for line in bridge["lines"]
    }


@pytest.mark.parametrize("e1,s1", ((130, 51), (130, 48), (114, 51), (114, 48)))
def test_R021_D5_four_situations_recalculate_exact_terms(
    tmp_path: Path, e1: int, s1: int
) -> None:
    source = _mutated_ratio_pair(tmp_path, e1, s1)
    output = tmp_path / "result"
    cli = _run_cli(source / "opening.xlsx", source / "closing.xlsx", output)
    # The declared mutations leave unrelated SCR and own-fund reconciliations broken.
    assert cli.returncode == 1, cli.stderr
    report = json.loads((output / "summary.json").read_text())
    assert all(v["status"] == "pass" for v in report["ratio_validations"])
    assert all(
        c["status"] == "pass"
        for c in report["comparisons"]
        if c["id"].endswith("_ratio")
    )
    ratio = next(b for b in report["bridges"] if b["id"] == "solvency_ratio")
    assert ratio["status"] == "pass"
    notes = " ".join(ratio["formula_notes"])
    assert "D5" in notes and "Interaction" in notes and "percentage points" in notes
    wanted = {
        "opening": 100 * Fraction(114, 48),
        "closing": 100 * Fraction(e1, s1),
        "own_funds": 100 * Fraction(e1 - 114, 48),
        "scr": 100 * 114 * (Fraction(1, s1) - Fraction(1, 48)),
        "interaction": 100 * (e1 - 114) * (Fraction(1, s1) - Fraction(1, 48)),
        "residual": Fraction(0),
    }
    original = output / "reconciliation.xlsx"
    fresh_path = _recalculate(original, tmp_path / "fresh")
    fresh = _formula_results(
        fresh_path
    )  # No formula anywhere may become an Excel error.
    workbook = load_workbook(original)
    try:
        for line in ratio["lines"]:
            value = line["result"]
            expected = wanted[line["id"]]
            assert Fraction(value["value"]) == expected
            assert value["unit"]["kind"] == "percentage_points"
            assert value["citations"]
            loc = value["excel"]
            cell = workbook[loc["sheet"]][loc["cell"]]
            assert cell.data_type == "f" and cell.number_format == "0.000000"
            assert "ROUND(" not in str(cell.value)
            actual = fresh[loc["sheet"], loc["cell"]]
            if expected == 0:
                assert actual == 0
            else:
                assert math.isclose(
                    float(actual), float(expected), rel_tol=1e-14, abs_tol=1e-10
                )
        assert fresh["solvency_ratio", "D9"] == "pass"
        assert any(
            "Formula notes" == c.value
            for row in workbook["solvency_ratio"]
            for c in row
        )
    finally:
        workbook.close()


@pytest.mark.parametrize("period", ("opening", "closing"))
@pytest.mark.parametrize("scr", (None, 0, -1))
def test_R021_missing_or_nonpositive_scr_is_a_cited_validation_failure(
    tmp_path: Path, period: str, scr: int | None
) -> None:
    source = tmp_path / "pair"
    change(
        PACKAGES / "1",
        source,
        {
            "operation": "alter-cell",
            "period": period,
            "table": "S.23.01.01.01",
            "row": "R0580",
            "column": "C0010",
            "value": scr,
        },
    )
    output = tmp_path / "result"
    cli = _run_cli(source / "opening.xlsx", source / "closing.xlsx", output)
    assert cli.returncode == 1, cli.stderr
    assert f"Validation failure ({period}_ratio_scr_positive)" in cli.stdout
    report = json.loads((output / "summary.json").read_text())
    validation = next(v for v in report["ratio_validations"] if v["period"] == period)
    assert validation["status"] == "fail" and validation["citations"]
    assert validation["input"]["value"] == (None if scr is None else str(scr))
    assert "S.23.01 R0580/C0010" in validation["message"]
    assert "source evidence" in validation["message"]
    original = output / "reconciliation.xlsx"
    cached = _formula_results(original)
    fresh = _formula_results(_recalculate(original, tmp_path / "fresh"))
    for line in _ratio_lines(report).values():
        amount = line["result"]
        assert amount["value"] is None and amount["status"] == "withheld"
        assert "Validation failure" in amount["reason"]
        assert f"{period}_ratio_scr_positive" in amount["reason"]
        loc = amount["excel"]
        observed = fresh[loc["sheet"], loc["cell"]]
        assert observed == cached[loc["sheet"], loc["cell"]]
        assert "Withheld: Validation failure" in observed
    loc = validation["input"]["excel"]
    row = loc["cell"][1:]
    assert fresh["Summary", f"B{row}"] == "fail"


@pytest.mark.parametrize("period", ("opening", "closing"))
def test_R010_R021_raw_scr_edit_to_zero_withholds_without_division_error(
    tmp_path: Path, period: str
) -> None:
    source = PACKAGES / "1"
    output = tmp_path / "result"
    cli = _run_cli(source / "opening.xlsx", source / "closing.xlsx", output)
    assert cli.returncode == 0, cli.stderr
    report = json.loads((output / "summary.json").read_text())
    workbook = load_workbook(output / "reconciliation.xlsx")
    edited = tmp_path / "zero.xlsx"
    try:
        raw = workbook[f"Raw_{period}"]
        target = next(
            r[12]
            for r in raw
            if r[2].value == "S.23.01.01.01"
            and r[3].value == "R0580"
            and r[4].value == "C0010"
        )
        target.value = 0
        workbook.save(edited)
    finally:
        workbook.close()
    fresh = _formula_results(_recalculate(edited, tmp_path / "fresh"))
    for line in _ratio_lines(report).values():
        loc = line["result"]["excel"]
        value = fresh[loc["sheet"], loc["cell"]]
        assert "Withheld: Validation failure" in value
        assert f"{period}_ratio_scr_positive" in value
    assert fresh["solvency_ratio", "D9"] == "withheld"


@pytest.mark.parametrize("period", ("opening", "closing"))
def test_R019_R020_scr_workbook_retains_headline_without_modules(
    tmp_path: Path, period: str
) -> None:
    source = tmp_path / "pair"
    change(
        PACKAGES / "1",
        source,
        {
            "operation": "remove-template",
            "period": period,
            "template": "S.25.01",
        },
    )
    output = tmp_path / "result"
    cli = _run_cli(source / "opening.xlsx", source / "closing.xlsx", output)
    assert cli.returncode == 0, cli.stderr
    report = json.loads((output / "summary.json").read_text())
    fresh = _formula_results(
        _recalculate(output / "reconciliation.xlsx", tmp_path / "fresh")
    )
    for bridge in report["bridges"]:
        if bridge["id"] not in {"scr_modules", "headline_scr"}:
            continue
        for line in bridge["lines"]:
            value = line["result"]
            loc = value["excel"]
            observed = fresh[loc["sheet"], loc["cell"]]
            if value["status"] == "value":
                assert observed == Fraction(value["value"])
            else:
                assert "Unavailable" in observed and "S.25.01" in observed
                assert period in observed


def test_R010_R011_R019_gross_modules_signed_LAC_and_visible_break(
    tmp_path: Path,
) -> None:
    source = PACKAGES / "1"
    output = tmp_path / "result"
    cli = _run_cli(source / "opening.xlsx", source / "closing.xlsx", output)
    assert cli.returncode == 0, cli.stderr
    report = json.loads((output / "summary.json").read_text())
    bridge = next(b for b in report["bridges"] if b["id"] == "scr_modules")
    workbook = load_workbook(output / "reconciliation.xlsx")
    broken, tied = tmp_path / "broken.xlsx", tmp_path / "tied.xlsx"
    try:
        cells = {
            (str(r[2].value), str(r[3].value), str(r[4].value)): r[12]
            for r in workbook["Raw_closing"].iter_rows(min_row=2)
        }
        market = cells["S.25.01.01.01", "R0010", "C0040"]
        market.value = int(str(market.value)) + 30
        workbook.save(broken)
        lac_tp = cells["S.25.01.01.02", "R0140", "C0100"]
        lac_tp.value = int(str(lac_tp.value)) - 11
        for table, row, col in (
            ("S.23.01.01.01", "R0580", "C0010"),
            ("S.25.01.01.02", "R0220", "C0100"),
        ):
            scr = cells[table, row, col]
            scr.value = int(str(scr.value)) + 19
        # Preserve the reported-ratio comparison after the declared SCR edit.
        funds = Decimal(str(cells["S.23.01.01.01", "R0540", "C0010"].value))
        total = Decimal(str(cells["S.23.01.01.01", "R0580", "C0010"].value))
        cells["S.23.01.01.01", "R0620", "C0010"].value = float(round(funds / total, 4))
        workbook.save(tied)
    finally:
        workbook.close()
    for path, deltas, status in (
        (broken, {"market": 30, "residual": -30}, "fail"),
        (tied, {"market": 30, "lac_tp": -11, "closing": 19}, "pass"),
    ):
        fresh = _formula_results(_recalculate(path, tmp_path / path.stem))
        for line in bridge["lines"]:
            amount = line["result"]
            loc = amount["excel"]
            expected = Fraction(amount["value"]) + deltas.get(line["id"], 0)
            assert fresh[loc["sheet"], loc["cell"]] == expected
            if line["id"] == "residual":
                assert fresh[loc["sheet"], "D" + loc["cell"][1:]] == status
