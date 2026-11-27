"""Independent controls on the frozen benchmark design, before any product scoring."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest
from bench_cases import period_cells
from bench_oracle import BS, MODULE, OF, RR, Amount, Date, expected_run
from bench_workbooks import RUNS


@pytest.mark.parametrize("case", list(RUNS))
def test_r008_r011_r021_case_arithmetic(case: str) -> None:
    a, b = period_cells(case, False), period_cells(case, True)
    for rid in RUNS[case]:
        key = expected_run(case, rid, a, b)
        if rid == "02a-stop":
            assert key["gate"]["status"] == "blocked"
            assert not key["bridges"]
            continue
        for comp in key["comparisons"]:
            if comp["status"] == "unavailable":
                assert (case, comp["id"], comp["missing_template"]) == (
                    "3",
                    "closing_scr",
                    "S.25.01",
                )
                continue
            observation = comp.get("fixture_arithmetic", comp)
            if comp.get("benchmark_dependency_open"):
                assert comp["status"] == "indeterminate"
            else:
                assert comp["status"] == "pass"
            delta = Fraction(observation["left"]["value"]) - Fraction(
                observation["right"]["value"]
            )
            assert Fraction(observation["signed_discrepancy"]["value"]) == delta
            assert abs(delta) <= Fraction(observation["tolerance"])
        for bridge in key["bridges"]:
            lines = bridge["lines"]
            if bridge["residual_status"] == "unavailable":
                assert (case, bridge["id"]) == ("3", "scr_modules")
                for item in lines:
                    if item["role"] in {"movement", "residual"}:
                        assert item["status"] == "unavailable" and "value" not in item
                        assert item["period"] == "closing"
                        assert item["missing_template"] == "S.25.01"
                continue
            assert bridge["residual_status"] == "pass"
            assert [x["role"] for x in (lines[0], lines[-2], lines[-1])] == [
                "opening",
                "residual",
                "closing",
            ]
            amounts = [Fraction(x["value"]) for x in lines]
            assert amounts[-2] == 0 and sum(amounts[:-1]) == amounts[-1]
            assert all(x["citations"] for x in lines)
            for x, v in zip(lines, amounts, strict=True):
                assert x["sign"] == (
                    "positive" if v > 0 else "negative" if v < 0 else "zero"
                )
            if bridge["id"] == "solvency_ratio":
                assert bridge["tolerance"] == "0"
                assert [ln["id"] for ln in lines[1:-2]] == [
                    "own_funds",
                    "scr",
                    "interaction",
                ]
                assert amounts[0] == 100 * Fraction(
                    int(a[OF, "R0540", "C0010"]), int(a[OF, "R0580", "C0010"])
                )
                assert amounts[-1] == 100 * Fraction(
                    int(b[OF, "R0540", "C0010"]), int(b[OF, "R0580", "C0010"])
                )


@pytest.mark.parametrize("case", list(RUNS))
@pytest.mark.parametrize("closing", (False, True))
def test_r008_r012_r019_source_identities(case: str, closing: bool) -> None:
    values = period_cells(case, closing)
    d = Date("closing" if closing else "opening", values)

    def at(table: str, row: str, col: str = "C0010") -> Amount:
        return d.fact(table, row, col)

    assert (at(BS, "R0500") - at(BS, "R0900")).n == at(BS, "R1000").n
    assert at(BS, "R1000").n == at(RR, "R0700", "C0060").n
    # Separate portfolio construction controls from verified regulatory equalities.
    for row_total, rows in [
        ("R0610", ("R0620", "R0630", "R0640")),
        ("R0650", ("R0660", "R0670", "R0680")),
        ("R0690", ("R0700", "R0710", "R0720")),
    ]:
        assert at(BS, row_total).n == sum(int(values[BS, r, "C0010"]) for r in rows)
    flow = "S.05.01.01.02"
    for gross, share, net in [
        ("R1410", "R1420", "R1500"),
        ("R1510", "R1520", "R1600"),
        ("R1610", "R1620", "R1700"),
    ]:
        for tab, row, col in values:
            if (tab, row) == (flow, gross):
                assert (at(flow, gross, col) - at(flow, share, col)).n == at(
                    flow, net, col
                ).n
    if case == "1":
        # Details are alternative presentations. Match net to net and gross to gross.
        for row, tab, detail, net_col in [
            ("R0010", "S.26.01.01.02", "R0800", "C0060"),
            ("R0020", "S.26.02.01.01", "R0400", "C0070"),
            ("R0030", "S.26.03.01.04", "R0900", "C0060"),
        ]:
            assert at(MODULE, row, "C0030").n == at(tab, detail, net_col).n
            assert at(MODULE, row, "C0040").n == at(tab, detail, "C0080").n


def test_r018_distinct_binding_limits_and_evidence() -> None:
    for case, rule, exclusion in [
        ("2b", "article82_3", 5_000_000),
        ("5", "article82_1_b", 14_000_000),
    ]:
        a, b = period_cells(case, False), period_cells(case, True)
        key = expected_run(case, RUNS[case][0], a, b)
        statuses = {t["id"]: t for t in key["tier_limits"]}
        item = statuses[f"closing_{rule}"]
        assert (
            item["status"] == "binding" and item["compliance_with_rounding"] == "pass"
        )
        assert Decimal(item["supply_less_eligible"]["value"]) == exclusion
        assert Decimal(item["other_basic_tier_items"]["value"]) == 0
        assert item["other_basic_tier_items"]["citations"]
        assert statuses[f"opening_{rule}"]["status"] == "slack"
        assert statuses["closing_article82_1_c"]["status"] == "slack"
        change = next(c for c in key["tier_changes"] if c["id"] == rule)
        assert change["transition"] == "newly_binding"
        if case == "2b":
            assert key["unsupported_splits"][0]["status"] == "unavailable"
        else:
            assert statuses["closing_article82_2_b"]["status"] == "binding"
            assert statuses["opening_article82_2_b"]["status"] == "binding"


@pytest.mark.parametrize("offset", (-1001, -1000, 1000, 1001))
def test_r011_d3_mixed_precision_visible_break(offset: int) -> None:
    a, b = period_cells("2a", False), period_cells("2a", True)
    # Alter one asset subtotal independently of every other line and both excess cells.
    baseline = expected_run("2a", "02a-confirmed", a, b)
    baseline_lines = next(
        br["lines"] for br in baseline["bridges"] if br["id"] == "excess"
    )
    k = BS, "R0410", "C0010"
    b[k] = int(b[k]) + offset
    r = expected_run("2a", "02a-confirmed", a, b)
    br = next(b for b in r["bridges"] if b["id"] == "excess")
    assert br["tolerance"] == "1000"
    assert int(br["lines"][-2]["value"]) == -offset
    assert br["residual_status"] == ("pass" if abs(offset) <= 1000 else "fail")
    for before, after in zip(baseline_lines, br["lines"], strict=True):
        delta = int(after["value"]) - int(before["value"])
        assert delta == {"residual": -offset, "other_assets": offset}.get(
            after["id"], 0
        )
