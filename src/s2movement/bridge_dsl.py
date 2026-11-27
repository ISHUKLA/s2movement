"""Compose bridge formulas from versioned template cells and signed contributions."""

from collections.abc import Iterable
from functools import reduce

from s2movement.check_catalog import catalog
from s2movement.engine import (
    AddExpr,
    BridgeDefinition,
    CellRef,
    DivideExpr,
    Expr,
    FactExpr,
    LineDefinition,
    MissingExpr,
    NegateExpr,
    PercentExpr,
    SubtractExpr,
)
from s2movement.models import Ledger, Period

# Physical alternatives. Each requested intersection is checked against the mapping.
PUBLIC = {
    "S.02.01.01.01": "S.02.01.02.01",
    "S.12.01.01.01": "S.12.01.02.01",
    "S.22.01.01.01": "S.22.01.21.01",
    "S.23.01.01.01": "S.23.01.01.01",
    "S.23.01.01.02": "S.23.01.01.02",
    "S.25.01.01.01": "S.25.01.21.01",
    "S.25.01.01.02": "S.25.01.21.02",
}


def fact(
    ledger: Ledger, period: Period, table: str, row: str, col: str = "C0010"
) -> Expr:
    variant = ledger.metadata_value(period, "variant")
    if variant and variant.value == "public_disclosure":
        table = PUBLIC.get(table, table)
    selector = catalog().selectors.get((table, row, col))
    if selector is None:
        return MissingExpr(
            table[:7], f"{period} {table} does not report {row}/{col}.", period
        )
    return FactExpr(
        CellRef(period, table, row, col, selector.dimensions, selector.coordinate)
    )


add = AddExpr
sub = SubtractExpr
neg = NegateExpr
divide = DivideExpr
pp = PercentExpr


def summed(terms: Iterable[Expr]) -> Expr:
    return reduce(AddExpr, terms)


def component(
    id: str, label: str, expr: Expr, sign: str, dependencies: tuple[str, ...] = ()
) -> LineDefinition:
    return LineDefinition(id, label, expr, sign, "movement", dependencies)


def residual_bridge(
    id: str,
    label: str,
    opening: Expr,
    closing: Expr,
    movements: list[LineDefinition],
    *,
    dependencies: tuple[str, ...] = (),
    residual_dependencies: tuple[str, ...] = (),
    period: Period | None = None,
    unit: str = "money",
    formula_notes: tuple[str, ...] = (),
) -> BridgeDefinition:
    residual = sub(sub(closing, opening), summed(m.expression for m in movements))
    checks = tuple(
        dict.fromkeys(
            (*residual_dependencies, *(c for m in movements for c in m.dependencies))
        )
    )
    return BridgeDefinition(
        id,
        "1.0",
        label,
        (
            LineDefinition(
                "opening", "Opening", opening, "Opening balance", "reported_balance"
            ),
            *movements,
            LineDefinition(
                "residual",
                "Unexplained residual",
                residual,
                "Closing less opening and signed contributions",
                "residual",
                checks,
            ),
            LineDefinition(
                "closing", "Closing", closing, "Closing balance", "reported_balance"
            ),
        ),
        "D5 exact identity before presentation rounding"
        if unit == "pp"
        else "D3 reporting unit; coarser source precision after confirmed conversion",
        dependencies,
        period,
        unit,
        formula_notes,
    )
