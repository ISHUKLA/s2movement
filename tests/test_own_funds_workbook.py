"""R-010/R-016–R-018 recalculate legal conclusions and adjustment effects."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from test_slice import _formula_results, _recalculate, _run_cli
from test_tp_bridges import PACKAGES


def test_R018_tier_formulas_and_status_changes_recalculate(tmp_path: Path) -> None:
    package = PACKAGES / "5"
    result = tmp_path / "result"
    cli = _run_cli(package / "opening.xlsx", package / "closing.xlsx", result)
    assert cli.returncode == 0, cli.stderr
    report = json.loads((result / "summary.json").read_text())
    path = result / "reconciliation.xlsx"
    cached = _formula_results(path)
    fresh = _formula_results(_recalculate(path, tmp_path / "recalculated"))
    assert {k: v for k, v in cached.items() if k[0] == "Tier_limits"} == {
        k: v for k, v in fresh.items() if k[0] == "Tier_limits"
    }
    closing = next(
        t for t in report["tier_limits"] if t["id"] == "closing_article82_1_b"
    )
    assert closing["status"] == "binding"
    assert closing["effect_on_eligible"]["value"] == "-14000000"
    assert closing["operator"] == "<" and "82(1)(b)" in closing["formula_notes"]

    book = load_workbook(path)
    try:
        # Restore all available Tier 3 to eligibility and provide sufficient SCR.
        # The tier calculation reads S.23 and stays independent of S.25 detail.
        raw = book["Raw_closing"]
        for row in raw.iter_rows(min_row=2):
            if row[2].value == "S.23.01.01.01":
                if (row[3].value, row[4].value) == ("R0580", "C0010"):
                    row[12].value = 300_000_000
                if (row[3].value, row[4].value) == ("R0540", "C0050"):
                    row[12].value = 32_000_000
        edited = tmp_path / "edited.xlsx"
        book.save(edited)
    finally:
        book.close()
    revised = load_workbook(_recalculate(edited, tmp_path / "updated"), data_only=True)
    try:
        rows = {r[0]: r for r in revised["Tier_limits"].values if r[0]}
        assert rows["closing_article82_1_b"][1] == "not_binding"
        assert rows["closing_article82_1_b"][11] == 0
        assert rows["article82_1_b"][3] == "unchanged"
        assert rows["article82_1_b"][5] == 0
        assert rows["closing_article82_3"][1] == "indeterminate"
    finally:
        revised.close()


def test_R018_strict_equality_stays_visible_in_excel(tmp_path: Path) -> None:
    package = PACKAGES / "5"
    result = tmp_path / "result"
    cli = _run_cli(package / "opening.xlsx", package / "closing.xlsx", result)
    assert cli.returncode == 0, cli.stderr
    book = load_workbook(result / "reconciliation.xlsx")
    try:
        for row in book["Raw_closing"].iter_rows(min_row=2):
            if row[2].value == "S.23.01.01.01" and (row[3].value, row[4].value) == (
                "R0580",
                "C0010",
            ):
                row[12].value = 120_000_000
        edited = tmp_path / "equality.xlsx"
        book.save(edited)
    finally:
        book.close()
    values = load_workbook(_recalculate(edited, tmp_path / "updated"), data_only=True)
    try:
        rows = {r[0]: r for r in values["Tier_limits"].values if r[0]}
        assessment = rows["closing_article82_1_b"]
        assert assessment[3] == assessment[6] == 18_000_000
        assert assessment[10] == "fail"  # The mapped strict bound rejects equality.
        assert assessment[1] == "indeterminate"
        assert str(assessment[11]).startswith("Indeterminate")
        assert rows["article82_1_b"][3] == "became_indeterminate"
        assert str(rows["article82_1_b"][5]).startswith("Indeterminate")
        assert Decimal(str(assessment[7])) == 0
    finally:
        values.close()
