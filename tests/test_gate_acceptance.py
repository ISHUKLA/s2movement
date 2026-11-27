"""Gate acceptance on one-declaration variants of the frozen benchmark."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from s2movement.engine import Analysis, analyze
from s2movement.models import Period
from s2movement.normalized import load_ledger
from s2movement.output import summary_data

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = FIXTURES / "packages/1"
PERIODS = ("opening", "closing")
type Mutation = Callable[[Path, Path, dict[str, Any]], None]


@pytest.fixture
def mutate(monkeypatch: pytest.MonkeyPatch) -> Mutation:
    # Import only the public mutation helper from Step 4.
    monkeypatch.syspath_prepend(str(FIXTURES))
    fn: Mutation = importlib.import_module("bench_mutate").mutate
    return fn


@pytest.fixture(scope="module")
def header_only(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("header_only")
    for period in PERIODS:
        name = f"{period}.xlsx"
        book = load_workbook(CLEAN / name)
        # Use normalized header evidence alone so one changed flag is a genuine
        # change of reporting basis, rather than conflicting declarations.
        del book["S.01.02"]
        del book["S.01.01"]
        book.save(directory / name)
        book.close()
    return directory


def comparison(directory: Path, *, reverse: bool = False) -> Analysis:
    a, b = directory / "opening.xlsx", directory / "closing.xlsx"
    return analyze(load_ledger(b, a) if reverse else load_ledger(a, b))


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "field,value",
    [
        ("taxonomy_version", "2.8.0"),
        ("frequency", "quarterly"),
        ("perimeter", "group"),
        ("scr_method", "partial_internal_model"),
        ("scr_method", "full_internal_model"),
        ("lei", "999900DIFFERENT12345"),
        ("currency", "GBP"),
        ("money_unit_scale", "1000"),
    ],
)
def test_R002_R003_R005_scope_stop(
    tmp_path: Path,
    header_only: Path,
    mutate: Mutation,
    period: Period,
    field: str,
    value: str,
) -> None:
    dest = tmp_path / "one-change"
    mutate(
        header_only,
        dest,
        {
            "period": period,
            "operation": "alter-metadata",
            "field": field,
            "value": value,
        },
    )
    result = comparison(dest)
    stops = [item for item in result.gate.findings if item.status == "blocked"]
    assert result.gate.status == "blocked" and result.bridge.lines == ()
    assert any(
        value in item.message
        and period in item.message.lower()
        and any(c.period == period for c in item.citations)
        for item in stops
    )
    assert not result.comparisons and not summary_data(result)["bridges"]


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "family", ["S.02.01", "S.23.01", "S.12.01", "S.25.01", "S.05.01", "S.22.01"]
)
def test_R005_R007_one_missing_template(
    tmp_path: Path, mutate: Mutation, period: Period, family: str
) -> None:
    dest = tmp_path / "one-change"
    mutate(
        CLEAN,
        dest,
        {"period": period, "operation": "remove-template", "template": family},
    )
    analysis = comparison(dest)
    finding = next(f for f in analysis.gate.findings if f.missing_template == family)
    assert finding.period == period and family in finding.message and finding.citations
    if family in {"S.02.01", "S.23.01"}:
        assert finding.status == "blocked" and not analysis.bridge.lines
    else:
        assert finding.status == "warning" and analysis.bridge.status == "pass"
        detail = summary_data(analysis)["affected_detail"]
        assert any(
            d["missing_template"] == family
            and d["period"] == period
            and d["status"] == "unavailable"
            for d in detail
        )


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "field,change,expected",
    [
        ("taxonomy_variant", "nace_2_1_hotfix", "taxonomy_variant_changed"),
        ("va_applied", "yes", "va_status_changed"),
        ("ma_applied", "yes", "ma_status_changed"),
        ("tmir_applied", "yes", "tmir_status_changed"),
        ("tmtp_applied", "yes", "tmtp_status_changed"),
        ("rff_indicator", "yes", "rff_indicator_without_sr"),
        ("map_indicator", "yes", "map_indicator_without_sr"),
    ],
)
def test_R006_one_basis_change(
    tmp_path: Path,
    header_only: Path,
    mutate: Mutation,
    period: Period,
    field: str,
    change: str,
    expected: str,
) -> None:
    dest = tmp_path / "one-change"
    mutate(
        header_only,
        dest,
        {
            "period": period,
            "operation": "alter-metadata",
            "field": field,
            "value": change,
        },
    )
    result = comparison(dest)
    assert result.gate.status == "pass" and result.bridge.status == "pass"
    warnings = [f for f in result.gate.findings if f.status == "warning"]
    assert (
        len(warnings) == 1
        and warnings[0].id.endswith(expected)
        and warnings[0].citations
    )


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "measure,column",
    [("va", "C0070"), ("ma", "C0090"), ("tmir", "C0050"), ("tmtp", "C0030")],
)
def test_R006_shift_in_s22_independent_of_status(
    tmp_path: Path,
    mutate: Mutation,
    period: Period,
    measure: str,
    column: str,
) -> None:
    dest = tmp_path / "one-change"
    mutate(
        CLEAN,
        dest,
        {
            "operation": "alter-cell",
            "period": period,
            "table": "S.22.01.01.01",
            "row": "R0010",
            "column": column,
            "value": 16_000_000,
        },
    )
    result = comparison(dest)
    warnings = [f for f in result.gate.findings if f.status == "warning"]
    assert result.bridge.status == "pass"
    assert [w.id for w in warnings] == [measure + "_tp_impact_material_shift"]
    assert {c.period for c in warnings[0].citations} == set(PERIODS)


@cache
def clean_sources() -> dict[tuple[str, str, str, str], str]:
    key = json.loads((CLEAN / "expected.yaml").read_text())

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            if "source_sha256" in value and "reported_value" in value:
                result[
                    value["period"], value["table"], value["row"], value["column"]
                ] = value["reported_value"]
            else:
                for item in value.values():
                    collect(item)

    result: dict[tuple[str, str, str, str], str] = {}
    collect(key)
    return result


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "check,table,row,col,delta,direction",
    [
        ("excess_consistency", "S.23.01.01.02", "R0700", "C0060", "2", -1),
        ("health_slt_tp", "S.02.01.01.01", "R0610", "C0010", "2", 1),
        ("health_slt_recoverables", "S.02.01.01.01", "R0320", "C0010", "2", 1),
        ("linked_recoverables", "S.02.01.01.01", "R0340", "C0010", "2", 1),
        ("nonlinked_life_recoverables", "S.02.01.01.01", "R0330", "C0010", "2", 1),
        ("scr", "S.25.01.01.02", "R0220", "C0100", "2", -1),
        ("ratio", "S.23.01.01.01", "R0620", "C0010", "0.0002", 1),
    ],
)
def test_R008_one_reconciliation_failure(
    tmp_path: Path,
    mutate: Mutation,
    period: Period,
    check: str,
    table: str,
    row: str,
    col: str,
    delta: str,
    direction: int,
) -> None:
    base = Decimal(clean_sources()[period, table, row, col])
    dest = tmp_path / "one-change"
    mutate(
        CLEAN,
        dest,
        {
            "operation": "alter-cell",
            "period": period,
            "table": table,
            "row": row,
            "column": col,
            "value": str(base + Decimal(delta)),
        },
    )
    result = comparison(dest)
    broken = [c for c in result.comparisons if c.status == "fail"]
    assert len(broken) == 1
    c = broken[0]
    assert c.id == f"{period}_{check}" and c.tolerance is not None
    assert c.left.citations and c.right.citations and c.discrepancy.value is not None
    assert direction * c.discrepancy.value > c.tolerance.value
    assert "reconciliation failure" in c.message.lower()
    assert result.bridge.status == (
        "withheld" if check == "excess_consistency" else "pass"
    )
    if check == "ratio":
        assert "solvency_ratio" in c.withholds


def test_R001_reversed_frozen_pair() -> None:
    forward, reverse = comparison(CLEAN), comparison(CLEAN, reverse=True)
    assert not forward.ledger.supplied_reversed and reverse.ledger.supplied_reversed
    assert [i.file_id for i in reverse.ledger.inputs] == [
        "opening.xlsx",
        "closing.xlsx",
    ]
    assert (
        forward.bridge == reverse.bridge and forward.comparisons == reverse.comparisons
    )


@pytest.mark.parametrize(
    "period,date",
    [
        ("opening", "2025-12-31"),
        ("closing", "2024-12-31"),
        ("opening", "2023-12-31"),
        ("closing", "2026-12-31"),
    ],
)
def test_R001_date_stop_precedes_other_checks(
    tmp_path: Path,
    mutate: Mutation,
    period: Period,
    date: str,
) -> None:
    dest = tmp_path / "one-change"
    mutate(
        CLEAN,
        dest,
        {
            "period": period,
            "operation": "alter-metadata",
            "field": "reference_date",
            "value": date,
        },
    )
    analysis = comparison(dest)
    assert [f.id for f in analysis.gate.findings] == ["consecutive_annual_periods"]
    f = analysis.gate.findings[0]
    assert f.status == "blocked" and date in f.message
    assert {c.period for c in f.citations} == set(PERIODS)
    assert not analysis.bridge.lines and not analysis.comparisons


@pytest.fixture(scope="module")
def inventory_base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("variation_inventory")
    for period in PERIODS:
        name = f"{period}.xlsx"
        wb = load_workbook(CLEAN / name)
        ws = wb["S.01.01"]
        context = next(
            r[0].value
            for r in wb["Contexts"].iter_rows(min_row=2)
            if r[3].value == "{}"
        )
        ws.append([])
        for values in (
            ("table", "S.01.01.01.01"),
            ("context", context),
            ("row/column", "C0010"),
            *[(r, "not reported") for r in ("R0600", "R0610", "R0620", "R0630")],
        ):
            ws.append(values)
        wb.save(directory / name)
        wb.close()
    return directory


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "family,row",
    [
        ("S.29.01", "R0600"),
        ("S.29.02", "R0610"),
        ("S.29.03", "R0620"),
        ("S.29.04", "R0630"),
    ],
)
def test_R003_variation_template_is_listed_and_changes_no_value(
    tmp_path: Path,
    inventory_base: Path,
    mutate: Mutation,
    period: Period,
    family: str,
    row: str,
) -> None:
    dest = tmp_path / "one-change"
    mutate(
        inventory_base,
        dest,
        {
            "period": period,
            "operation": "alter-cell",
            "table": "S.01.01.01.01",
            "row": row,
            "column": "C0010",
            "value": "reported",
        },
    )
    result = comparison(dest)
    reference = comparison(CLEAN)
    assert [line.result.value for line in result.bridge.lines] == [
        line.result.value for line in reference.bridge.lines
    ]
    entries = summary_data(result)["present_not_used"]
    assert len(entries) == 1 and family in entries[0]["message"]
    assert entries[0]["period"] == period and entries[0]["citations"][0]["row"] == row


@pytest.mark.parametrize(
    "case,run_index",
    [("1", 0), ("2a", 0), ("2a", 1), ("2b", 0), ("3", 0), ("4", 0), ("5", 0)],
)
def test_R001_R008_R031_expected_benchmark_gate(case: str, run_index: int) -> None:
    package = FIXTURES / "packages" / case
    key = json.loads((package / "expected.yaml").read_text())["runs"][run_index]
    confirm = package / "confirmations.json" if key["id"] == "02a-confirmed" else None
    report = summary_data(
        analyze(
            load_ledger(
                package / "opening.xlsx",
                package / "closing.xlsx",
                confirmation_path=confirm,
            )
        )
    )
    warnings = [w["id"] for w in report["warnings"]]
    gate = report["gate"]
    status = "warn" if warnings and gate["status"] == "pass" else gate["status"]
    assert status == key["gate"]["status"]
    assert sorted(warnings) == sorted(key["gate"]["warnings"])
    assert sorted(gate["stops"]) == sorted(key["gate"]["stops"])
    if status == "blocked":
        assert report["bridges"] == [] and report["comparisons"] == []
    else:
        assert report["bridges"][0]["status"] == "pass"
        assert all(c["status"] != "fail" for c in report["comparisons"])
    if confirm:
        decision = gate["conversions"][0]
        assert decision["source_unit_scale"] == "1000" and decision["factor"] == "1000"
        assert decision["target_unit_scale"] == "1"
        assert decision["rerun_gate_status"] == "pass" and decision["converted_facts"]


@pytest.mark.parametrize(
    "indicator,member",
    [
        ("rff_indicator", "s2c_x96"),
        ("map_indicator", "s2c_x53"),
    ],
)
@pytest.mark.parametrize("period", PERIODS)
def test_R006_only_corresponding_sr_portfolio_clears_warning(
    tmp_path: Path,
    header_only: Path,
    mutate: Mutation,
    period: Period,
    indicator: str,
    member: str,
) -> None:
    dest = tmp_path / "variant"
    mutate(
        header_only,
        dest,
        {
            "period": period,
            "operation": "alter-metadata",
            "field": indicator,
            "value": "yes",
        },
    )
    path = dest / f"{period}.xlsx"
    wb = load_workbook(path)
    contexts = wb["Contexts"]
    _, lei, date, _ = next(contexts.iter_rows(min_row=2, max_row=2, values_only=True))
    sheet = wb.create_sheet("SR.25.01")
    # First context is the other portfolio. Finding it must not hide a warning.
    other = "s2c_x53" if member == "s2c_x96" else "s2c_x96"
    for step, kind in enumerate((other, member), 1):
        ctx = f"portfolio-{step}"
        dims = {"s2c_PO": kind, "s2c_FN": str(step), "s2c_AO": "s2c_x0"}
        contexts.append([ctx, lei, date, json.dumps(dims)])
        for row in (
            ["table", "SR.25.01.01.02"],
            ["context", ctx],
            ["row/column", "C0100"],
            ["R0130", 50],
            [],
        ):
            sheet.append(row)
        wb.save(path)
        a = comparison(dest)
        assert a.gate.status == "pass"
        assert any(
            f.id.endswith(f"{indicator}_without_sr") for f in a.gate.findings
        ) == (step == 1)
    wb.close()


@pytest.mark.parametrize("period", PERIODS)
def test_R003_pdf_writes_cited_stopped_summary(tmp_path: Path, period: Period) -> None:
    pdf = tmp_path / "submission.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    a, b = CLEAN / "opening.xlsx", CLEAN / "closing.xlsx"
    report = summary_data(
        analyze(
            load_ledger(
                pdf if period == "opening" else a, pdf if period == "closing" else b
            )
        )
    )
    assert report["gate"]["status"] == "blocked" and not report["bridges"]
    finding = report["gate"]["checks"][0]
    assert (
        "PDF" in finding["message"] and finding["citations"][0]["file_id"] == pdf.name
    )
