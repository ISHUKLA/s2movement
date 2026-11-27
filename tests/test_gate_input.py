"""Evidence and ordering boundaries at the normalized adapter (R-001 to R-005)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from s2movement.normalized import InputError, load_ledger

PACKAGES = Path(__file__).parent / "fixtures" / "packages"


def test_R001_R004_mixed_precision_reversed_rerun() -> None:
    case = PACKAGES / "2a"
    ledger = load_ledger(
        case / "closing.xlsx",
        case / "opening.xlsx",
        confirmation_path=case / "confirmations.json",
    )
    assert ledger.supplied_reversed
    assert [f.period for f in ledger.inputs] == ["opening", "closing"]
    assert [f.file_id for f in ledger.inputs] == ["opening.xlsx", "closing.xlsx"]
    assert not ledger.input_issues
    converted = next(
        f
        for f in ledger.facts
        if f.kind == "money"
        and not f.reported_value.is_zero()
        and f.period == "opening"
    )
    assert converted.resolved_value == converted.reported_value * 1000
    assert converted.resolved_precision == 1000
    ratios = [f for f in ledger.facts if f.kind == "ratio"]
    assert all(
        f.conversion is None
        and f.resolved_value == f.reported_value
        and f.reported_precision == Decimal("0.0001")
        for f in ratios
    )
    assert len(ratios) == 4
    lei = ledger.metadata_value("closing", "lei")
    assert lei and lei.citation.sheet == "Metadata"
    assert len(lei.corroboration) == 1
    assert (lei.corroboration[0].row, lei.corroboration[0].sheet) == (
        "R0020",
        "S.01.02",
    )
    assert any(d.citation.sheet == "S.01.01" for d in ledger.declarations)


def test_R001_date_stop_precedes_malformed_financial_and_header_fields(
    tmp_path: Path,
) -> None:
    case = PACKAGES / "1"
    edited = tmp_path / "duplicate-date.xlsx"
    book = load_workbook(case / "opening.xlsx")
    book["Metadata"]["B12"] = None
    book["S.02.01"]["B1"] = "invalid table"
    book.save(edited)
    book.close()
    ledger = load_ledger(case / "opening.xlsx", edited)
    assert [i.id for i in ledger.input_issues] == ["consecutive_annual_periods"]
    assert {(c.file_id, c.cell) for c in ledger.input_issues[0].citations} == {
        ("opening.xlsx", "B3"),
        (edited.name, "B3"),
    }
    assert not ledger.facts


def test_R003_pdf_only_and_other_file_keeps_actual_evidence(tmp_path: Path) -> None:
    pdf = tmp_path / "uploaded.xlsx"  # Extension cannot make a PDF a workbook.
    pdf.write_bytes(b"%PDF-1.4\n")
    other = PACKAGES / "1" / "closing.xlsx"
    ledger = load_ledger(pdf, other)
    assert [i.id for i in ledger.input_issues] == ["opening_pdf_input"]
    assert ledger.input_issues[0].citations[0].sha256 == ledger.inputs[0].sha256
    assert ledger.metadata_value("opening", "reference_date") is None
    assert ledger.metadata_value("closing", "reference_date") is not None
    assert not ledger.facts


def test_R005_D2_correction_cannot_hide_other_entity(tmp_path: Path) -> None:
    opening = PACKAGES / "1" / "opening.xlsx"
    closing = PACKAGES / "3" / "closing.xlsx"
    uncorrected = load_ledger(opening, closing)
    a = uncorrected.metadata_value("opening", "lei")
    b = uncorrected.metadata_value("closing", "lei")
    assert a and b and a.value != b.value
    fix = tmp_path / "corrections.json"
    fix.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corrections": [
                    {
                        "period": "closing",
                        "file_id": closing.name,
                        "field": "lei",
                        "original_value": b.value,
                        "corrected_value": a.value,
                        "evidence": "Reviewer assertion differs from filed identity",
                        "reason": "Correct purported identifier typo",
                        "reviewer": "synthetic",
                    }
                ],
            }
        )
    )
    ledger = load_ledger(opening, closing, correction_path=fix)
    issues = {i.id: i for i in ledger.input_issues}
    assert {"closing_lei_context", "closing_lei_declarations"} == set(issues)
    assert any(c.sheet == "Contexts" for c in issues["closing_lei_context"].citations)
    assert any(
        c.sheet == "S.01.02" for c in issues["closing_lei_declarations"].citations
    )


def test_R005_confirmation_requires_actual_evidence(tmp_path: Path) -> None:
    case = PACKAGES / "2a"
    confirmation = json.loads((case / "confirmations.json").read_text())
    confirmation["confirmations"][0]["evidence"] = None
    sidecar = tmp_path / "invalid.json"
    sidecar.write_text(json.dumps(confirmation))
    with pytest.raises(InputError, match="evidence"):
        load_ledger(
            case / "opening.xlsx", case / "closing.xlsx", confirmation_path=sidecar
        )
