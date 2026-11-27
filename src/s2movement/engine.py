"""Evaluate cited comparisons and bridge expressions over the immutable fact ledger."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import TYPE_CHECKING, Literal

from s2movement.check_catalog import CheckRule, catalog
from s2movement.gate import PERIODS, Gate, evaluate_gate, metadata, metadata_citations
from s2movement.models import (
    MAX_EXACT_EXCEL_INTEGER,
    Citation,
    Ledger,
    Period,
)

if TYPE_CHECKING:
    from s2movement.tier_limits import TierAssessment, TierChange

ValueStatus = Literal["value", "unavailable", "withheld", "indeterminate"]
CheckStatus = Literal[
    "pass", "fail", "blocked", "withheld", "unavailable", "indeterminate"
]

SII_VALUE = {"s2c_VG": "s2c_x80"}
NON_LINKED_INVESTMENTS = {**SII_VALUE, "s2c_BL": "s2c_x91"}
LINKED_ASSETS = {**SII_VALUE, "s2c_BL": "s2c_x119"}


@dataclass(frozen=True)
class CellRef:
    period: Period
    table: str
    row: str
    column: str
    dimensions: dict[str, str]
    coordinate_context: str | None = None


@dataclass(frozen=True)
class FactExpr:
    ref: CellRef


@dataclass(frozen=True)
class AddExpr:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class SubtractExpr:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class NegateExpr:
    operand: Expr


@dataclass(frozen=True)
class DivideExpr:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class PercentExpr:
    operand: Expr


@dataclass(frozen=True)
class ScaleExpr:
    operand: Expr
    factor: Decimal


@dataclass(frozen=True)
class MissingExpr:
    template: str
    reason: str
    period: Period


type Expr = (
    FactExpr
    | AddExpr
    | SubtractExpr
    | NegateExpr
    | DivideExpr
    | PercentExpr
    | MissingExpr
    | ScaleExpr
)


@dataclass(frozen=True)
class LineDefinition:
    id: str
    label: str
    expression: Expr
    sign: str
    role: Literal["reported_balance", "movement", "residual"]
    dependencies: tuple[str, ...] = ()
    component_rows: tuple[str, ...] = ()
    covered_rows: tuple[str, ...] = ()


@dataclass(frozen=True)
class BridgeDefinition:
    id: str
    version: str
    label: str
    lines: tuple[LineDefinition, ...]
    tolerance_policy: str
    dependencies: tuple[str, ...] = ()
    period: Period | None = None
    unit: str = "money"
    formula_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalValue:
    status: ValueStatus
    value: Decimal | None
    currency: str | None
    unit_scale: Decimal | None
    precision: Decimal | None
    sign: str
    citations: tuple[Citation, ...]
    reason: str | None = None
    missing_template: str | None = None
    expression_id: str | None = None
    exact_value: Fraction | None = None
    missing_period: Period | None = None


@dataclass(frozen=True)
class Tolerance:
    value: Decimal
    currency: str
    unit_scale: Decimal
    policy: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Comparison:
    id: str
    label: str
    status: CheckStatus
    left: EvalValue
    right: EvalValue
    discrepancy: EvalValue
    tolerance: Tolerance | None
    period: Period
    left_expr: Expr | None
    right_expr: Expr | None
    withholds: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class RatioValidation:
    id: str
    period: Period
    status: Literal["pass", "fail"]
    amount: EvalValue
    expression: Expr
    message: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class BridgeLine:
    definition: LineDefinition
    result: EvalValue
    status: CheckStatus | ValueStatus
    check_ids: tuple[str, ...] = ()
    validation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BridgeResult:
    status: CheckStatus
    definition: BridgeDefinition
    lines: tuple[BridgeLine, ...]
    residual_status: CheckStatus
    tolerance: Tolerance
    residual_discrepancy: EvalValue


@dataclass(frozen=True)
class ScheduleDefinition:
    id: str
    label: str
    opening: Expr
    closing: Expr
    dependencies: tuple[str, ...] = ()
    sign: str = "Closing minus opening"
    category: str = "reported_detail"
    bridge_id: str | None = None
    operands: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleResult:
    id: str
    label: str
    opening: EvalValue
    closing: EvalValue
    movement: EvalValue
    opening_expr: Expr
    closing_expr: Expr
    movement_expr: Expr
    check_ids: tuple[str, ...] = ()
    category: str = "reported_detail"
    bridge_id: str | None = None
    operands: tuple[str, ...] = ()


@dataclass(frozen=True)
class LinkedMateriality:
    period: Period
    status: Literal["material", "not_material", "indeterminate"]
    linked_assets: EvalValue
    total_assets: EvalValue
    threshold: EvalValue
    linked_expr: Expr
    total_expr: Expr
    floor_eur: Decimal
    fraction: Decimal
    source: str = "tests/fixtures/thresholds.yaml#rules/linked_materiality"


@dataclass(frozen=True)
class UnsupportedSplit:
    id: str
    period: Period
    reason: str
    template: str
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class Analysis:
    ledger: Ledger
    gate: Gate
    comparisons: tuple[Comparison, ...]
    bridge: BridgeResult
    warnings: tuple[str, ...]
    unimplemented: tuple[str, ...]
    bridges: tuple[BridgeResult, ...] = ()
    schedules: tuple[ScheduleResult, ...] = ()
    unsupported_splits: tuple[UnsupportedSplit, ...] = ()
    linked_materiality: tuple[LinkedMateriality, ...] = ()
    tier_limits: tuple[TierAssessment, ...] = ()
    tier_changes: tuple[TierChange, ...] = ()
    ratio_validations: tuple[RatioValidation, ...] = ()


def _cell(
    period: Period,
    table: str,
    row: str,
    column: str,
    dimensions: dict[str, str],
    coordinate_context: str | None = None,
) -> FactExpr:
    return FactExpr(CellRef(period, table, row, column, dimensions, coordinate_context))


def _delta(table: str, row: str, column: str, dimensions: dict[str, str]) -> Expr:
    return SubtractExpr(
        _cell("closing", table, row, column, dimensions),
        _cell("opening", table, row, column, dimensions),
    )


def _other_assets(period: Period) -> Expr:
    return SubtractExpr(
        SubtractExpr(
            _cell(period, "S.02.01.01.01", "R0500", "C0010", SII_VALUE),
            _cell(period, "S.02.01.01.01", "R0070", "C0010", NON_LINKED_INVESTMENTS),
        ),
        _cell(period, "S.02.01.01.01", "R0220", "C0010", LINKED_ASSETS),
    )


BRIDGE_DEFINITION = BridgeDefinition(
    id="s02_excess_assets_over_liabilities",
    version="0.1",
    label="Excess of assets over liabilities",
    lines=(
        LineDefinition(
            "opening_excess",
            "Opening excess of assets over liabilities",
            _cell("opening", "S.02.01.01.01", "R1000", "C0010", SII_VALUE),
            "As reported; positive is excess of assets over liabilities",
            "reported_balance",
        ),
        LineDefinition(
            "investments_movement",
            "Investments excluding linked assets",
            _delta("S.02.01.01.01", "R0070", "C0010", NON_LINKED_INVESTMENTS),
            "Positive movement increases assets and excess",
            "movement",
        ),
        LineDefinition(
            "linked_assets_movement",
            "Assets held for index-linked and unit-linked contracts",
            _delta("S.02.01.01.01", "R0220", "C0010", LINKED_ASSETS),
            "Positive movement increases assets and excess",
            "movement",
        ),
        LineDefinition(
            "other_assets_movement",
            "Other assets (derived remainder)",
            SubtractExpr(_other_assets("closing"), _other_assets("opening")),
            "Positive movement increases assets and excess",
            "movement",
        ),
        LineDefinition(
            "liabilities_contribution",
            "Total liabilities contribution",
            NegateExpr(_delta("S.02.01.01.01", "R0900", "C0010", SII_VALUE)),
            "Negative liability movement reduces excess",
            "movement",
        ),
        LineDefinition(
            "residual",
            "Unexplained residual",
            SubtractExpr(
                SubtractExpr(
                    _cell("closing", "S.02.01.01.01", "R1000", "C0010", SII_VALUE),
                    _cell("opening", "S.02.01.01.01", "R1000", "C0010", SII_VALUE),
                ),
                AddExpr(
                    AddExpr(
                        _delta(
                            "S.02.01.01.01", "R0070", "C0010", NON_LINKED_INVESTMENTS
                        ),
                        _delta("S.02.01.01.01", "R0220", "C0010", LINKED_ASSETS),
                    ),
                    AddExpr(
                        SubtractExpr(
                            _other_assets("closing"), _other_assets("opening")
                        ),
                        NegateExpr(
                            _delta("S.02.01.01.01", "R0900", "C0010", SII_VALUE)
                        ),
                    ),
                ),
            ),
            "Closing less opening less all signed movements; displayed explicitly",
            "residual",
        ),
        LineDefinition(
            "closing_excess",
            "Closing excess of assets over liabilities",
            _cell("closing", "S.02.01.01.01", "R1000", "C0010", SII_VALUE),
            "As reported; positive is excess of assets over liabilities",
            "reported_balance",
        ),
    ),
    tolerance_policy=(
        "one reporting unit; after confirmed conversion, one unit of the "
        "coarser source precision"
    ),
)


def _unique_citations(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
    seen: set[tuple[str, str, str, str, str, str | None]] = set()
    result: list[Citation] = []
    for citation in citations:
        key = (
            citation.period,
            citation.file_id,
            citation.sheet,
            citation.cell,
            citation.row or "",
            citation.context_id,
        )
        if key not in seen:
            seen.add(key)
            result.append(citation)
    return tuple(result)


def _empty(
    status: ValueStatus,
    sign: str,
    reason: str,
    expression_id: str,
    template: str | None = None,
) -> EvalValue:
    return EvalValue(
        status, None, None, None, None, sign, (), reason, template, expression_id
    )


def _lookup(ledger: Ledger, ref: CellRef, sign: str, expression_id: str) -> EvalValue:
    matches = [
        fact
        for fact in ledger.facts
        if fact.period == ref.period
        and fact.table == ref.table
        and fact.row == ref.row
        and fact.column == ref.column
        and fact.dimensions == ref.dimensions
        and fact.coordinate_context == ref.coordinate_context
    ]
    if not matches:
        return replace(
            _empty(
                "unavailable",
                sign,
                f"{ref.period} {ref.table} {ref.row}/{ref.column} "
                "with the required context is absent",
                expression_id,
                ref.table[:7],
            ),
            missing_period=ref.period,
        )
    if len(matches) != 1:
        return EvalValue(
            "indeterminate",
            None,
            None,
            None,
            None,
            sign,
            tuple(fact.citation for fact in matches),
            "more than one fact matches the full coordinate and context",
            None,
            expression_id,
        )
    fact = matches[0]
    return EvalValue(
        "value",
        fact.resolved_value,
        "ratio" if fact.kind == "ratio" else fact.currency,
        fact.resolved_unit_scale,
        fact.resolved_precision,
        sign,
        (fact.citation, fact.conversion.citation)
        if fact.conversion
        else (fact.citation,),
        None,
        None,
        expression_id,
    )


def _eval(ledger: Ledger, expression: Expr, sign: str, expression_id: str) -> EvalValue:
    if isinstance(expression, FactExpr):
        return _lookup(ledger, expression.ref, sign, expression_id)
    if isinstance(expression, MissingExpr):
        return replace(
            _empty(
                "unavailable",
                sign,
                expression.reason,
                expression_id,
                expression.template,
            ),
            missing_period=expression.period,
        )
    if isinstance(expression, ScaleExpr):
        operand = _eval(ledger, expression.operand, sign, expression_id)
        if operand.value is None:
            return operand
        return replace(
            operand,
            value=operand.value * expression.factor,
            exact_value=Fraction(operand.value) * Fraction(expression.factor),
        )
    if isinstance(expression, (NegateExpr, PercentExpr)):
        operand = _eval(ledger, expression.operand, sign, expression_id)
        if operand.status != "value" or operand.value is None:
            return operand
        percent = isinstance(expression, PercentExpr)
        multiplier = 100 if percent else -1
        return replace(
            operand,
            value=operand.value * multiplier,
            currency="pp" if percent else operand.currency,
            exact_value=None
            if operand.exact_value is None
            else operand.exact_value * multiplier,
        )
    left = _eval(ledger, expression.left, sign, expression_id)
    right = _eval(ledger, expression.right, sign, expression_id)
    citations = _unique_citations(left.citations + right.citations)
    if left.status != "value" or right.status != "value":
        failed = next(item for item in (left, right) if item.status != "value")
        return EvalValue(
            failed.status,
            None,
            failed.currency,
            failed.unit_scale,
            failed.precision,
            sign,
            citations,
            failed.reason,
            failed.missing_template,
            expression_id,
            missing_period=failed.missing_period,
        )
    if left.currency != right.currency or left.unit_scale != right.unit_scale:
        return EvalValue(
            "indeterminate",
            None,
            None,
            None,
            None,
            sign,
            citations,
            "arithmetic operands have incompatible currency units",
            None,
            expression_id,
        )
    assert left.value is not None and right.value is not None
    if isinstance(expression, DivideExpr):
        if right.value <= 0:
            return EvalValue(
                "indeterminate",
                None,
                "ratio",
                Decimal(1),
                None,
                sign,
                citations,
                "SCR must be positive",
                expression_id=expression_id,
            )
        exact = Fraction(left.value) / Fraction(right.value)
        with localcontext() as ctx:
            ctx.prec = 50
            decimal_value = Decimal(exact.numerator) / Decimal(exact.denominator)
        return EvalValue(
            "value",
            decimal_value,
            "ratio",
            Decimal(1),
            None,
            sign,
            citations,
            expression_id=expression_id,
            exact_value=exact,
        )
    if left.exact_value is not None or right.exact_value is not None:
        a = left.exact_value if left.exact_value is not None else Fraction(left.value)
        b = (
            right.exact_value
            if right.exact_value is not None
            else Fraction(right.value)
        )
        exact = a + b if isinstance(expression, AddExpr) else a - b
        with localcontext() as ctx:
            ctx.prec = 50
            value = Decimal(exact.numerator) / Decimal(exact.denominator)
        return replace(
            left,
            value=value,
            exact_value=exact,
            citations=citations,
            expression_id=expression_id,
            sign=sign,
        )
    value = (
        left.value + right.value
        if isinstance(expression, AddExpr)
        else left.value - right.value
    )
    if value != value.to_integral_value() or abs(value) > MAX_EXACT_EXCEL_INTEGER:
        return EvalValue(
            "indeterminate",
            None,
            left.currency,
            left.unit_scale,
            None,
            sign,
            citations,
            "result exceeds the supported exact Excel integer range",
            None,
            expression_id,
        )
    return EvalValue(
        "value",
        value,
        left.currency,
        left.unit_scale,
        max(left.precision or Decimal(1), right.precision or Decimal(1)),
        sign,
        citations,
        None,
        None,
        expression_id,
    )


def _tolerance(ledger: Ledger, period: Period | None = None) -> Tolerance:
    money_facts = [fact for fact in ledger.facts if fact.table.startswith("S.02.01")]
    if period is not None:
        money_facts = [fact for fact in money_facts if fact.period == period]
    has_conversion = any(
        period is None or item.period == period for item in ledger.conversions
    )
    precision = (
        max(
            (
                fact.resolved_precision
                for fact in money_facts
                if fact.resolved_precision is not None
            ),
            default=Decimal(1),
        )
        if has_conversion
        else Decimal(1)
    )
    scale = money_facts[0].resolved_unit_scale if money_facts else Decimal(1)
    currency = (
        money_facts[0].currency
        if money_facts
        else (metadata(ledger, "closing", "currency") or "UNKNOWN")
    )
    citations = tuple(
        citation
        for fact in ledger.metadata
        if fact.name in {"money_unit_scale", "money_precision"}
        and (period is None or fact.period == period)
        for citation in (
            fact.citation,
            *((fact.correction.citation,) if fact.correction is not None else ()),
        )
    )
    citations += tuple(
        item.citation
        for item in ledger.conversions
        if period is None or item.period == period
    )
    return Tolerance(
        precision,
        currency,
        scale,
        "one reporting unit; after confirmed conversion, one unit of the "
        "coarser source precision",
        _unique_citations(citations),
    )


def _operand(period: Period, tokens: list[str], public: bool, operation: str) -> Expr:
    expressions: list[Expr] = []
    for token in tokens:
        address = catalog().address(token, public)
        selector = catalog().selectors[address]
        cell = _cell(period, *address, selector.dimensions, selector.coordinate)
        expressions.append(NegateExpr(cell) if token.startswith("-") else cell)
    if operation == "divide":
        left, right = expressions
        return DivideExpr(left, right)
    result = expressions[0]
    for term in expressions[1:]:
        result = AddExpr(result, term)
    return result


def _comparison(ledger: Ledger, period: Period, rule: CheckRule) -> Comparison:
    public = metadata(ledger, period, "variant") == "public_disclosure"
    ident = f"{period}_{rule.id}"
    label = f"{period.title()} {rule.label}"
    sign = "Reported left value minus the right-hand comparison value"
    is_ratio = rule.tolerance == "reported_ratio_precision"
    tolerance: Tolerance | None = None if is_ratio else _tolerance(ledger, period)
    left_expr = right_expr = None
    tables = {
        catalog().address(token, public)[0][:7] for token in rule.left + rule.right
    } | {catalog().tables[alias][int(public)][:7] for alias in rule.required_tables}
    inp = next(item for item in ledger.inputs if item.period == period)
    missing = sorted(tables - set(inp.templates))
    gap = rule.gap or (rule.public_gap if public else "")
    withholds = tuple(rule.withholds)
    if gap:
        status: Literal["unavailable", "indeterminate"] = (
            "unavailable" if missing else "indeterminate"
        )
        reason = f"{period}: missing {', '.join(missing)}." if missing else gap
        value = _empty(status, sign, reason, ident, missing[0] if missing else None)
        return Comparison(
            ident,
            label,
            status,
            value,
            value,
            value,
            tolerance,
            period,
            None,
            None,
            withholds,
            reason,
        )
    left_expr = _operand(period, rule.left, public, "sum")
    right_expr = _operand(period, rule.right, public, rule.right_operation)
    left_val = _eval(ledger, left_expr, rule.label + " (left)", ident + "_left")
    right_val = _eval(ledger, right_expr, rule.label + " (right)", ident + "_right")
    refs = _unique_citations(left_val.citations + right_val.citations)
    if is_ratio and left_val.precision is not None:
        tolerance = Tolerance(
            left_val.precision,
            "ratio",
            Decimal(1),
            "One unit of the reported ratio's last decimal place",
            _unique_citations(
                metadata_citations(ledger, ("ratio_precision",), (period,))
            ),
        )
    message = rule.message
    check: CheckStatus
    if left_val.value is None or right_val.value is None:
        missing_val = left_val if left_val.value is None else right_val
        assert missing_val.status != "value"
        check = missing_val.status
        message = f"{period}: {missing_val.reason}."
        diff = replace(missing_val, citations=refs, sign=sign, expression_id=ident)
    else:
        exact = Fraction(left_val.value) - (
            right_val.exact_value
            if right_val.exact_value is not None
            else Fraction(right_val.value)
        )
        with localcontext() as ctx:
            ctx.prec = 50
            delta = Decimal(exact.numerator) / Decimal(exact.denominator)
        diff = EvalValue(
            "value",
            delta,
            left_val.currency,
            left_val.unit_scale,
            None if tolerance is None else tolerance.value,
            sign,
            refs,
            expression_id=ident,
            exact_value=exact if is_ratio else None,
        )
        if tolerance is None:
            check = "indeterminate"
            message = f"{period.title()} reported ratio precision is unavailable."
        else:
            check = "pass" if abs(exact) <= Fraction(tolerance.value) else "fail"
            if check == "fail":
                message = (
                    f"{label}: reconciliation failure. Left {left_val.value}, "
                    f"right {right_val.value}, signed difference {delta:+f}, "
                    f"tolerance {tolerance.value}. {rule.message}"
                )
    return Comparison(
        ident,
        label,
        check,
        left_val,
        right_val,
        diff,
        tolerance,
        period,
        left_expr,
        right_expr,
        withholds,
        message,
    )


def _bridge_expr(ledger: Ledger, expr: Expr) -> Expr:
    if isinstance(expr, FactExpr):
        ref = expr.ref
        if (
            metadata(ledger, ref.period, "variant") == "public_disclosure"
            and ref.table == "S.02.01.01.01"
        ):
            return FactExpr(replace(ref, table=catalog().tables["BS"][1]))
        return expr
    if isinstance(expr, MissingExpr):
        return expr
    if isinstance(expr, (NegateExpr, PercentExpr, ScaleExpr)):
        return replace(expr, operand=_bridge_expr(ledger, expr.operand))
    return replace(
        expr,
        left=_bridge_expr(ledger, expr.left),
        right=_bridge_expr(ledger, expr.right),
    )


def _withheld(
    result: EvalValue, reason: str, citations: tuple[Citation, ...] | None = None
) -> EvalValue:
    return EvalValue(
        "withheld",
        None,
        result.currency,
        result.unit_scale,
        result.precision,
        result.sign,
        result.citations if citations is None else citations,
        reason,
        None,
        result.expression_id,
    )


def _checks_for(
    comparisons: tuple[Comparison, ...],
    names: tuple[str, ...],
    period: Period | None = None,
) -> tuple[Comparison, ...]:
    return tuple(
        item
        for item in comparisons
        if (period is None or item.period == period)
        and (item.id in names or item.id.removeprefix(item.period + "_") in names)
        and item.status in {"pass", "fail"}
    )


def _apply_checks(value: EvalValue, checks: tuple[Comparison, ...]) -> EvalValue:
    failures = [c for c in checks if c.status == "fail"]
    if not failures or value.status == "unavailable":
        return value
    return _withheld(
        value,
        "Reconciliation failure in " + ", ".join(c.id for c in failures),
        _unique_citations(
            value.citations
            + tuple(
                citation for item in failures for citation in item.discrepancy.citations
            )
        ),
    )


def _evaluate_bridge(
    ledger: Ledger,
    definition: BridgeDefinition,
    comparisons: tuple[Comparison, ...],
    validations: tuple[RatioValidation, ...] = (),
) -> BridgeResult:
    tolerance = (
        Tolerance(Decimal(0), "pp", Decimal(1), definition.tolerance_policy, ())
        if definition.unit == "pp"
        else _tolerance(ledger, definition.period)
    )
    lines = []
    applicable = validations if definition.id == "solvency_ratio" else ()
    failures = tuple(v for v in applicable if v.status == "fail")
    for line in definition.lines:
        dependencies = line.dependencies
        if line.role != "reported_balance":
            dependencies += definition.dependencies
        checks = _checks_for(comparisons, dependencies, definition.period)
        if failures and line.role != "reported_balance":
            # A comparison that could not run on invalid source data must be
            # rerun, not silently removed from a repaired workbook's dependencies.
            checks = tuple(c for c in comparisons if c.id.endswith("_ratio"))
        value = _apply_checks(
            _eval(ledger, line.expression, line.sign, line.id), checks
        )
        if definition.unit == "pp":
            value = replace(value, currency="pp", unit_scale=Decimal(1))
        if failures:
            value = _withheld(
                value,
                "Validation failure: "
                + "; ".join(f"{v.id}: {v.message}" for v in failures),
                _unique_citations(
                    value.citations + tuple(c for v in failures for c in v.citations)
                ),
            )
        lines.append(
            BridgeLine(
                line,
                value,
                value.status,
                tuple(c.id for c in checks),
                tuple(v.id for v in applicable),
            )
        )
    residual = next(line.result for line in lines if line.definition.role == "residual")
    status: CheckStatus
    if residual.status == "value":
        assert residual.value is not None
        discrepancy = residual.exact_value
        if discrepancy is None:
            discrepancy = Fraction(residual.value)
        status = "pass" if abs(discrepancy) <= Fraction(tolerance.value) else "fail"
    else:
        status = residual.status
    return BridgeResult(status, definition, tuple(lines), status, tolerance, residual)


def _evaluate_schedule(
    ledger: Ledger, definition: ScheduleDefinition, comparisons: tuple[Comparison, ...]
) -> ScheduleResult:
    movement = SubtractExpr(definition.closing, definition.opening)
    checks = _checks_for(comparisons, definition.dependencies)
    return ScheduleResult(
        definition.id,
        definition.label,
        _eval(ledger, definition.opening, "Opening balance", definition.id),
        _eval(ledger, definition.closing, "Closing balance", definition.id),
        _apply_checks(_eval(ledger, movement, definition.sign, definition.id), checks),
        definition.opening,
        definition.closing,
        movement,
        tuple(c.id for c in checks),
        definition.category,
        definition.bridge_id,
        definition.operands,
    )


def _restricted_tier_splits(ledger: Ledger) -> tuple[UnsupportedSplit, ...]:
    from s2movement.bridge_dsl import fact

    result = []
    for period in PERIODS:
        ident = "restricted_tier1_excess_reclassified_to_tier2"
        instrument, eligible = (
            _eval(
                ledger,
                fact(ledger, period, "S.23.01.01.01", row, "C0030"),
                "Reported restricted Tier 1 amount",
                ident,
            )
            for row in ("R0140", "R0540")
        )
        if (
            instrument.value is not None
            and eligible.value is not None
            and instrument.value > eligible.value
        ):
            result.append(
                UnsupportedSplit(
                    ident,
                    period,
                    "S.23.01 does not separately report how much restricted Tier 1 "
                    "excess was reclassified to Tier 2.",
                    "S.23.01",
                    _unique_citations(instrument.citations + eligible.citations),
                )
            )
    return tuple(result)


def analyze(ledger: Ledger) -> Analysis:
    """Stop before movement calculations unless the ordered pair passes the gate."""
    from s2movement.capital_bridges import capital, own_fund_splits, ratio_validations
    from s2movement.tier_limits import assess_limits, changes
    from s2movement.tp_bridges import (
        linked_materiality,
        schedules,
        tp,
        unsupported_splits,
    )

    gate = evaluate_gate(ledger)
    warnings = tuple(f.message for f in gate.findings if f.status == "warning")
    if gate.status == "blocked":
        stopped = _empty("withheld", "", "Comparability gate is blocked.", "gate")
        return Analysis(
            ledger,
            gate,
            (),
            BridgeResult(
                "blocked",
                BRIDGE_DEFINITION,
                (),
                "withheld",
                _tolerance(ledger),
                stopped,
            ),
            warnings,
            (),
        )
    comparisons = tuple(
        _comparison(ledger, period, rule)
        for rule in catalog().checks
        for period in PERIODS
    )
    definitions = capital(ledger) + tp(ledger)
    # The initial five-row input format supports a coarser but fully reported
    # balance sheet reconciliation. Expanded inputs use the itemised buckets.
    summary_rows = {"R0070", "R0220", "R0500", "R0900", "R1000"}
    if all(
        {f.row for f in ledger.facts if f.period == p and f.template == "S.02.01"}
        == summary_rows
        for p in PERIODS
    ):
        definitions[0] = replace(
            BRIDGE_DEFINITION,
            dependencies=("excess_consistency",),
            lines=tuple(
                replace(line, expression=_bridge_expr(ledger, line.expression))
                for line in BRIDGE_DEFINITION.lines
            ),
        )
    validations = ratio_validations(ledger)
    bridges = tuple(
        _evaluate_bridge(ledger, d, comparisons, validations) for d in definitions
    )
    materiality = linked_materiality(ledger)
    details = tuple(
        _evaluate_schedule(ledger, d, comparisons)
        for d in schedules(ledger, materiality)
    )
    tiers = assess_limits(ledger)
    return Analysis(
        ledger,
        gate,
        comparisons,
        bridges[0],
        warnings,
        (),
        bridges,
        details,
        _restricted_tier_splits(ledger)
        + tuple(unsupported_splits(ledger))
        + tuple(own_fund_splits(ledger)),
        materiality,
        tiers,
        changes(tiers),
        validations,
    )


def canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text
