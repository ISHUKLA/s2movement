"""D7 boundary tests for the independent benchmark settings and flag arithmetic."""

from __future__ import annotations

import json
from typing import Any

import pytest
from bench_cases import period_cells
from bench_observations import BS, FLOW, LTG, OF, SCR, TP, observations
from bench_workbooks import HERE, Cells


def ruleset() -> dict[str, Any]:
    return dict(json.loads((HERE / "thresholds.yaml").read_text())["rules"])


def compare(
    left: Cells, right: Cells, rules: dict[str, Any] | None = None
) -> dict[str, Any]:
    # Use a separate, unscored mutation. These tests vary individual operands
    # without asserting any of the six scored packages' commentary seeds.
    return observations("1", left, right, rules or ruleset(), [])


def flags(result: dict[str, Any]) -> dict[str, Any]:
    return {f["id"]: f for f in result["flags"]}


@pytest.mark.parametrize("step", (-1, 0, 1))
@pytest.mark.parametrize("direction", (-1, 1))
@pytest.mark.parametrize("base,cutoff", [(0, 100_000), (8_000_000, 400_000)])
def test_r023_money_boundaries(
    base: int, cutoff: int, direction: int, step: int
) -> None:
    a = period_cells("1", False)
    key = BS, "R0040", "C0010"
    a[key] = base
    b = {**a, key: base + direction * (cutoff + step)}
    the_id = "movement_money/" + "/".join(key)
    found = flags(compare(a, b))
    assert (the_id in found) == (step > 0)
    if step > 0:
        assert int(found[the_id]["signed_statistic"]) == direction * (cutoff + 1)
    # Override on identical facts must move the threshold.
    rules = ruleset()
    rules["movement_money"]["threshold"]["absolute_eur"] = 9_000_000
    assert the_id not in flags(compare(a, b, rules))


@pytest.mark.parametrize("step", (-1, 0, 1))
def test_r023_exact_coverage_points(step: int) -> None:
    a = period_cells("1", False)
    scr, funds = (OF, "R0580", "C0010"), (OF, "R0540", "C0010")
    a[scr] = 100_000_000
    b = {**a, funds: int(a[funds]) + 2_000_000 + step}
    f = flags(compare(a, b))
    assert ("movement_ratio/own_funds" in f) == (step > 0)
    assert ("movement_ratio/ratio_change" in f) == (step > 0)
    assert "movement_ratio/interaction" not in f


@pytest.mark.parametrize("col", ("C0030", "C0050", "C0070", "C0090"))
@pytest.mark.parametrize("step", (-1, 0, 1))
def test_r006_r024_scenario_impact_boundary(col: str, step: int) -> None:
    a = period_cells("1", False)
    base = LTG, "R0010", "C0010"
    a[base] = 30_000_000
    k = LTG, "R0010", col
    b = {**a, k: int(a[k]) - 300_000 - step}
    observed = flags(compare(a, b))
    assert ("measure_impact/" + col in observed) == (step > 0)
    assert not any(k.startswith("measure_status/") for k in observed)


@pytest.mark.parametrize("step", (-1, 0, 1))
def test_r015_linked_assets_activation(step: int) -> None:
    a = period_cells("1", False)
    total, linked = (BS, "R0500", "C0010"), (BS, "R0220", "C0010")
    a[total] = 40_000_000
    a[linked] = 0
    b = {**a, linked: 2_000_000 + step}
    assert compare(a, b)["linked_material"] is (step > 0)
    rules = ruleset()
    rules["linked_materiality"]["threshold"]["fraction_of_total_assets"] = "0.051"
    assert compare(a, b, rules)["linked_material"] is False


@pytest.mark.parametrize("direction", (-1, 1))
@pytest.mark.parametrize("step", (-1, 0, 1))
def test_r015_r024_linked_divergence(direction: int, step: int) -> None:
    a = period_cells("1", False)
    linked = BS, "R0220", "C0010"
    a[BS, "R0500", "C0010"] = 80_000_000
    a[linked] = 20_000_000
    # Vary the risk margin only. Rising RM has a negative contribution to pairing.
    margin = BS, "R0720", "C0010"
    b = {**a, margin: int(a[margin]) + direction * (400_000 + step)}
    the_id = "linked_divergence/linked_portfolio"
    observed = flags(compare(a, b))
    assert (the_id in observed) == (step > 0)
    if step > 0:
        assert int(observed[the_id]["signed_statistic"]) == -direction * 400_001


@pytest.mark.parametrize("row", ("R1410", "R1610"))
@pytest.mark.parametrize("step", (-1, 0, 1))
def test_r024_annual_scale_factor(row: str, step: int) -> None:
    a = period_cells("1", False)
    k = FLOW, row, "C0230"
    a[k] = 10_000
    b = {**a, k: 1_000_000 + step}
    the_id = f"premium_claim_scale/{row}/C0230"
    assert (the_id in flags(compare(a, b))) == (step > 0)
    assert (the_id in flags(compare(b, a))) == (step > 0)


@pytest.mark.parametrize("step", (-1, 0, 1))
@pytest.mark.parametrize("gross_bel_delta", (0, 500_000))
def test_r024_gross_flow_vs_same_lob_bel(gross_bel_delta: int, step: int) -> None:
    a = period_cells("1", False)
    bel = TP, "R0030", "C0040"
    flow = FLOW, "R1410", "C0230"
    b = {**a, bel: int(a[bel]) + gross_bel_delta}
    limit = max(100_000, 5 * gross_bel_delta)
    b[flow] = limit + step
    other_lob = TP, "R0030", "C0020"
    b[other_lob] = int(a[other_lob]) + 200_000_000
    the_id = "premium_claim_vs_bel/R1410/C0230"
    assert (the_id in flags(compare(a, b))) == (step > 0)
    assert (the_id in flags(compare(a, {**b, flow: -int(b[flow])}))) == (step > 0)


@pytest.mark.parametrize("step", (-1, 0, 1))
def test_r024_lac_dt_direction_and_reconstruction(step: int) -> None:
    opening = period_cells("1", False)
    closing = opening.copy()
    relief = SCR, "R0150", "C0100"
    operation = SCR, "R0130", "C0100"
    total = SCR, "R0220", "C0100"
    size = 100_000 + step
    # Two independent observations: operational charge rises and relief falls.
    for key, delta in ((operation, size), (relief, size), (total, 2 * size)):
        closing[key] = int(opening[key]) + delta
    flag = "lac_dt_direction/relief_magnitude"
    assert (flag in flags(compare(opening, closing))) == (step > 0)
    if step > 0:
        closing[total] = int(closing[total]) + 2
        result = compare(opening, closing)
        assert flag not in flags(result)
        assert any(
            e["rule"] == "lac_dt_direction" and e["status"] == "indeterminate"
            for e in result["flag_evaluations"]
        )
