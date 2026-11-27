"""R-016–R-018 independent row coverage, legal boundaries and observed effects."""

from __future__ import annotations

import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from test_capital_bridges import _edit_amounts
from test_tp_bridges import pair

from s2movement.capital_bridges import BALANCE_PARTS
from s2movement.engine import analyze
from s2movement.models import Ledger, Period
from s2movement.output import summary_data
from s2movement.tier_limits import assess_limits, changes

MAPPING = Path(__file__).parents[1] / "mappings/2.8.2"
TABLE = "S.23.01.01.01"


def test_R016_all_rows_are_assigned_once_or_sourced_subtotals() -> None:
    data = json.loads((MAPPING / "balance_sheet_buckets.json").read_text())
    records = list(csv.DictReader((MAPPING / "cells.csv").open()))
    official = [r for r in records if r["table"].startswith("S.02.01")]
    assert set(data["rows"]) == {r["row"] for r in official}
    mapped = data["rows"]
    owners = Counter(row for b in data["buckets"] for row in b["rows"])
    for row, entry in mapped.items():
        if entry["kind"] == "component":
            assert owners[row] == 1 and entry["bucket"]
        else:
            assert entry["children"] and len(entry["children"]) == len(
                entry["coefficients"]
            )
            if row != "R1000":
                record = next(
                    r for r in official if r["row"] == row and r["column"] == "C0010"
                )
                assert record["subtotal_status"] == "verified subtotal"
                assert entry["children"] == record["subtotal_components"].split(" + ")
                assert entry["relationship_source"] == record["subtotal_source"]
            else:
                assert entry["children"] == ["R0500", "R0900"]
                assert entry["coefficients"] == [1, -1]

    def leaves(row: str, visited: tuple[str, ...] = ()) -> list[str]:
        assert row not in visited
        if mapped[row]["kind"] == "component":
            return [row]
        return [
            v
            for child in mapped[row]["children"]
            for v in leaves(child, (*visited, row))
        ]

    counted: Counter[str] = Counter()
    for b, part in zip(data["buckets"], BALANCE_PARTS, strict=True):
        assert b["id"] == part.id
        assert b["reported_roots"] == list(part.rows)
        assert b["rows"] == list(part.covered_rows)
        expanded = [v for root in part.rows for v in leaves(root)]
        assert all(mapped[v]["bucket"] == part.id for v in expanded)
        counted.update(expanded)
    sii_leaves = {
        r
        for r, v in mapped.items()
        if v["kind"] == "component" and "C0010" in v["columns"]
    }
    assert set(counted) == sii_leaves
    assert set(counted.values()) == {1}
    # The other three rows are statutory-only source cells, assigned but never
    # included in the Solvency II-valued movement.
    assert {r for r in mapped if "C0010" not in mapped[r]["columns"]} == {
        "R0010",
        "R0020",
        "R0730",
    }
    assert set(leaves("R1000")) == sii_leaves


@pytest.mark.parametrize("case", ("1", "2a", "2b", "3", "4", "5"))
def test_R017_two_dates_explain_the_annual_adjustments(case: str) -> None:
    analysis = analyze(pair(case))
    bridges = {b.definition.id: b for b in analysis.bridges}
    opening = {
        line.definition.id: line.result.value
        for line in bridges["opening_excess_to_eligible"].lines
    }
    closing = {
        line.definition.id: line.result.value
        for line in bridges["closing_excess_to_eligible"].lines
    }
    yearly = {
        line.definition.id: line.result.value
        for line in bridges["eligible_own_funds"].lines
    }
    assert opening["residual"] == closing["residual"] == yearly["residual"] == 0
    for key in opening.keys() - {"opening", "closing", "residual"}:
        a, b = opening[key], closing[key]
        assert a is not None and b is not None
        assert yearly[key] == b - a
    split_ids = {(s.id, s.period) for s in analysis.unsupported_splits}
    for period in ("opening", "closing"):
        assert ("rff_map_restrictions_split", period) in split_ids
        assert (
            "foreseeable_dividends_distributions_charges_split",
            period,
        ) in split_ids
    report = summary_data(analysis)
    excess = next(b for b in report["bridges"] if b["id"] == "excess")
    for line in excess["lines"]:
        if line["role"] == "movement":
            assert line["reported_inputs"] and line["covered_rows"]


@pytest.fixture(scope="module")
def ledger() -> Ledger:
    return pair("1")


def tier_pair(
    base: Ledger,
    period: Period,
    available2: int = 20,
    eligible2: int = 20,
    available3: int = 8,
    eligible3: int = 8,
    scr: int = 100,
) -> Ledger:
    updates = {
        (period, TABLE, row, col): Decimal(value)
        for row, col, value in (
            ("R0500", "C0040", available2),
            ("R0540", "C0040", eligible2),
            ("R0500", "C0050", available3),
            ("R0540", "C0050", eligible3),
            ("R0580", "C0010", scr),
        )
    }
    return _edit_amounts(base, updates)


@pytest.mark.parametrize("period", ("opening", "closing"))
@pytest.mark.parametrize(
    "eligible,conclusion,compliance",
    (
        (13, "indeterminate", "pass"),
        (14, "binding", "pass"),
        (15, "indeterminate", "fail"),
        (16, "indeterminate", "fail"),
    ),
)
def test_R018_strict_tier3_boundary(
    ledger: Ledger, period: Period, eligible: int, conclusion: str, compliance: str
) -> None:
    result = assess_limits(tier_pair(ledger, period, available3=32, eligible3=eligible))
    item = next(
        t for t in result if t.period == period and t.rule.id == "article82_1_b"
    )
    assert item.rule.operator == "<"
    assert item.amounts["bound"].value == 15
    assert item.reported_compliance == compliance
    assert item.status == conclusion


@pytest.mark.parametrize("period", ("opening", "closing"))
@pytest.mark.parametrize(
    "eligible2,conclusion,compliance",
    (
        (40, "indeterminate", "pass"),
        (41, "indeterminate", "pass"),
        (42, "binding", "pass"),
        (43, "indeterminate", "fail"),
    ),
)
def test_R018_inclusive_combined_boundary(
    ledger: Ledger, period: Period, eligible2: int, conclusion: str, compliance: str
) -> None:
    result = assess_limits(
        tier_pair(ledger, period, available2=50, eligible2=eligible2)
    )
    item = next(
        t for t in result if t.period == period and t.rule.id == "article82_1_c"
    )
    assert item.rule.operator == "<="
    assert item.amounts["bound"].value == 50
    assert item.reported_compliance == compliance
    assert item.status == conclusion


def test_R018_competing_limits_and_source_precision(ledger: Ledger) -> None:
    ambiguous = tier_pair(
        ledger, "closing", available2=50, eligible2=35, available3=32, eligible3=14
    )
    results = {t.rule.id: t for t in assess_limits(ambiguous) if t.period == "closing"}
    assert (
        results["article82_1_b"].status
        == results["article82_1_c"].status
        == "indeterminate"
    )
    near = tier_pair(ledger, "closing", available3=16, eligible3=14)
    t = next(t for t in assess_limits(near) if t.id == "closing_article82_1_b")
    assert t.status == "indeterminate"  # Excess supply is within one source unit.
    unknown = ledger.model_copy(
        update={
            "facts": tuple(
                f.model_copy(update={"reported_precision": None})
                if f.table == TABLE and f.row == "R0580"
                else f
                for f in ledger.facts
            )
        }
    )
    assert all(t.status == "indeterminate" for t in assess_limits(unknown))


def test_R018_tax_cliff_effect_and_release() -> None:
    base = pair("5")
    assessed = assess_limits(base)
    transition = next(t for t in changes(assessed) if t.id == "article82_1_b")
    assert transition.direction == "newly_binding"
    assert (
        transition.observed_adjustment_change.value
        == transition.effect.value
        == -14_000_000
    )
    assert all(
        t.status == "indeterminate" for t in assessed if t.rule.id == "article82_3"
    )
    # Reverse only the period labels to exercise the direction of the same observations.
    reverse = base.model_copy(
        update={
            "facts": tuple(
                f.model_copy(
                    update={"period": "closing" if f.period == "opening" else "opening"}
                )
                for f in base.facts
            )
        }
    )
    released = next(
        t for t in changes(assess_limits(reverse)) if t.id == "article82_1_b"
    )
    assert released.direction == "released" and released.effect.value == 14_000_000


def test_R018_scr_detail_absence_leaves_tier_assessments_usable() -> None:
    analysis = analyze(pair("3"))
    assert all(t.amounts["denominator"].value is not None for t in analysis.tier_limits)
    assert all(
        t.status == "not_binding"
        for t in analysis.tier_limits
        if t.rule.id != "article82_3"
    )
    assert all(
        c.template == "S.23.01"
        for t in analysis.tier_limits
        for c in t.effect.citations
    )


def test_R018_restricted_tier1_keeps_observation_without_attribution() -> None:
    assessments = assess_limits(pair("2b"))
    restricted = [t for t in assessments if t.rule.id == "article82_3"]
    assert len(restricted) == 2
    assert all(
        t.status == "indeterminate" and t.effect.value is None for t in restricted
    )
    assert all(
        t.amounts["available"].value is not None
        and t.amounts["eligible"].value is not None
        for t in restricted
    )
    assert all("VERIFICATION.md" in t.reason for t in restricted)
