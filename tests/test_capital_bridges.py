"""Individual source signs and exact coverage arithmetic for R-011, R-016–R-021."""

from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from s2movement.capital_bridges import capital
from s2movement.engine import FactExpr, MissingExpr, SubtractExpr, _eval, analyze
from s2movement.models import Ledger, Period
from s2movement.normalized import load_ledger

PACKAGE = Path(__file__).parent / "fixtures/packages/1"


@pytest.fixture(scope="module")
def clean() -> Ledger:
    return load_ledger(PACKAGE / "opening.xlsx", PACKAGE / "closing.xlsx")


def _edit_amounts(
    ledger: Ledger,
    edits: dict[tuple[Period, str, str, str], Decimal],
    *,
    add: bool = False,
) -> Ledger:
    facts = []
    edited = set()
    for item in ledger.facts:
        key = item.period, item.table, item.row, item.column
        if key in edits:
            value = edits[key] + item.reported_value if add else edits[key]
            item = item.model_copy(update={"reported_value": value})
            assert key not in edited
            edited.add(key)
        facts.append(item)
    assert edited == edits.keys()
    return ledger.model_copy(update={"facts": tuple(facts)})


def _values(ledger: Ledger, bridge_id: str) -> dict[str, Fraction]:
    result: dict[str, Fraction] = {}
    bridge = next(b for b in capital(ledger) if b.id == bridge_id)
    for line in bridge.lines:
        value = _eval(ledger, line.expression, line.sign, line.id)
        assert value.status == "value" and value.value is not None, value.reason
        result[line.id] = (
            value.exact_value
            if value.exact_value is not None
            else Fraction(value.value)
        )
    return result


@pytest.mark.parametrize(
    "bridge,line,table,row,col,sign",
    [
        ("excess", "investments", "S.02.01.01.01", "R0070", "C0010", 1),
        ("excess", "linked_assets", "S.02.01.01.01", "R0220", "C0010", 1),
        ("excess", "deferred_tax_assets", "S.02.01.01.01", "R0040", "C0010", 1),
        ("excess", "other_assets", "S.02.01.01.01", "R0270", "C0010", 1),
        ("excess", "technical_provisions", "S.02.01.01.01", "R0690", "C0010", -1),
        ("excess", "deferred_tax_liabilities", "S.02.01.01.01", "R0780", "C0010", -1),
        ("excess", "other_liabilities", "S.02.01.01.01", "R0850", "C0010", -1),
        (
            "eligible_own_funds",
            "foreseeable_dividends_distributions_charges",
            "S.23.01.01.02",
            "R0720",
            "C0060",
            -1,
        ),
        ("eligible_own_funds", "own_shares", "S.23.01.01.02", "R0710", "C0060", -1),
        ("eligible_own_funds", "rff_map", "S.23.01.01.02", "R0740", "C0060", -1),
        (
            "eligible_own_funds",
            "subordinated_liabilities",
            "S.23.01.01.01",
            "R0140",
            "C0010",
            1,
        ),
        ("eligible_own_funds", "ancillary_funds", "S.23.01.01.01", "R0400", "C0010", 1),
        *(
            (
                "eligible_own_funds",
                "reported_eligibility_" + tier,
                "S.23.01.01.01",
                row,
                col,
                sign,
            )
            for tier, col in (
                ("unrestricted_t1", "C0020"),
                ("restricted_t1", "C0030"),
                ("tier2", "C0040"),
                ("tier3", "C0050"),
            )
            for row, sign in (("R0500", -1), ("R0540", 1))
        ),
        ("scr_modules", "diversification", "S.25.01.01.01", "R0060", "C0040", 1),
        ("scr_modules", "rff_map", "S.25.01.01.02", "R0120", "C0100", 1),
        ("scr_modules", "lac_tp", "S.25.01.01.02", "R0140", "C0100", 1),
        ("scr_modules", "lac_dt", "S.25.01.01.02", "R0150", "C0100", 1),
        ("scr_modules", "add_ons", "S.25.01.01.02", "R0210", "C0100", 1),
    ],
)
def test_R011_R016_R017_R019_signed_source_increment(
    clean: Ledger, bridge: str, line: str, table: str, row: str, col: str, sign: int
) -> None:
    before = _values(clean, bridge)
    changed = _edit_amounts(
        clean, {("closing", table, row, col): Decimal(17)}, add=True
    )
    after = _values(changed, bridge)
    assert after[line] - before[line] == 17 * sign
    assert after["residual"] - before["residual"] == -17 * sign
    assert all(after[k] == v for k, v in before.items() if k not in {line, "residual"})
    if bridge == "eligible_own_funds":
        start = _values(clean, "closing_excess_to_eligible")
        end = _values(changed, "closing_excess_to_eligible")
        assert end[line] - start[line] == 17 * sign


@pytest.mark.parametrize(
    "e1,s1,funds,scr,interaction",
    [
        (130, 51, Fraction(100, 3), Fraction(-475, 34), Fraction(-100, 51)),
        (130, 48, Fraction(100, 3), Fraction(0), Fraction(0)),
        (114, 51, Fraction(0), Fraction(-475, 34), Fraction(0)),
        (114, 48, Fraction(0), Fraction(0), Fraction(0)),
    ],
)
def test_R021_three_exact_effects(
    clean: Ledger,
    e1: int,
    s1: int,
    funds: Fraction,
    scr: Fraction,
    interaction: Fraction,
) -> None:
    # E0=114, S0=48. Both denominators test repeating fractions before display.
    edits: dict[tuple[Period, str, str, str], Decimal] = {}
    dates: tuple[tuple[Period, int, int], ...] = (
        ("opening", 114, 48),
        ("closing", e1, s1),
    )
    for period, eligible, capital_required in dates:
        for row, n in (("R0540", eligible), ("R0580", capital_required)):
            edits[period, "S.23.01.01.01", row, "C0010"] = Decimal(n)
    values = _values(_edit_amounts(clean, edits), "solvency_ratio")
    assert values["own_funds"] == funds
    assert values["scr"] == scr
    assert values["interaction"] == interaction
    assert values["residual"] == 0
    assert values["closing"] - values["opening"] == funds + scr + interaction


def test_R019_gross_scr_plus_signed_lac_tp(clean: Ledger) -> None:
    # Loss absorption reduces a EUR 30 gross increase to a EUR 19 net increase.
    # R0140 is a separate, signed reporting line in the additive SCR equation.
    delta: dict[tuple[Period, str, str, str], Decimal] = {
        ("closing", "S.25.01.01.01", "R0010", "C0040"): Decimal(30),
        ("closing", "S.25.01.01.01", "R0010", "C0030"): Decimal(19),
        ("closing", "S.25.01.01.02", "R0140", "C0100"): Decimal(-11),
        ("closing", "S.23.01.01.01", "R0580", "C0010"): Decimal(19),
    }
    changed = _edit_amounts(clean, delta, add=True)
    values = _values(changed, "scr_modules")
    assert values["market"] == 30
    assert values["lac_tp"] == -11
    assert values["closing"] - values["opening"] == 19
    assert values["residual"] == 0


def test_R019_public_gross_basis_and_undisclosed_rff(clean: Ledger) -> None:
    metadata = tuple(
        m.model_copy(update={"value": "public_disclosure"})
        if m.name == "variant"
        else m
        for m in clean.metadata
    )
    public = clean.model_copy(update={"metadata": metadata})
    definition = next(b for b in capital(public) if b.id == "scr_modules")
    expressions = {line.id: line.expression for line in definition.lines}
    market = expressions["market"]
    assert isinstance(market, SubtractExpr)
    for operand in (market.left, market.right):
        assert isinstance(operand, FactExpr)
        assert (operand.ref.table, operand.ref.column) == ("S.25.01.21.01", "C0110")
    rff = expressions["rff_map"]
    assert isinstance(rff, SubtractExpr)
    assert isinstance(rff.left, MissingExpr)
    assert rff.left.template == "S.25.01" and rff.left.period == "closing"


@pytest.mark.parametrize("period", ["opening", "closing"])
def test_R008_excess_failure_preserves_independent_own_funds_lines(
    clean: Ledger, period: Period
) -> None:
    ledger = _edit_amounts(
        clean, {(period, "S.23.01.01.02", "R0700", "C0060"): Decimal(9)}, add=True
    )
    result = analyze(ledger)
    for bridge in result.bridges:
        bridge_id = bridge.definition.id
        if bridge_id == "eligible_own_funds":
            dependent = {"excess", "residual"}
        elif bridge_id == f"{period}_excess_to_eligible":
            dependent = {"residual"}
        elif bridge_id.endswith("_excess_to_eligible"):
            dependent = set()
        else:
            continue
        for line in bridge.lines:
            if line.definition.id in dependent:
                assert line.result.status == "withheld"
                assert f"{period}_excess_consistency" in (line.result.reason or "")
            else:
                assert line.result.status == "value"
