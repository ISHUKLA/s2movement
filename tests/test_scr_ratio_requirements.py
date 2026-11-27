"""R-019–R-021 source isolation, missing detail and exact D5 arithmetic."""

from __future__ import annotations

import random
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from test_capital_bridges import _edit_amounts, _values
from test_tp_bridges import PACKAGES, pair
from test_tp_workbook import change

from s2movement.engine import Analysis, analyze
from s2movement.models import Ledger, Period
from s2movement.normalized import load_ledger


@pytest.fixture(autouse=True)
def benchmark_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(PACKAGES.parent))


@pytest.fixture(scope="module")
def clean() -> Ledger:
    return pair("1")


def bridge_results(analysis: Analysis) -> list[object]:
    """Exclude source-file checksums, which legitimately change after a mutation."""
    return [
        (
            b.definition,
            b.status,
            b.residual_status,
            b.tolerance.value,
            [
                (
                    line.definition,
                    line.status,
                    line.result.value,
                    line.result.exact_value,
                    line.result.currency,
                    line.result.unit_scale,
                    [
                        (
                            c.period,
                            c.table,
                            c.row,
                            c.column,
                            c.dimensions,
                            c.coordinate_context,
                            c.sheet,
                            c.cell,
                        )
                        for c in line.result.citations
                    ],
                )
                for line in b.lines
            ],
        )
        for b in analysis.bridges
    ]


@pytest.mark.parametrize("period", ("opening", "closing"))
@pytest.mark.parametrize("template", ("S.26.01", "S.26.02", "S.26.03"))
@pytest.mark.parametrize("operation", ("remove-template", "alter-cell"))
def test_R019_drilldowns_never_change_top_level_results(
    tmp_path: Path, clean: Ledger, period: Period, template: str, operation: str
) -> None:
    before = analyze(clean)
    source = next(
        f for f in clean.facts if f.period == period and f.template == template
    )
    variant = tmp_path / "variant"
    change(
        PACKAGES / "1",
        variant,
        {
            "period": period,
            "operation": operation,
            "template": template,
            "table": source.table,
            "row": source.row,
            "column": source.column,
            "context_id": source.context_id,
            "coordinate_context": source.coordinate_context,
            "value": str(source.reported_value + 17),
        },
    )
    after = analyze(load_ledger(variant / "opening.xlsx", variant / "closing.xlsx"))
    # Adding the missing schedules back (the original pair) gives exactly the
    # same top-level results as the pair with the single template removed.
    assert bridge_results(after) == bridge_results(before)
    identifier = "/".join((source.table, source.row, source.column))
    old, new = (
        next(s for s in a.schedules if s.id == identifier) for a in (before, after)
    )
    assert new.category == "scr_drilldown" and new.bridge_id == "scr_modules"
    observed = getattr(new, period)
    if operation == "remove-template":
        assert observed.status == "unavailable"
        assert (
            observed.missing_template == template and observed.missing_period == period
        )
        assert new.movement.status == "unavailable"
    else:
        assert observed.value == source.reported_value + 17
        assert old.movement.value is not None and new.movement.value is not None
        assert new.movement.value - old.movement.value == (
            17 if period == "closing" else -17
        )


@pytest.mark.parametrize("period", ("opening", "closing"))
def test_R020_missing_S2501_preserves_cited_S2301_headline(
    tmp_path: Path, clean: Ledger, period: Period
) -> None:
    variant = tmp_path / "variant"
    change(
        PACKAGES / "1",
        variant,
        {
            "period": period,
            "operation": "remove-template",
            "template": "S.25.01",
        },
    )
    after = analyze(load_ledger(variant / "opening.xlsx", variant / "closing.xlsx"))
    bridges = {b.definition.id: b for b in after.bridges}
    headline = bridges["headline_scr"]
    assert headline.status == "pass"
    expected = _values(clean, "headline_scr")
    for line in headline.lines:
        assert line.result.value == expected[line.definition.id]
        assert line.result.citations
        assert {c.template for c in line.result.citations} == {"S.23.01"}
        assert {c.row for c in line.result.citations} == {"R0580"}
    assert bridges["solvency_ratio"].status == "pass"
    for line in bridges["scr_modules"].lines:
        if line.definition.role == "reported_balance":
            assert line.result.status == "value"
        else:
            assert line.result.status == "unavailable"
            assert line.result.missing_template == "S.25.01"
            assert line.result.missing_period == period


def test_R021_D5_exact_rational_property_for_random_positive_inputs(
    clean: Ledger,
) -> None:
    # A fixed seed makes failure reproduction independent of machine or test order.
    generator = random.Random(20261126)
    cases = [
        (
            generator.randint(1, 10**12),
            generator.randint(1, 10**12),
            generator.randint(1, 10**12),
            generator.randint(1, 10**12),
        )
        for _ in range(500)
    ]
    cases.extend(
        [
            (10**12, 10**12 + 1, 10**12, 10**12 + 1),
            (1, 10**12, 1, 10**12),
            (10**12, 1, 10**12, 1),
            (2, 5, 3, 7),
        ]
    )
    for e0, e1, s0, s1 in cases:
        edits: dict[tuple[Period, str, str, str], Decimal] = {}
        dates: tuple[tuple[Period, int, int], ...] = (
            ("opening", e0, s0),
            ("closing", e1, s1),
        )
        for period, eligible, scr in dates:
            for row, value in (("R0540", eligible), ("R0580", scr)):
                edits[period, "S.23.01.01.01", row, "C0010"] = Decimal(value)
        actual = _values(_edit_amounts(clean, edits), "solvency_ratio")
        inverse_change = Fraction(1, s1) - Fraction(1, s0)
        expected = {
            "own_funds": 100 * Fraction(e1 - e0, s0),
            "scr": 100 * e0 * inverse_change,
            "interaction": 100 * (e1 - e0) * inverse_change,
        }
        assert {key: actual[key] for key in expected} == expected
        total = sum(expected.values(), Fraction(0))
        assert total == 100 * (Fraction(e1, s1) - Fraction(e0, s0))
        assert actual["closing"] - actual["opening"] == total
        assert actual["residual"] == 0


@pytest.mark.parametrize("period", ("opening", "closing"))
def test_R008_R021_failed_reported_ratio_withholds_only_dependent_effects(
    clean: Ledger, period: Period
) -> None:
    edited = _edit_amounts(
        clean,
        {(period, "S.23.01.01.01", "R0620", "C0010"): Decimal("0.01")},
        add=True,
    )
    result = analyze(edited)
    assert all(v.status == "pass" for v in result.ratio_validations)
    for bridge in result.bridges:
        if bridge.definition.id != "solvency_ratio":
            assert bridge.status == "pass"
            continue
        for line in bridge.lines:
            if line.definition.role == "reported_balance":
                assert line.result.status == "value"
            else:
                assert line.result.status == "withheld"
                assert f"{period}_ratio" in (line.result.reason or "")
