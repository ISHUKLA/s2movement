"""Article 82 observations and conservative conclusions from cited S.23.01 facts."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from functools import cache
from typing import Literal

from s2movement.bridge_dsl import fact, sub, summed
from s2movement.check_catalog import ROOT
from s2movement.engine import (
    EvalValue,
    Expr,
    ScaleExpr,
    _eval,
    _unique_citations,
)
from s2movement.gate import PERIODS
from s2movement.models import Ledger, Period

Status = Literal["binding", "not_binding", "indeterminate"]
TABLE = "S.23.01.01.01"
# All selectors are present in cells.csv. Restricted Tier 1's excess treatment
# remains unverified in VERIFICATION.md §3, so it has no binding decision rule.
COLUMNS = {
    "article82_3": ("C0030",),
    "article82_1_b": ("C0050",),
    "article82_1_c": ("C0040", "C0050"),
}


REASONS = {
    "binding": (
        "Supply exceeds the bound and eligible funds reach it at source precision. "
        "The competing limit has headroom."
    ),
    "not_binding": "Reported supply has headroom under this limit.",
    "indeterminate": (
        "Reported precision, missing evidence or another restriction "
        "prevents attribution to this limit."
    ),
}
RESTRICTED_REASON = (
    "VERIFICATION.md §3 does not confirm how excess restricted Tier 1 is reported."
)


@dataclass(frozen=True)
class LegalRule:
    id: str
    fraction: Decimal
    operator: str
    article: str
    source_file: str
    source_location: str
    boundary: str
    label: str
    denominator: str


@dataclass(frozen=True)
class Decision:
    status: Status
    conditions: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class TierAssessment:
    id: str
    period: Period
    rule: LegalRule
    amounts: dict[str, EvalValue]
    expressions: dict[str, Expr]
    precision: Decimal | None
    status: Status
    reason: str
    decisions: tuple[Decision, ...]
    reported_compliance: str
    effect: EvalValue


@dataclass(frozen=True)
class TierChange:
    id: str
    opening_status: Status
    closing_status: Status
    direction: str
    observed_adjustment_change: EvalValue
    effect: EvalValue


@cache
def legal_rules() -> dict[str, LegalRule]:
    with (ROOT / "mappings/2.8.2/legal_limits.csv").open(encoding="utf-8") as stream:
        return {
            r["id"]: LegalRule(
                r["id"],
                Decimal(r["fraction"]),
                r["operator"],
                r["legal_location"],
                r["source_file"],
                r["source_location"],
                r["boundary"],
                r["left_side"],
                r["denominator"],
            )
            for r in csv.DictReader(stream)
            if r["id"] in COLUMNS
        }


def compare(a: Decimal | str, operator: str, b: Decimal | str) -> bool:
    if operator == "==":
        return a == b
    assert isinstance(a, Decimal) and isinstance(b, Decimal)
    if operator == "<":
        return a < b
    if operator == "<=":
        return a <= b
    if operator == ">":
        return a > b
    if operator == ">=":
        return a >= b
    raise ValueError(f"Unsupported legal comparison {operator}")


def decide(decisions: tuple[Decision, ...], values: dict[str, Decimal | str]) -> Status:
    for decision in decisions:
        passed = True
        for left, op, right in decision.conditions:
            rhs = (
                values[right]
                if right in values
                else (Decimal(0) if right == "0" else right)
            )
            passed = passed and compare(values[left], op, rhs)
        if passed:
            return decision.status
    return "indeterminate"


def decision_rules(rule: LegalRule) -> tuple[Decision, ...]:
    if rule.id == "article82_3":
        return ()
    valid = (
        ("denominator", ">", "0"),
        ("available", ">=", "0"),
        ("eligible", ">=", "0"),
        ("eligible", "<=", "available"),
        ("eligible", rule.operator, "bound"),
    )
    slack = Decision("not_binding", valid + (("available_headroom", ">", "precision"),))
    binding = valid + (
        ("supply_excess", ">", "precision"),
        ("eligible", "==", "max_reportable"),
    )
    if rule.id == "article82_1_b":
        return slack, Decision(
            "binding", binding + (("other_headroom", ">", "precision"),)
        )
    return (
        slack,
        Decision(
            "not_binding",
            valid
            + (
                ("tier3_status", "==", "binding"),
                ("effective_headroom", ">", "precision"),
                ("eligible", "==", "available_after_tier3"),
            ),
        ),
        Decision("binding", binding + (("tier3_status", "==", "not_binding"),)),
    )


def _expressions(ledger: Ledger, period: Period, rule: LegalRule) -> dict[str, Expr]:
    def tier(row: str, columns: tuple[str, ...]) -> Expr:
        return summed(fact(ledger, period, TABLE, row, c) for c in columns)

    columns = COLUMNS[rule.id]
    available = tier("R0500", columns)
    eligible = tier("R0540", columns)
    scr = fact(ledger, period, TABLE, "R0580")
    denominator = tier("R0540", ("C0020", "C0030")) if rule.id == "article82_3" else scr
    bound = ScaleExpr(denominator, rule.fraction)
    combined_bound = ScaleExpr(scr, legal_rules()["article82_1_c"].fraction)
    after_t3 = summed((tier("R0500", ("C0040",)), tier("R0540", ("C0050",))))
    return {
        "available": available,
        "eligible": eligible,
        "denominator": denominator,
        "bound": bound,
        "headroom": sub(bound, eligible),
        "available_headroom": sub(bound, available),
        "supply_excess": sub(available, bound),
        "observed_adjustment": sub(eligible, available),
        "other_headroom": sub(combined_bound, tier("R0540", ("C0040", "C0050"))),
        "available_after_tier3": after_t3,
        "effective_headroom": sub(bound, after_t3),
    }


def assess_limits(ledger: Ledger) -> tuple[TierAssessment, ...]:
    results = []
    for period in PERIODS:
        tier3_status: Status = "indeterminate"
        for key in ("article82_1_b", "article82_1_c", "article82_3"):
            rule = legal_rules()[key]
            expressions = _expressions(ledger, period, rule)
            amounts = {
                k: _eval(
                    ledger,
                    expr,
                    "Eligible minus available"
                    if k == "observed_adjustment"
                    else k.replace("_", " "),
                    f"{period}_{key}/{k}",
                )
                for k, expr in expressions.items()
            }
            required = ("available", "eligible", "denominator")
            precision_values = [amounts[k].precision for k in required]
            precision = (
                max(p for p in precision_values if p is not None)
                if all(p is not None for p in precision_values)
                else None
            )
            bound_amount = amounts["bound"]
            max_reportable = replace(
                bound_amount,
                status="indeterminate",
                value=None,
                exact_value=None,
                reason="Source precision or legal bound is unavailable.",
                sign="Largest source-precision multiple within the mapped bound",
                citations=_unique_citations(
                    tuple(c for k in required for c in amounts[k].citations)
                ),
            )
            if precision is not None and bound_amount.value is not None:
                quotient = bound_amount.value / precision
                if rule.operator == "<":
                    maximum = (
                        quotient.to_integral_value(rounding=ROUND_CEILING) - 1
                    ) * precision
                else:
                    maximum = (
                        quotient.to_integral_value(rounding=ROUND_FLOOR) * precision
                    )
                max_reportable = replace(
                    max_reportable, status="value", value=maximum, reason=None
                )
            amounts["max_reportable"] = max_reportable
            decisions = decision_rules(rule)
            relevant = {
                name
                for d in decisions
                for c in d.conditions
                for name in (c[0], c[2])
                if name in amounts
            }
            status: Status = "indeterminate"
            numeric = {k: v.value for k, v in amounts.items() if v.value is not None}
            if precision is not None and relevant <= numeric.keys():
                values: dict[str, Decimal | str] = dict(numeric)
                values.update(precision=precision, tier3_status=tier3_status)
                status = decide(decisions, values)
            eligible, bound = amounts["eligible"], amounts["bound"]
            compliance = "indeterminate"
            if eligible.value is not None and bound.value is not None:
                compliance = (
                    "pass"
                    if compare(eligible.value, rule.operator, bound.value)
                    else "fail"
                )
            reason = RESTRICTED_REASON if key == "article82_3" else REASONS[status]
            if key == "article82_1_b":
                tier3_status = status
            adjustment = amounts["observed_adjustment"]
            effect = replace(
                adjustment,
                citations=_unique_citations(
                    tuple(
                        c
                        for k in sorted(set(required) | relevant)
                        for c in amounts[k].citations
                    )
                ),
                sign="Effect of the evidenced limit on eligible own funds",
            )
            if status == "not_binding":
                effect = replace(effect, value=Decimal(0), exact_value=None)
            elif status == "indeterminate":
                effect = replace(
                    effect,
                    status="indeterminate",
                    value=None,
                    exact_value=None,
                    reason=reason,
                )
            results.append(
                TierAssessment(
                    f"{period}_{key}",
                    period,
                    rule,
                    amounts,
                    expressions,
                    precision,
                    status,
                    reason,
                    decisions,
                    compliance,
                    effect,
                )
            )
    return tuple(results)


def _change(before: EvalValue, after: EvalValue, ident: str) -> EvalValue:
    citations = _unique_citations(before.citations + after.citations)
    if before.value is None or after.value is None:
        return replace(
            after,
            status="indeterminate",
            value=None,
            exact_value=None,
            citations=citations,
            expression_id=ident,
            reason="At least one period's limit effect is indeterminate.",
        )
    return replace(
        after,
        value=after.value - before.value,
        exact_value=None,
        citations=citations,
        expression_id=ident,
        sign="Closing minus opening",
    )


def transition(before: Status, after: Status) -> str:
    if before == after:
        return "unchanged"
    if after == "indeterminate":
        return "became_indeterminate"
    if before == "indeterminate":
        return "resolved_to_" + after
    return "newly_binding" if after == "binding" else "released"


def changes(tiers: tuple[TierAssessment, ...]) -> tuple[TierChange, ...]:
    results = []
    for key in COLUMNS:
        before, after = (
            next(t for t in tiers if t.period == p and t.rule.id == key)
            for p in PERIODS
        )
        results.append(
            TierChange(
                key,
                before.status,
                after.status,
                transition(before.status, after.status),
                _change(
                    before.amounts["observed_adjustment"],
                    after.amounts["observed_adjustment"],
                    key,
                ),
                _change(before.effect, after.effect, key),
            )
        )
    return tuple(results)
