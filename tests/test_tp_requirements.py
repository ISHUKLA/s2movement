"""Independent totals, threshold boundaries and cited pairings for R-012–R-015."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_tp_bridges import PACKAGES, alter_closing, pair

from s2movement.engine import EvalValue, analyze
from s2movement.models import Ledger, Period
from s2movement.output import summary_data
from s2movement.tp_bridges import linked_materiality


def amount(value: EvalValue) -> Decimal:
    assert value.value is not None and value.unit_scale is not None
    return value.value * value.unit_scale


def reported_tp(path: Path, column: str) -> dict[str, Decimal]:
    """Read source workbook cells without product expressions or fixture arithmetic."""
    wb = load_workbook(path, data_only=True)
    result = {}
    index = None
    try:
        for row in wb["S.12.01"].values:
            if row[0] == "table":
                index = None
            elif row[0] == "row/column":
                index = row.index(column) if column in row else None
            elif str(row[0]).startswith("R") and index is not None:
                if row[index] is not None:
                    assert str(row[0]) not in result
                    result[str(row[0])] = Decimal(str(row[index]))
        metadata = {r[0]: r[1] for r in wb["Metadata"].values}
        scale = Decimal(str(metadata["money_unit_scale"]))
        return {r: value * scale for r, value in result.items()}
    finally:
        wb.close()


@pytest.mark.parametrize("case", ("1", "2a", "2b", "3", "4", "5"))
@pytest.mark.parametrize(
    "business,column", (("life", "C0150"), ("health_slt", "C0210"))
)
def test_R012_totals_independently_exclude_double_counting(
    case: str, business: str, column: str
) -> None:
    analysis = analyze(pair(case))
    schedules = {s.id: s for s in analysis.schedules}
    prefix = f"tp/{business}"
    before, after = (
        reported_tp(PACKAGES / case / f"{p}.xlsx", column)
        for p in ("opening", "closing")
    )
    calculated = []
    for period, values in (("opening", before), ("closing", after)):
        net_bel = values["R0030"] - values["R0080"]
        # Whole TP minus its recoverables, net BEL, risk margin, signed transitionals.
        total = (
            values["R0010"]
            - values["R0020"]
            + net_bel
            + values["R0100"]
            + values["R0110"]
            + values["R0120"]
            + values["R0130"]
        )
        assert total == values["R0210"]
        assert total != total + net_bel  # These packages have nonzero BEL.
        subtotal = getattr(schedules[prefix + "/net_bel"], period)
        total_amount = getattr(schedules[prefix + "/components_total"], period)
        assert amount(subtotal) == net_bel
        assert amount(total_amount) == total
        assert {c.row for c in subtotal.citations if c.row} == {"R0030", "R0080"}
        calculated.append(total)
    bridge = next(
        b for b in analysis.bridges if b.definition.id == f"{business}_net_tp"
    )
    movements = [
        amount(line.result)
        for line in bridge.lines
        if line.definition.role == "movement"
    ]
    assert sum(movements) == calculated[1] - calculated[0]
    assert "net_bel" not in {line.definition.id for line in bridge.lines}


def replace_bs(ledger: Ledger, period: Period, amounts: dict[str, int]) -> Ledger:
    return ledger.model_copy(
        update={
            "facts": tuple(
                f.model_copy(update={"reported_value": Decimal(amounts[f.row])})
                if f.period == period and f.template == "S.02.01" and f.row in amounts
                else f
                for f in ledger.facts
            )
        }
    )


@pytest.mark.parametrize("period", ("opening", "closing"))
@pytest.mark.parametrize(
    "total,boundary", ((10_000_000, 500_000), (1_000_000, 100_000))
)
@pytest.mark.parametrize(
    "offset,expected", ((-1, "not_material"), (0, "not_material"), (1, "material"))
)
def test_R015_frozen_threshold_each_date_and_absolute_floor(
    period: Period, total: int, boundary: int, offset: int, expected: str
) -> None:
    ledger = pair("1")
    for p in ("opening", "closing"):
        ledger = replace_bs(ledger, p, {"R0220": 0, "R0500": total})
    ledger = replace_bs(ledger, period, {"R0220": boundary + offset})
    result = analyze(ledger)
    report = summary_data(result)["linked_pairing"]
    assert report["status"] == expected
    measured = next(m for m in result.linked_materiality if m.period == period)
    assert measured.threshold.value == boundary
    assert measured.threshold.citations[0].row == "R0500"
    assert report["operator"] == ">"
    assert len(report["difference_ids"]) == (4 if expected == "material" else 0)


@pytest.mark.parametrize("bad_total", (0, -1))
def test_R015_nonpositive_denominator_is_indeterminate(bad_total: int) -> None:
    ledger = replace_bs(pair("1"), "opening", {"R0220": 0, "R0500": 1_000_000})
    ledger = replace_bs(ledger, "closing", {"R0500": bad_total})
    result = summary_data(analyze(ledger))["linked_pairing"]
    assert result["status"] == "indeterminate"
    closing = result["materiality"][1]
    assert closing["threshold"]["value"] is None
    assert "nonpositive" in closing["threshold"]["reason"]


def test_R015_missing_operand_and_currency_are_explicit() -> None:
    ledger = pair("1")
    missing = ledger.model_copy(
        update={
            "facts": tuple(
                f
                for f in ledger.facts
                if not (
                    f.period == "closing"
                    and f.template == "S.02.01"
                    and f.row == "R0500"
                )
            )
        }
    )
    closing = linked_materiality(missing)[1]
    assert closing.status == "indeterminate"
    assert closing.total_assets.status == "unavailable"
    assert closing.total_assets.missing_template == "S.02.01"
    assert closing.total_assets.missing_period == "closing"
    foreign = ledger.model_copy(
        update={
            "facts": tuple(
                f.model_copy(update={"currency": "GBP"}) for f in ledger.facts
            )
        }
    )
    assert all(m.status == "indeterminate" for m in linked_materiality(foreign))
    assert all("EUR" in str(m.threshold.reason) for m in linked_materiality(foreign))


def test_R015_mixed_scale_materiality_uses_euros() -> None:
    ledger = pair("2a")
    result = linked_materiality(ledger)
    for measured in result:
        assert measured.linked_assets.value is not None
        assert measured.total_assets.value is not None
        assert measured.threshold.value == max(
            Decimal(100_000),
            amount(measured.total_assets) * Decimal("0.05"),
        )
        assert measured.status == "material"
    assert any(
        c.sheet == "confirmations.json" or "confirm" in c.file_id
        for c in result[0].linked_assets.citations
    )


def test_R013_R015_pairwise_differences_have_all_inputs_and_no_attribution() -> None:
    result = analyze(pair("4"))
    details = {s.id: s for s in result.schedules}
    expected = {
        "R0340": 20_000_000,
        "R0700": 20_000_000,
        "R0710": 19_000_000,
        "R0720": 19_000_000,
    }
    for row, expected_amount in expected.items():
        observed = details[f"linked/assets_less_{row}"]
        assert observed.category == "movement_difference"
        assert observed.operands == ("linked/R0220", f"linked/{row}")
        assert observed.movement.value == expected_amount
        assert observed.movement.value == (
            amount(details["linked/R0220"].movement)
            - amount(details[f"linked/{row}"].movement)
        )
        assert {(c.period, c.row) for c in observed.movement.citations} == {
            (p, r) for p in ("opening", "closing") for r in ("R0220", row)
        }
        assert "Difference between movements" in observed.label
    for column in ("C0040", "C0050"):
        assert f"S.12.01.01.01/R0030/{column}" in details
        assert f"S.12.01.01.01/R0100/{column}" not in details
    assert (
        "Index-linked and unit-linked insurance"
        in details["S.12.01.01.01/R0100/C0030"].label
    )


def test_R014_scenario_impacts_do_not_change_tp_components() -> None:
    ledger = pair("2b")
    changed = ledger.model_copy(
        update={
            "facts": tuple(
                f.model_copy(update={"reported_value": f.reported_value - 100})
                if f.template == "S.22.01"
                and f.column == "C0070"
                and f.period == "closing"
                else f
                for f in ledger.facts
            )
        }
    )
    before, after = analyze(ledger), analyze(changed)
    assert [b for b in before.bridges if b.definition.id.endswith("net_tp")] == [
        b for b in after.bridges if b.definition.id.endswith("net_tp")
    ]
    a = next(s for s in before.schedules if s.id == "S.22.01.01.01/R0010/C0070")
    b = next(s for s in after.schedules if s.id == a.id)
    assert amount(b.movement) == amount(a.movement) - 100
    assert b.category == "ltg_scenario"


def test_R015_failed_recoverables_check_withholds_only_its_comparisons() -> None:
    ledger = alter_closing(pair("4"), "R0080", "C0040", 100)
    details = {s.id: s for s in analyze(ledger).schedules}
    assert details["linked/assets_less_R0340"].movement.status == "withheld"
    assert "closing_linked_recoverables" in str(
        details["linked/assets_less_R0340"].movement.reason
    )
    for row in ("R0700", "R0710", "R0720"):
        assert details[f"linked/assets_less_{row}"].movement.status == "value"
