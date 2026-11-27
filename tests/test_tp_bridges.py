"""R-011–R-015/R-019 signed TP, observed pairing and drill-down evidence."""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from s2movement.engine import Analysis, analyze
from s2movement.models import Ledger
from s2movement.normalized import load_ledger

PACKAGES = Path(__file__).parent / "fixtures/packages"


def pair(case: str) -> Ledger:
    base = PACKAGES / case
    return load_ledger(
        base / "opening.xlsx",
        base / "closing.xlsx",
        confirmation_path=(base / "confirmations.json") if case == "2a" else None,
    )


def alter_closing(ledger: Ledger, row: str, column: str, amount: int) -> Ledger:
    facts = []
    for item in ledger.facts:
        if (
            item.period == "closing"
            and item.template == "S.12.01"
            and (item.row, item.column) == (row, column)
        ):
            item = item.model_copy(
                update={"reported_value": item.reported_value + Decimal(amount)}
            )
        facts.append(item)
    return ledger.model_copy(update={"facts": tuple(facts)})


@pytest.fixture(scope="module")
def clean() -> Ledger:
    return pair("1")


@pytest.mark.parametrize("case", ("1", "2a", "2b", "3", "4", "5"))
def test_r011_r012_r013_r014_r019_benchmark(case: str) -> None:
    key = json.loads((PACKAGES / case / "expected.yaml").read_text())["runs"][-1]
    result = analyze(pair(case))
    bridges = {b.definition.id: b for b in result.bridges}
    for wanted in key["bridges"]:
        if wanted["id"] not in {"life_net_tp", "health_slt_net_tp"}:
            continue
        measured = bridges[wanted["id"]]
        assert measured.residual_status == wanted["residual_status"]
        assert measured.tolerance.value == Decimal(wanted["tolerance"])
        lines = {line.definition.id: line.result for line in measured.lines}
        for line in wanted["lines"]:
            assert lines[line["id"]].value == Decimal(line["value"])
            assert lines[line["id"]].citations
    details = {item.id: item for item in result.schedules}
    for schedule in key["schedules"]:
        actual = details[schedule["id"]]
        for field in ("opening", "closing", "movement"):
            observed = getattr(actual, field)
            assert Fraction(observed.value) == Fraction(schedule[field]["value"])
            assert observed.citations


def test_r011_r012_signed_recoverables_and_selective_withholding(clean: Ledger) -> None:
    # More recoverables reduce net TP, regardless of whether they are attached
    # to whole provisions or best estimate. Preserve each source row and sign.
    for row, ident in (
        ("R0020", "recoverables_as_whole"),
        ("R0080", "bel_recoverables"),
    ):
        # This alters both dates' difference by +17 with no change in the others.
        variant = alter_closing(clean, row, "C0150", 17)
        result = analyze(variant)
        bridge = next(b for b in result.bridges if b.definition.id == "life_net_tp")
        signed = next(x for x in bridge.lines if x.definition.id == ident)
        assert signed.result.status == "withheld"
        assert "closing_nonlinked_life_recoverables" in str(signed.result.reason)
        gross = next(x for x in bridge.lines if x.definition.id == "gross_bel")
        assert gross.result.status == "value"
        assert bridge.residual_status == "withheld"
        # Restore the R-008 match on S.02 so the signed movement is exposed.
        matched = variant.model_copy(
            update={
                "facts": tuple(
                    f.model_copy(update={"reported_value": f.reported_value + 17})
                    if f.period == "closing"
                    and f.table == "S.02.01.01.01"
                    and f.row == "R0330"
                    else f
                    for f in variant.facts
                )
            }
        )
        measured = analyze(matched)
        control = analyze(clean)
        assert (
            value(measured, "life_net_tp", ident)
            == value(control, "life_net_tp", ident) - 17
        )
        assert value(measured, "life_net_tp", "residual") == 17


def value(result: Analysis, bridge: str, line: str) -> Decimal:
    item = next(b for b in result.bridges if b.definition.id == bridge)
    n = next(x.result.value for x in item.lines if x.definition.id == line)
    assert n is not None
    return n


def test_r012_tmtp_allocations_keep_reported_negative_sign(clean: Ledger) -> None:
    updated = clean
    for row, amount in (("R0110", -11), ("R0120", -22), ("R0130", -33)):
        updated = alter_closing(updated, row, "C0150", amount)
    result = analyze(alter_closing(updated, "R0210", "C0150", -66))
    assert value(result, "life_net_tp", "transitional_whole") == -11
    assert value(result, "life_net_tp", "transitional_bel") == -22
    assert value(result, "life_net_tp", "transitional_rm") == -33
    assert value(result, "life_net_tp", "residual") == 0


def test_r008_r012_health_tp_break_preserves_independent_lines(clean: Ledger) -> None:
    result = analyze(alter_closing(clean, "R0200", "C0210", 2))
    health = next(b for b in result.bridges if b.definition.id == "health_slt_net_tp")
    lines = {line.definition.id: line.result for line in health.lines}
    for key in ("gross_bel", "risk_margin", "tp_as_whole", "residual"):
        assert lines[key].status == "withheld"
        assert "closing_health_slt_tp" in str(lines[key].reason)
    for key in ("opening", "closing", "bel_recoverables", "recoverables_as_whole"):
        assert lines[key].status == "value"
    life = next(b for b in result.bridges if b.definition.id == "life_net_tp")
    assert life.residual_status == "pass"


def test_r013_r015_linked_gap_and_risk_margin_scope() -> None:
    result = analyze(pair("4"))
    details = {item.id: item for item in result.schedules}
    assert details["linked/observed_difference"].movement.value == 18_000_000
    cites = details["linked/observed_difference"].movement.citations
    assert {(c.period, c.row) for c in cites} == {
        (period, row)
        for period in ("opening", "closing")
        for row in ("R0220", "R0340", "R0700", "R0710", "R0720")
    }
    linked = details["S.12.01.01.01/R0100/C0030"]
    assert "Index-linked and unit-linked insurance" in linked.label
    splits = [
        s
        for s in result.unsupported_splits
        if s.id == "linked_risk_margin_by_guarantee_group"
    ]
    assert {s.period for s in splits} == {"opening", "closing"}
    assert all(s.citations[0].column == "C0030" for s in splits)
    assert "S.12.01.01.01/R0100/C0040" not in details
    assert "S.12.01.01.01/R0100/C0050" not in details
