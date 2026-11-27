"""R-010–R-015 exercise TP outputs through the CLI and a real formula engine."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook
from test_slice import _formula_results, _recalculate, _run_cli
from test_tp_bridges import PACKAGES

from s2movement.engine import analyze
from s2movement.normalized import load_ledger
from s2movement.output import summary_data


@pytest.fixture(autouse=True)
def benchmark_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(PACKAGES.parent))


def change(base: Path, destination: Path, declaration: dict[str, Any]) -> None:
    # Pytest collects the independent helper's directory on its import path.
    importlib.import_module("bench_mutate").mutate(base, destination, declaration)


@pytest.mark.parametrize("period", ("opening", "closing"))
@pytest.mark.parametrize("template", ("S.12.01", "S.22.01"))
def test_R007_R012_R014_missing_detail_is_named(
    tmp_path: Path,
    period: str,
    template: str,
) -> None:
    variant = tmp_path / "variant"
    change(
        PACKAGES / "1",
        variant,
        {
            "operation": "remove-template",
            "period": period,
            "template": template,
        },
    )
    result = analyze(load_ledger(variant / "opening.xlsx", variant / "closing.xlsx"))
    for schedule in result.schedules:
        affected = (
            schedule.bridge_id in ("life_net_tp", "health_slt_net_tp")
            if template == "S.12.01"
            else schedule.category == "ltg_scenario"
        )
        if affected:
            assert schedule.movement.status == "unavailable"
            assert schedule.movement.missing_template == template
            assert schedule.movement.missing_period == period
            assert getattr(schedule, period).status == "unavailable"
    if template == "S.22.01":
        assert all(b.status == "pass" for b in result.bridges)
    report = summary_data(result)
    assert report["linked_pairing"]["difference_ids"]


def test_R010_R012_R015_recalculation_and_live_pairing(tmp_path: Path) -> None:
    result = tmp_path / "result"
    source = PACKAGES / "4"
    cli = _run_cli(source / "opening.xlsx", source / "closing.xlsx", result)
    assert cli.returncode == 0, cli.stderr
    path = result / "reconciliation.xlsx"
    report = json.loads((result / "summary.json").read_text())
    before = _formula_results(path)
    fresh = _formula_results(_recalculate(path, tmp_path / "recalculated"))
    sheets = {"life_net_tp", "health_slt_net_tp", "Schedules", "Linked_pairing"}
    assert {k: v for k, v in before.items() if k[0] in sheets} == {
        k: v for k, v in fresh.items() if k[0] in sheets
    }
    # All components, net subtotal and the scenario schedule appear beside each bridge.
    workbook = load_workbook(path)
    try:
        for name in ("life_net_tp", "health_slt_net_tp"):
            labels = [row[10].value for row in workbook[name].iter_rows()]
            assert "Net best estimate — subtotal" in labels
            assert "S.22.01 undertaking TP scenarios" in labels
        raw = workbook["Raw_closing"]
        row = next(
            r
            for r in raw.iter_rows(min_row=2)
            if r[2].value == "S.02.01.01.01" and r[3].value == "R0220"
        )
        row[12].value = int(str(row[12].value)) + 17
        edited = tmp_path / "edited.xlsx"
        workbook.save(edited)
    finally:
        workbook.close()
    updated = _formula_results(_recalculate(edited, tmp_path / "updated"))
    for schedule in report["schedules"]:
        location = schedule["movement"]["excel"]
        key = location["sheet"], location["cell"]
        expected_change = (
            17
            if (
                schedule["id"] == "linked/R0220"
                or schedule["category"]
                in ("movement_difference", "linked_aggregate_difference")
            )
            else 0
        )
        assert updated[key] == before[key] + expected_change
    assert updated["Linked_pairing", "B2"] == "material"


def test_R010_R014_unavailable_scenario_recalculates_as_text(tmp_path: Path) -> None:
    variant = tmp_path / "variant"
    change(
        PACKAGES / "1",
        variant,
        {
            "operation": "remove-template",
            "period": "closing",
            "template": "S.22.01",
        },
    )
    result = tmp_path / "result"
    cli = _run_cli(variant / "opening.xlsx", variant / "closing.xlsx", result)
    assert cli.returncode == 0, cli.stderr
    path = result / "reconciliation.xlsx"
    before = _formula_results(path)
    after = _formula_results(_recalculate(path, tmp_path / "recalculated"))
    for key, value in before.items():
        if key[0] in ("life_net_tp", "health_slt_net_tp", "Schedules"):
            assert value == after[key]
    assert any(
        "Unavailable" in str(v) and "closing" in str(v) and "S.22.01" in str(v)
        for k, v in after.items()
        if k[0] == "life_net_tp"
    )
