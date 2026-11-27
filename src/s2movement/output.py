"""Cited JSON and a review workbook with live calculations over the raw ledger."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import xlsxwriter

from s2movement.engine import (
    AddExpr,
    Analysis,
    BridgeResult,
    Comparison,
    DivideExpr,
    EvalValue,
    Expr,
    FactExpr,
    MissingExpr,
    NegateExpr,
    PercentExpr,
    ScaleExpr,
    SubtractExpr,
    Tolerance,
    canonical_decimal,
)
from s2movement.gate import GateFinding
from s2movement.models import Citation, Ledger, Period
from s2movement.tier_limits import REASONS, TierAssessment

type RawKey = tuple[str, str, str, str, tuple[tuple[str, str], ...], str | None]
type RawRows = dict[RawKey, int]


def _citations(items: Iterable[Citation]) -> list[dict[str, Any]]:
    return [c.model_dump(mode="json", exclude_none=True) for c in items]


def _source_text(items: Iterable[Citation]) -> str:
    return "\n".join(
        f"[{c.period} | {c.table or c.sheet} | "
        f"{c.row or c.metadata_field or 'source'} | {c.column or c.cell}] "
        f"{c.file_id} {c.sheet}!{c.cell}"
        + (
            f" ({c.context_id}, {c.dimensions}, {c.coordinate_context or 'no Z'})"
            if c.context_id
            else ""
        )
        for c in items
    )


def _unit(currency: str | None, scale: Decimal | None) -> dict[str, Any] | None:
    if currency in {"ratio", "pp"}:
        return {
            "kind": "ratio" if currency == "ratio" else "percentage_points",
            "scale": "1",
        }
    if currency is None:
        return None
    return {
        "kind": "money",
        "currency": currency,
        "scale": canonical_decimal(scale) if scale is not None else None,
    }


def _amount(value: EvalValue) -> dict[str, Any]:
    number = None
    if value.value is not None:
        number = canonical_decimal(value.value)
        if value.exact_value is not None and value.exact_value != value.value:
            number = str(value.exact_value)
    result: dict[str, Any] = {
        "status": value.status,
        "value": number,
        "unit": _unit(value.currency, value.unit_scale),
        "precision": canonical_decimal(value.precision)
        if value.precision is not None
        else None,
        "sign": value.sign,
        "citations": _citations(value.citations),
    }
    for field in ("expression_id", "reason", "missing_template"):
        if (v := getattr(value, field)) is not None:
            result[field] = v
    if value.missing_period:
        result["period"] = value.missing_period
    return result


def _tolerance(t: Tolerance | None) -> dict[str, Any] | None:
    if t is None:
        return None
    return {
        "value": canonical_decimal(t.value),
        "unit": _unit(t.currency, t.unit_scale),
        "policy": t.policy,
        "citations": _citations(t.citations),
    }


def _finding(item: GateFinding) -> dict[str, Any]:
    return {
        "id": item.id,
        "status": item.status,
        "period": item.period,
        "message": item.message,
        "missing_template": item.missing_template,
        "detail": list(item.detail),
        "citations": _citations(item.citations),
    }


def _meta_value(ledger: Ledger, period: Period, name: str) -> str | None:
    fact = ledger.metadata_value(period, name)
    return fact.value if fact else None


def _decisions(analysis: Analysis) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger = analysis.ledger
    conversions = []
    for change in ledger.conversions:
        old = ledger.metadata_value(change.period, "money_unit_scale")
        currency = ledger.metadata_value(change.period, "currency")
        conversions.append(
            {
                **change.model_dump(mode="json", exclude={"citation"}),
                "source_unit_scale": old.value if old else None,
                "currency": currency.value if currency else None,
                "rerun_gate_status": analysis.gate.status,
                "citations": _citations(
                    (change.citation, *((old.citation,) if old else ()))
                ),
                "converted_facts": [
                    {
                        "reported_value": canonical_decimal(f.reported_value),
                        "resolved_value": canonical_decimal(f.resolved_value),
                        "currency": f.currency,
                        "source_unit_scale": canonical_decimal(f.unit_scale),
                        "target_unit_scale": canonical_decimal(f.resolved_unit_scale),
                        "factor": canonical_decimal(change.factor),
                        "citations": _citations((f.citation, change.citation)),
                    }
                    for f in ledger.facts
                    if f.conversion == change
                ],
            }
        )
    corrections = []
    for change_meta in ledger.corrections:
        old = ledger.metadata_value(change_meta.period, change_meta.name)
        corrections.append(
            {
                **change_meta.model_dump(mode="json", exclude={"citation", "name"}),
                "field": change_meta.name,
                "result_unit_scale": _meta_value(
                    ledger, change_meta.period, "money_unit_scale"
                ),
                "currency": _meta_value(ledger, change_meta.period, "currency"),
                "rerun_gate_status": analysis.gate.status,
                "citations": _citations(
                    (change_meta.citation, *((old.citation,) if old else ()))
                ),
            }
        )
    return conversions, corrections


def _location(sheet: str, cell: str) -> dict[str, str]:
    return {"sheet": sheet, "cell": cell}


def _sheet(bridge: BridgeResult, index: int) -> str:
    return "Bridge" if index == 0 else bridge.definition.id


def _bridge_data(bridge: BridgeResult, sheet: str) -> dict[str, Any]:
    tolerance = _tolerance(bridge.tolerance)
    assert tolerance is not None
    tolerance["excel"] = _location(sheet, "B2")
    lines = []
    residual = {}
    for n, line in enumerate(bridge.lines, 5):
        result = _amount(line.result)
        result["excel"] = _location(sheet, f"C{n}")
        lines.append(
            {
                "id": line.definition.id,
                "label": line.definition.label,
                "role": line.definition.role,
                "status": line.status,
                "sign": line.definition.sign,
                "reported_inputs": list(line.definition.component_rows),
                "covered_rows": list(line.definition.covered_rows),
                "validation_ids": list(line.validation_ids),
                "result": result,
            }
        )
        if line.definition.role == "residual":
            residual = {
                **_amount(bridge.residual_discrepancy),
                "excel": result["excel"],
            }
    return {
        "id": bridge.definition.id,
        "version": bridge.definition.version,
        "label": bridge.definition.label,
        "status": bridge.status,
        "formula_notes": list(bridge.definition.formula_notes),
        "lines": lines,
        "tolerance": tolerance,
        "residual_check": {
            "status": bridge.residual_status,
            "signed_discrepancy": residual,
            "tolerance": tolerance,
        },
    }


def _schedule_data(analysis: Analysis) -> list[dict[str, Any]]:
    return [
        {
            "id": s.id,
            "label": s.label,
            "category": s.category,
            "bridge_id": s.bridge_id,
            "operands": list(s.operands),
            "opening": {**_amount(s.opening), "excel": _location("Schedules", f"C{n}")},
            "closing": {**_amount(s.closing), "excel": _location("Schedules", f"D{n}")},
            "movement": {
                **_amount(s.movement),
                "excel": _location("Schedules", f"E{n}"),
            },
        }
        for n, s in enumerate(analysis.schedules, 2)
    ]


def _pairing_data(analysis: Analysis) -> dict[str, Any]:
    dates = analysis.linked_materiality
    status = _pairing_status(analysis)
    return {
        "status": status,
        "rule_source": "tests/fixtures/thresholds.yaml#rules/linked_materiality",
        "operator": ">",
        "trigger": "either_date_qualifies",
        "equal": "not_material",
        "nonpositive_total_assets": "indeterminate_for_date",
        "materiality": [
            {
                "period": m.period,
                "status": m.status,
                "linked_assets": {
                    **_amount(m.linked_assets),
                    "excel": _location("Linked_pairing", f"C{n}"),
                },
                "total_assets": {
                    **_amount(m.total_assets),
                    "excel": _location("Linked_pairing", f"E{n}"),
                },
                "threshold": {
                    **_amount(m.threshold),
                    "excel": _location("Linked_pairing", f"I{n}"),
                },
                "parameters": {
                    "absolute_eur": canonical_decimal(m.floor_eur),
                    "fraction_of_total_assets": canonical_decimal(m.fraction),
                    "source": m.source,
                },
            }
            for n, m in enumerate(dates, 5)
        ],
        "movement_ids": [
            s.id for s in analysis.schedules if s.category == "linked_movement"
        ],
        "difference_ids": [
            s.id for s in analysis.schedules if s.category == "movement_difference"
        ],
        "aggregate_difference_ids": [
            s.id
            for s in analysis.schedules
            if s.category == "linked_aggregate_difference"
        ],
    }


def _pairing_status(analysis: Analysis) -> str:
    states = {m.status for m in analysis.linked_materiality}
    if "material" in states:
        return "material"
    if not states:
        return "withheld"
    return "indeterminate" if "indeterminate" in states else "not_material"


TIER_COLUMNS = {
    "available": "C",
    "eligible": "D",
    "denominator": "E",
    "bound": "G",
    "headroom": "H",
    "observed_adjustment": "I",
    "available_headroom": "Q",
    "supply_excess": "R",
    "other_headroom": "S",
    "available_after_tier3": "T",
    "effective_headroom": "U",
    "max_reportable": "W",
}


def _tier_notes(t: TierAssessment) -> str:
    return (
        f"Delegated Regulation (EU) 2015/35 {t.rule.article}. "
        f"{t.rule.label} {t.rule.operator} {t.rule.fraction} × {t.rule.denominator} "
        f"({t.rule.boundary}). Source {t.rule.source_file}, {t.rule.source_location}."
    )


def _tiers_data(analysis: Analysis) -> list[dict[str, Any]]:
    return [
        {
            "id": t.id,
            "period": t.period,
            "status": t.status,
            "reason": t.reason,
            "operator": t.rule.operator,
            "boundary": t.rule.boundary,
            "rule_source": f"mappings/2.8.2/legal_limits.csv#{t.rule.id}",
            "formula_notes": _tier_notes(t),
            "label": t.rule.label,
            "denominator_label": t.rule.denominator,
            "reported_compliance": t.reported_compliance,
            "precision": {
                "value": None
                if t.precision is None
                else canonical_decimal(t.precision),
                "unit": _unit(
                    t.amounts["eligible"].currency, t.amounts["eligible"].unit_scale
                ),
                "citations": _citations(
                    tuple(
                        c
                        for k in ("available", "eligible", "denominator")
                        for c in t.amounts[k].citations
                    )
                ),
                "excel": _location("Tier_limits", f"J{n}"),
            },
            **{
                k: {
                    **_amount(v),
                    "excel": _location("Tier_limits", f"{TIER_COLUMNS[k]}{n}"),
                }
                for k, v in t.amounts.items()
            },
            "effect_on_eligible": {
                **_amount(t.effect),
                "excel": _location("Tier_limits", f"L{n}"),
            },
        }
        for n, t in enumerate(analysis.tier_limits, 5)
    ]


def _tier_changes_data(analysis: Analysis) -> list[dict[str, Any]]:
    return [
        {
            "id": t.id,
            "opening_status": t.opening_status,
            "closing_status": t.closing_status,
            "status_changed": t.opening_status != t.closing_status,
            "direction": t.direction,
            "observed_adjustment_change": {
                **_amount(t.observed_adjustment_change),
                "excel": _location("Tier_limits", f"E{n}"),
            },
            "effect_on_eligible_change": {
                **_amount(t.effect),
                "excel": _location("Tier_limits", f"F{n}"),
            },
        }
        for n, t in enumerate(analysis.tier_changes, 14)
    ]


def summary_data(
    analysis: Analysis, check_rows: dict[str, int] | None = None
) -> dict[str, Any]:
    ledger = analysis.ledger
    findings = [_finding(f) for f in analysis.gate.findings]
    conversions, corrections = _decisions(analysis)
    metadata = [
        {
            "period": m.period,
            "name": m.name,
            "status": "value",
            "value": m.value,
            "reported_value": m.reported_value
            if m.reported_value is not None
            else m.value,
            "citations": _citations([m.citation]),
            "corroborating_citations": _citations(m.corroboration),
            "correction": (
                None
                if m.correction is None
                else {
                    **m.correction.model_dump(mode="json", exclude={"citation"}),
                    "citations": _citations([m.correction.citation]),
                }
            ),
        }
        for m in ledger.metadata
    ]
    comparisons: list[dict[str, Any]] = [
        {
            "id": c.id,
            "label": c.label,
            "status": c.status,
            "period": c.period,
            "message": c.message,
            "missing_template": c.discrepancy.missing_template,
            "withholds": list(c.withholds),
            "left": _amount(c.left),
            "right": _amount(c.right),
            "signed_discrepancy": _amount(c.discrepancy),
            "tolerance": _tolerance(c.tolerance),
        }
        for c in analysis.comparisons
    ]
    for c in comparisons:
        if check_rows and c["id"] in check_rows:
            n = check_rows[c["id"]]
            for field, col in (
                ("left", "D"),
                ("right", "F"),
                ("signed_discrepancy", "G"),
                ("tolerance", "H"),
            ):
                if c[field] is not None:
                    c[field]["excel"] = _location("Summary", f"{col}{n}")
    affected = [
        {
            "dependency": name,
            "period": c.period,
            "check": c.id,
            "status": "withheld" if c.status == "fail" else c.status,
            "missing_template": c.discrepancy.missing_template,
            "reason": c.message,
            "citations": _citations(c.discrepancy.citations),
        }
        for c in analysis.comparisons
        if c.status != "pass"
        for name in c.withholds
    ]
    affected.extend(
        {
            "dependency": name,
            "period": f.period,
            "status": "unavailable",
            "missing_template": f.missing_template,
            "reason": f.message,
            "citations": _citations(f.citations),
        }
        for f in analysis.gate.findings
        if f.missing_template
        for name in f.detail
    )
    affected.extend(
        {
            "dependency": "solvency_ratio",
            "period": v.period,
            "check": v.id,
            "status": "withheld",
            "reason": "Validation failure: " + v.message,
            "citations": _citations(v.citations),
        }
        for v in analysis.ratio_validations
        if v.status == "fail"
    )
    return {
        "schema_version": "0.1",
        "inputs": [i.model_dump(mode="json") for i in ledger.inputs],
        "supplied_reversed": ledger.supplied_reversed,
        "metadata": metadata,
        "gate": {
            "status": analysis.gate.status,
            "checks": findings,
            "stops": [f["id"] for f in findings if f["status"] == "blocked"],
            "conversions": conversions,
            "corrections": corrections,
        },
        "warnings": [f for f in findings if f["status"] == "warning"],
        "present_not_used": [f for f in findings if f["id"].endswith("_unused")],
        "comparisons": comparisons,
        "ratio_validations": [
            {
                "id": v.id,
                "requirement": "R-021/D5",
                "period": v.period,
                "status": v.status,
                "input": {
                    **_amount(v.amount),
                    **(
                        {"excel": _location("Summary", f"D{check_rows[v.id]}")}
                        if check_rows and v.id in check_rows
                        else {}
                    ),
                },
                "condition": "SCR is reported and strictly greater than zero",
                "withholds": ["solvency_ratio"],
                "message": v.message,
                "citations": _citations(v.citations),
            }
            for v in analysis.ratio_validations
        ],
        "affected_detail": affected,
        "withheld": (
            [
                {
                    "id": "all_cross_period_movements",
                    "status": "withheld",
                    "reason": "Comparability gate blocked.",
                    "dependency": "R-005/unit_scale_mismatch"
                    if any(
                        f.id == "unit_scale_mismatch" for f in analysis.gate.findings
                    )
                    else "comparability_gate",
                    "blocking_checks": [
                        f.id for f in analysis.gate.findings if f.status == "blocked"
                    ],
                }
            ]
            if analysis.gate.status == "blocked"
            else []
        ),
        "bridges": [
            _bridge_data(b, _sheet(b, i)) for i, b in enumerate(analysis.bridges)
        ],
        "schedules": _schedule_data(analysis),
        "linked_pairing": _pairing_data(analysis),
        "tier_limits": _tiers_data(analysis),
        "tier_changes": _tier_changes_data(analysis),
        "unsupported_splits": [
            {
                "id": s.id,
                "status": "unavailable",
                "period": s.period,
                "missing_template": s.template,
                "reason": s.reason,
                "citations": _citations(s.citations),
            }
            for s in analysis.unsupported_splits
        ],
        "unimplemented": list(analysis.unimplemented),
    }


def write_json(
    analysis: Analysis, path: Path, check_rows: dict[str, int] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            summary_data(analysis, check_rows),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _excel_formula(expr: Expr, rows: RawRows) -> str:
    if isinstance(expr, FactExpr):
        ref = expr.ref
        key = (
            ref.period,
            ref.table,
            ref.row,
            ref.column,
            tuple(sorted(ref.dimensions.items())),
            ref.coordinate_context,
        )
        row = rows.get(key)
        if row is None:
            return _literal(
                f"Unavailable: {ref.period} {ref.table} {ref.row}/{ref.column}"
            )
        return f"'Raw_{ref.period}'!$S${row}"
    if isinstance(expr, MissingExpr):
        return _literal(f"Unavailable: {expr.period} {expr.template}")
    if isinstance(expr, ScaleExpr):
        return f"({expr.factor}*{_excel_formula(expr.operand, rows)})"
    if isinstance(expr, PercentExpr):
        return f"(100*{_excel_formula(expr.operand, rows)})"
    if isinstance(expr, NegateExpr):
        return f"(-{_excel_formula(expr.operand, rows)})"
    left = _excel_formula(expr.left, rows)
    right = _excel_formula(expr.right, rows)
    if isinstance(expr, AddExpr):
        return f"({left}+{right})"
    if isinstance(expr, SubtractExpr):
        return f"({left}-{right})"
    if isinstance(expr, DivideExpr):
        return (
            f"IF(AND(ISNUMBER({left}),ISNUMBER({right})),IF(({right})>0,"
            f'({left})/({right}),"Validation failure: SCR must be positive"),'
            '"Unavailable: ratio operand missing")'
        )
    raise TypeError(f"Unsupported expression {type(expr).__name__}")


def _signed_terms(
    expr: Expr, rows: RawRows, weight: int = 1
) -> Iterator[tuple[str, int]]:
    """Distribute the ratio definition into signed quotients of raw facts."""
    if isinstance(expr, PercentExpr):
        yield from _signed_terms(expr.operand, rows, 100 * weight)
    elif isinstance(expr, (AddExpr, SubtractExpr)):
        yield from _signed_terms(expr.left, rows, weight)
        yield from _signed_terms(
            expr.right, rows, -weight if isinstance(expr, SubtractExpr) else weight
        )
    elif isinstance(expr, NegateExpr):
        yield from _signed_terms(expr.operand, rows, -weight)
    elif isinstance(expr, DivideExpr):
        divisor = _excel_formula(expr.right, rows)
        for numerator, coefficient in _signed_terms(expr.left, rows, weight):
            yield f"({numerator}/{divisor})", coefficient
    else:
        yield _excel_formula(expr, rows), weight


def _ratio_residual(expr: Expr, rows: RawRows) -> str:
    # Group identical quotients before combining unlike floating point numbers.
    # Each coefficient comes from the opening, closing and movement expressions.
    # An incorrect coefficient or missing term will leave a visible residual.
    terms: dict[str, list[int]] = defaultdict(list)
    for term, weight in _signed_terms(expr, rows):
        terms[term].append(weight)
    return (
        "("
        + "+".join(
            f"({term}*({' + '.join(str(w) for w in weights)}))"
            for term, weights in terms.items()
        )
        + ")"
    )


def _literal(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _cached(v: EvalValue) -> int | float | str:
    if v.status == "value" and v.value is not None:
        return (
            int(v.value) if v.value == v.value.to_integral_value() else float(v.value)
        )
    reason = v.reason or v.missing_template or "required evidence"
    return f"{v.status.capitalize()}: {reason}"


def _write_raw(
    book: Any, period: Period, ledger: Ledger, rows: RawRows, fmt: Any
) -> None:
    sheet = book.add_worksheet(f"Raw_{period}")
    headers = (
        "period",
        "template",
        "table",
        "row",
        "column",
        "context_id",
        "dimensions",
        "coordinate_context",
        "source_file",
        "source_sha256",
        "source_sheet",
        "source_cell",
        "reported_value",
        "currency",
        "source_unit_scale",
        "source_precision",
        "conversion_factor",
        "result_unit_scale",
        "resolved_value",
        "resolved_precision",
        "conversion_status",
        "conversion_reason",
        "conversion_reviewer",
        "conversion_evidence",
        "conversion_citation",
        "fact_citation",
    )
    sheet.write_row(0, 0, headers, fmt)
    facts = sorted(
        (f for f in ledger.facts if f.period == period),
        key=lambda f: (
            f.table,
            f.row,
            f.column,
            sorted(f.dimensions.items()),
            f.coordinate_context or "",
        ),
    )
    for n, f in enumerate(facts, 2):
        rows[
            period,
            f.table,
            f.row,
            f.column,
            tuple(sorted(f.dimensions.items())),
            f.coordinate_context,
        ] = n
        conv = f.conversion
        prec = f.reported_precision
        sheet.write_row(
            n - 1,
            0,
            (
                period,
                f.template,
                f.table,
                f.row,
                f.column,
                f.context_id,
                json.dumps(f.dimensions, sort_keys=True),
                f.coordinate_context or "",
                f.citation.file_id,
                f.citation.sha256,
                f.citation.sheet,
                f.citation.cell,
                float(f.reported_value),
                f.currency,
                float(f.unit_scale),
                float(prec) if prec is not None else "unknown",
                float(conv.factor) if conv else 1,
                float(f.resolved_unit_scale),
                None,
                None,
                "confirmed" if conv else "as reported",
                conv.reason if conv else "",
                conv.reviewer if conv else "",
                conv.evidence if conv else "",
                _source_text((conv.citation,)) if conv else "",
                _source_text((f.citation,)),
            ),
        )
        # A scale stop leaves the displayed raw amount in its original unit.
        sheet.write_formula(n - 1, 18, f"=M{n}*Q{n}", None, float(f.resolved_value))
        if f.resolved_precision is not None:
            sheet.write_formula(
                n - 1, 19, f"=P{n}*O{n}/R{n}", None, float(f.resolved_precision)
            )
        else:
            sheet.write_string(n - 1, 19, "unknown")
    end = len(facts) + 1
    for decl in ledger.declarations:
        c = decl.citation
        if c.period == period:
            sheet.write_row(
                end,
                0,
                (
                    period,
                    c.template,
                    c.table,
                    c.row,
                    c.column,
                    c.context_id,
                    json.dumps(c.dimensions, sort_keys=True),
                    c.coordinate_context,
                    c.file_id,
                    c.sha256,
                    c.sheet,
                    c.cell,
                    decl.value,
                ),
            )
            end += 1
    sheet.freeze_panes(1, 2)
    sheet.autofilter(0, 0, end - 1, len(headers) - 1)
    sheet.set_column(0, 25, 19)
    sheet.set_column(6, 6, 42)
    sheet.set_column(21, 25, 45)


def _write_ratio_validations(
    sheet: Any, start: int, analysis: Analysis, rows: RawRows, fmt: Any
) -> tuple[int, dict[str, int]]:
    if not analysis.ratio_validations:
        return start, {}
    sheet.write(start, 0, "Solvency-ratio input validation (R-021/D5)")
    sheet.write_row(
        start + 1,
        0,
        (
            "validation_id",
            "status",
            "period",
            "reported SCR",
            "condition",
            "message",
            "evidence",
        ),
        fmt,
    )
    checked_rows = {}
    index = start + 2
    for validation in analysis.ratio_validations:
        n = index + 1
        sheet.write(index, 0, validation.id)
        sheet.write_formula(
            index,
            1,
            f'=IF(ISNUMBER(D{n}),IF(D{n}>0,"pass","fail"),"fail")',
            None,
            validation.status,
        )
        sheet.write(index, 2, validation.period)
        cached_input = _cached(validation.amount)
        input_formula = (
            _excel_formula(validation.expression, rows)
            if validation.amount.status == "value"
            else _literal(str(cached_input))
        )
        sheet.write_formula(
            index,
            3,
            "=" + input_formula,
            None,
            cached_input,
        )
        sheet.write(index, 4, "Reported SCR > 0")
        # This message stays accurate when a reviewer edits either raw denominator.
        rule = validation.message
        sheet.write_formula(
            index,
            5,
            f'=IF(B{n}="pass","Validation passed",{_literal(rule)})',
            None,
            "Validation passed" if validation.status == "pass" else rule,
        )
        sheet.write(index, 6, _source_text(validation.citations))
        checked_rows[validation.id] = n
        index += 1
    return index + 1, checked_rows


def _write_checks(
    sheet: Any, start: int, analysis: Analysis, rows: RawRows, fmt: Any
) -> tuple[int, dict[str, int]]:
    sheet.write(start, 0, "Within-period reconciliation")
    sheet.write_row(
        start + 1,
        0,
        (
            "comparison_id",
            "status",
            "left status",
            "left",
            "right status",
            "right",
            "signed discrepancy",
            "tolerance",
            "policy",
            "message",
            "dependent detail",
            "left evidence",
            "right evidence",
            "precision evidence",
        ),
        fmt,
    )
    checked_rows = {}
    index = start + 2
    for c in analysis.comparisons:
        n = index + 1
        sheet.write(index, 0, c.id)
        for v, expr, col in ((c.left, c.left_expr, 2), (c.right, c.right_expr, 4)):
            cached = _cached(v)
            formula = (
                _excel_formula(expr, rows)
                if expr is not None and v.status == "value"
                else _literal(str(cached))
            )
            value_cell = f"{'D' if col == 2 else 'F'}{n}"
            sheet.write_formula(index, col + 1, "=" + formula, None, cached)
            unknown_status = v.status if v.status != "value" else "indeterminate"
            sheet.write_formula(
                index,
                col,
                f'=IF(ISNUMBER({value_cell}),"value",{_literal(unknown_status)})',
                None,
                v.status,
            )
        tolerance = c.tolerance
        if tolerance:
            sheet.write_number(index, 7, float(tolerance.value))
        else:
            sheet.write_string(index, 7, "Indeterminate: precision unavailable")
        cached_diff = _cached(c.discrepancy)
        unavailable = (
            str(cached_diff)
            if isinstance(cached_diff, str)
            else "Indeterminate: operand unavailable"
        )
        discrepancy = _literal(unavailable)
        if c.discrepancy.status == "value":
            discrepancy = (
                f"IF(AND(ISNUMBER(D{n}),ISNUMBER(F{n})),D{n}-F{n},{discrepancy})"
            )
        sheet.write_formula(index, 6, "=" + discrepancy, None, cached_diff)
        status = _check_status_formula(c, n)
        sheet.write_formula(index, 1, "=" + status, None, c.status)
        sheet.write_row(
            index,
            8,
            (
                tolerance.policy if tolerance else "Precision unavailable",
                c.message,
                ", ".join(c.withholds),
                _source_text(c.left.citations),
                _source_text(c.right.citations),
                _source_text(tolerance.citations) if tolerance else "",
            ),
        )
        checked_rows[c.id] = n
        index += 1
    return index, checked_rows


def _check_status_formula(c: Comparison, n: int) -> str:
    if c.status not in ("pass", "fail"):
        return _literal(c.status)
    condition = f"ABS(G{n})<=H{n}"
    # Comparing the unrounded quotient to the two inclusive decimal bounds avoids
    # subtractive cancellation when the reported discrepancy is exactly one unit.
    if (
        c.tolerance is not None
        and c.tolerance.currency == "ratio"
        and c.left.value is not None
    ):
        digits = max(
            0,
            -int(c.left.value.as_tuple().exponent),
            -int(c.tolerance.value.as_tuple().exponent),
        )
        condition = (
            f"AND(F{n}>=ROUND(D{n}-H{n},{digits}),F{n}<=ROUND(D{n}+H{n},{digits}))"
        )
    return f'IF(ISNUMBER(G{n}),IF({condition},"pass","fail"),"indeterminate")'


def _checks_pass(ids: tuple[str, ...], check_rows: dict[str, int]) -> str:
    terms = [f"'Summary'!$B${check_rows[i]}=\"pass\"" for i in ids]
    return f"AND({','.join(terms)})" if terms else "TRUE"


def _dependency_message(ids: tuple[str, ...], check_rows: dict[str, int]) -> str:
    failed = [
        f'IF(Summary!$B${check_rows[i]}="pass","",{_literal(", " + i)})' for i in ids
    ]
    return '"Reconciliation failure in "&MID(' + "&".join(failed) + ",3,32767)"


def _validation_message(ids: tuple[str, ...], check_rows: dict[str, int]) -> str:
    failed = [
        f'IF(Summary!$B${check_rows[i]}="pass","",'
        f"{_literal('; ' + i + ': ')}&Summary!$F${check_rows[i]})"
        for i in ids
    ]
    return '"Validation failure: "&MID(' + "&".join(failed) + ",3,32767)"


def _write_bridge(
    book: Any,
    bridge: BridgeResult,
    name: str,
    rows: RawRows,
    check_rows: dict[str, int],
    fmt: Any,
) -> int:
    sheet = book.add_worksheet(name)
    sheet.write_row(0, 0, (bridge.definition.label,))
    sheet.write_row(
        1,
        0,
        (
            "Bridge tolerance",
            float(bridge.tolerance.value),
            bridge.tolerance.currency,
            bridge.tolerance.policy,
            _source_text(bridge.tolerance.citations),
        ),
    )
    sheet.write_row(
        3,
        0,
        (
            "line_id",
            "line",
            "result",
            "status",
            "sign",
            "unit",
            "citations",
            "tolerance",
            "reason",
        ),
        fmt,
    )
    residual_row = 0
    number_format = None
    if bridge.definition.unit == "pp":
        sheet.write(2, 0, "Exact percentage-point decomposition (D5)")
        sheet.write(
            2,
            1,
            "Own funds at opening SCR, SCR effect on opening funds, and interaction.",
        )
        number_format = book.add_format({"num_format": "0.000000"})
    for n, line in enumerate(bridge.lines, 5):
        v = line.result
        spec = line.definition
        sheet.write_row(n - 1, 0, (spec.id, spec.label))
        if spec.component_rows:
            sheet.write(3, 9, "Reported inputs", fmt)
            sheet.write(n - 1, 9, "\n".join(spec.component_rows))
            sheet.set_column(9, 9, 45)
        if spec.covered_rows:
            sheet.write(3, 10, "Covered rows (including reported subtotals)", fmt)
            sheet.write(n - 1, 10, ", ".join(spec.covered_rows))
            sheet.set_column(10, 10, 60)
        expression = (
            _ratio_residual(spec.expression, rows)
            if spec.role == "residual" and bridge.definition.unit == "pp"
            else _excel_formula(spec.expression, rows)
        )
        valid = _checks_pass(line.validation_ids, check_rows)
        available = _checks_pass(line.check_ids + line.validation_ids, check_rows)
        if spec.role == "residual":
            residual_row = n
        # Check failure can be repaired by editing a raw figure. The formula
        # therefore tests the dependency status on each workbook recalculation.
        if v.status in ("value", "withheld"):
            success = (
                f'IF(ABS({expression})<=$B$2,"pass","fail")'
                if spec.role == "residual"
                else '"value"'
            )
            status = f'IF({available},{success},"withheld")'
        else:
            status = _literal(line.status)
        stored_status = (
            bridge.residual_status if spec.role == "residual" else line.status
        )
        sheet.write_formula(n - 1, 3, "=" + status, None, stored_status)
        cached = _cached(v)
        reason = v.reason or "Required evidence unavailable"
        if (line.check_ids or line.validation_ids) and v.status in (
            "value",
            "withheld",
        ):
            # The actual failed IDs change when a reviewer edits a raw value.
            issue = (
                _dependency_message(line.check_ids, check_rows)
                if line.check_ids
                else _literal("Required checks passed")
            )
            if line.validation_ids:
                validation_issue = _validation_message(line.validation_ids, check_rows)
                issue = f"IF({valid},{issue},{validation_issue})"
            summary = f'IF({available},"Passed",{issue})'
            sheet.write_formula(n - 1, 8, "=" + summary, None, v.reason or "Passed")
        else:
            sheet.write(n - 1, 8, reason if v.status != "value" else "Reported")
        value_formula = (
            f'=IF(OR(D{n}="value",D{n}="pass",D{n}="fail"),{expression},'
            f'IF(D{n}="withheld","Withheld: "&I{n},'
            f'IF(D{n}="unavailable","Unavailable: "&I{n},"Indeterminate: "&I{n})))'
        )
        sheet.write_formula(n - 1, 2, value_formula, number_format, cached)
        sheet.write_row(
            n - 1,
            4,
            (
                spec.sign,
                f"{bridge.tolerance.currency} × {bridge.tolerance.unit_scale}",
                _source_text(v.citations),
            ),
        )
        sheet.write_formula(n - 1, 7, "=$B$2", None, float(bridge.tolerance.value))
    if bridge.definition.formula_notes:
        start = len(bridge.lines) + 6
        sheet.write(start, 0, "Formula notes", fmt)
        note_format = book.add_format({"text_wrap": True, "valign": "top"})
        for index, note in enumerate(bridge.definition.formula_notes, start + 1):
            sheet.merge_range(index, 0, index, 8, note, note_format)
            sheet.set_row(index, 32)
    sheet.freeze_panes(4, 2)
    sheet.set_column(0, 1, 40)
    sheet.set_column(2, 3, 22)
    sheet.set_column(4, 8, 46)
    return residual_row


def _write_schedules(
    book: Any, analysis: Analysis, rows: RawRows, check_rows: dict[str, int], fmt: Any
) -> None:
    if not analysis.schedules:
        return
    sheet = book.add_worksheet("Schedules")
    sheet.write_row(
        0,
        0,
        (
            "id",
            "reported measure",
            "opening",
            "closing",
            "movement",
            "opening evidence",
            "closing evidence",
            "movement evidence",
        ),
        fmt,
    )
    for n, s in enumerate(analysis.schedules, 2):
        sheet.write_row(n - 1, 0, (s.id, s.label))
        for col, (v, expr) in enumerate(
            (
                (s.opening, s.opening_expr),
                (s.closing, s.closing_expr),
                (s.movement, s.movement_expr),
            ),
            2,
        ):
            cached = _cached(v)
            formula = _literal(str(cached))
            if v.status == "value" or (v.status == "withheld" and s.check_ids):
                formula = _excel_formula(expr, rows)
                if col == 4 and s.check_ids:
                    reason = _dependency_message(s.check_ids, check_rows)
                    passes = _checks_pass(s.check_ids, check_rows)
                    formula = f'IF({passes},{formula},"Withheld: "&{reason})'
            sheet.write_formula(n - 1, col, "=" + formula, None, cached)
            sheet.write(n - 1, col + 3, _source_text(v.citations))
    sheet.freeze_panes(1, 2)
    sheet.set_column(0, 1, 47)
    sheet.set_column(2, 4, 24)
    sheet.set_column(5, 7, 48)


def _write_tp_overviews(book: Any, analysis: Analysis, fmt: Any) -> None:
    """Place levels, subtotal and LTG evidence alongside each TP bridge."""
    for bridge_id in ("life_net_tp", "health_slt_net_tp"):
        sheet = book.get_worksheet_by_name(bridge_id)
        if sheet is None:
            continue
        sheet.write_row(3, 10, ("TP components", "opening", "closing", "movement"), fmt)
        sheet.write(1, 10, "Net BEL = gross BEL − BEL recoverables")
        sheet.write(
            2, 10, "Net TP = whole TP − whole recoverables + net BEL + RM + signed TMTP"
        )
        position = 4
        for n, schedule in enumerate(analysis.schedules, 2):
            if schedule.bridge_id != bridge_id:
                continue
            sheet.write(position, 10, schedule.label)
            for col, (field, value) in enumerate(
                (
                    ("C", schedule.opening),
                    ("D", schedule.closing),
                    ("E", schedule.movement),
                ),
                11,
            ):
                sheet.write_formula(
                    position, col, f"=Schedules!{field}{n}", None, _cached(value)
                )
            position += 1
        position += 2
        sheet.write(position, 10, "S.22.01 undertaking TP scenarios", fmt)
        sheet.write(
            position + 1, 10, "Reported step-by-step impacts for the whole undertaking"
        )
        sheet.write_row(
            position + 2, 10, ("scenario", "opening", "closing", "movement"), fmt
        )
        position += 3
        for n, schedule in enumerate(analysis.schedules, 2):
            if schedule.category != "ltg_scenario":
                continue
            sheet.write(position, 10, schedule.label)
            for col, (field, value) in enumerate(
                (
                    ("C", schedule.opening),
                    ("D", schedule.closing),
                    ("E", schedule.movement),
                ),
                11,
            ):
                sheet.write_formula(
                    position, col, f"=Schedules!{field}{n}", None, _cached(value)
                )
            position += 1
        sheet.set_column(10, 10, 65)
        sheet.set_column(11, 13, 22)


def _write_pairing(book: Any, analysis: Analysis, rows: RawRows, fmt: Any) -> None:
    if not analysis.linked_materiality:
        return
    sheet = book.add_worksheet("Linked_pairing")
    sheet.write(0, 0, "Index-linked and unit-linked insurance — movement comparisons")
    sheet.write(1, 0, "Materiality at either date")
    sheet.write_formula(
        1,
        1,
        '=IF(OR(B5="material",B6="material"),"material",'
        'IF(OR(B5="indeterminate",B6="indeterminate"),"indeterminate","not_material"))',
        None,
        _pairing_status(analysis),
    )
    sheet.write_row(
        3,
        0,
        (
            "period",
            "materiality",
            "linked assets",
            "unit scale",
            "total assets",
            "unit scale",
            "floor EUR",
            "fraction of total assets",
            "threshold EUR",
            "rule source",
            "linked evidence",
            "total evidence",
        ),
        fmt,
    )
    for n, m in enumerate(analysis.linked_materiality, 5):
        sheet.write(n - 1, 0, m.period)
        sheet.write(n - 1, 6, float(m.floor_eur))
        sheet.write(n - 1, 7, float(m.fraction))
        sheet.write(n - 1, 9, m.source)
        for col, value, expr in (
            (2, m.linked_assets, m.linked_expr),
            (4, m.total_assets, m.total_expr),
        ):
            formula = (
                _excel_formula(expr, rows)
                if value.status == "value"
                else _literal(str(_cached(value)))
            )
            sheet.write_formula(n - 1, col, "=" + formula, None, _cached(value))
            sheet.write(
                n - 1,
                col + 1,
                float(value.unit_scale)
                if value.unit_scale is not None
                else "Unavailable",
            )
            sheet.write(n - 1, 10 + (col - 2) // 2, _source_text(value.citations))
        eligible = (
            m.linked_assets.status == m.total_assets.status == "value"
            and m.linked_assets.currency == m.total_assets.currency == "EUR"
        )
        status = _literal("indeterminate")
        threshold = _literal(str(_cached(m.threshold)))
        if eligible:
            threshold = (
                f"IF(E{n}>0,MAX(G{n},E{n}*F{n}*H{n}),"
                '"Indeterminate: total assets are nonpositive")'
            )
            status = (
                f'IF(E{n}<=0,"indeterminate",'
                f'IF(ABS(C{n}*D{n})>I{n},"material","not_material"))'
            )
        sheet.write_formula(n - 1, 8, "=" + threshold, None, _cached(m.threshold))
        sheet.write_formula(n - 1, 1, "=" + status, None, m.status)
    sheet.write_row(
        8, 0, ("id", "reported movement or difference", "value", "evidence"), fmt
    )
    position = 9
    for n, s in enumerate(analysis.schedules, 2):
        if not s.category.startswith("linked_") and s.category != "movement_difference":
            continue
        sheet.write_row(position, 0, (s.id, s.label))
        sheet.write_formula(position, 2, f"=Schedules!E{n}", None, _cached(s.movement))
        sheet.write(position, 3, _source_text(s.movement.citations))
        position += 1
    sheet.freeze_panes(9, 2)
    sheet.set_column(0, 0, 33)
    sheet.set_column(1, 1, 65)
    sheet.set_column(2, 8, 22)
    sheet.set_column(9, 11, 50)


def _tier_status_formula(t: TierAssessment, row: int, tier3_row: int) -> str:
    if t.precision is None:
        return '"indeterminate"'
    refs = {k: f"{col}{row}" for k, col in TIER_COLUMNS.items()}
    refs.update(precision=f"J{row}", tier3_status=f"B{tier3_row}")
    formula = '"indeterminate"'
    for decision in reversed(t.decisions):
        conditions = []
        for left, op, right in decision.conditions:
            if left in t.amounts and t.amounts[left].value is None:
                return '"indeterminate"'
            if right in t.amounts and t.amounts[right].value is None:
                return '"indeterminate"'
            rhs = refs.get(right, "0" if right == "0" else _literal(right))
            conditions.append(f"({refs[left]}{'=' if op == '==' else op}{rhs})")
        formula = f'IF(AND({",".join(conditions)}),"{decision.status}",{formula})'
    return formula


def _write_tiers(book: Any, analysis: Analysis, rows: RawRows, fmt: Any) -> None:
    if not analysis.tier_limits:
        return
    sheet = book.add_worksheet("Tier_limits")
    sheet.write(0, 0, "Article 82 — reported eligibility and limit assessments")
    sheet.write(
        1,
        0,
        "Observed eligibility adjustments and attributed limit effects.",
    )
    sheet.write(
        2,
        0,
        "Legal bounds apply before rounding. Precision and competing limits "
        "govern attribution.",
    )
    sheet.write_row(
        3,
        0,
        (
            "id",
            "conclusion",
            "available",
            "eligible",
            "denominator",
            "legal fraction",
            "legal bound",
            "bound less eligible",
            "eligible less available",
            "source precision",
            "reported compliance",
            "effect on eligible",
            "reason",
            "operator",
            "legal source",
            "financial evidence",
            "bound less available",
            "supply above bound",
            "combined-limit headroom",
            "available after Tier 3 restriction",
            "headroom after Tier 3 restriction",
        ),
        fmt,
    )
    indices = {t.id: n for n, t in enumerate(analysis.tier_limits, 5)}
    # Source monetary facts are whole reporting units. These places retain all
    # digits introduced by the mapped legal fractions, including live raw edits.
    legal_places = max(
        len(format(t.rule.fraction, "f").partition(".")[2])
        for t in analysis.tier_limits
    )
    for n, t in enumerate(analysis.tier_limits, 5):
        sheet.write(n - 1, 0, t.id)
        for key, value in t.amounts.items():
            formula = _literal(str(_cached(value)))
            if value.status == "value":
                if key == "max_reportable":
                    formula = (
                        f"(-INT(-G{n}/J{n})-1)*J{n}"
                        if t.rule.operator == "<"
                        else f"INT(G{n}/J{n})*J{n}"
                    )
                else:
                    formula = _excel_formula(t.expressions[key], rows)
                formula = f"ROUND({formula},{legal_places})"
            sheet.write_formula(
                f"{TIER_COLUMNS[key]}{n}", "=" + formula, None, _cached(value)
            )
        sheet.write(n - 1, 5, float(t.rule.fraction))
        precision_refs = []
        for key in ("available", "eligible", "denominator"):
            for c in t.amounts[key].citations:
                raw_key = (
                    c.period,
                    c.table,
                    c.row,
                    c.column,
                    tuple(sorted(c.dimensions.items())),
                    c.coordinate_context,
                )
                if raw_key in rows:
                    precision_refs.append(f"'Raw_{c.period}'!T{rows[raw_key]}")
        precision_formula = (
            "MAX(" + ",".join(dict.fromkeys(precision_refs)) + ")"
            if t.precision is not None
            else '"Indeterminate: missing precision"'
        )
        sheet.write_formula(
            n - 1,
            9,
            "=" + precision_formula,
            None,
            float(t.precision)
            if t.precision is not None
            else "Indeterminate: missing precision",
        )
        tier3_row = indices[f"{t.period}_article82_1_b"]
        sheet.write_formula(
            n - 1, 1, "=" + _tier_status_formula(t, n, tier3_row), None, t.status
        )
        compliance = (
            f"IF(AND(ISNUMBER(D{n}),ISNUMBER(G{n})),"
            f'IF(D{n}{t.rule.operator}G{n},"pass","fail"),"indeterminate")'
        )
        sheet.write_formula(n - 1, 10, "=" + compliance, None, t.reported_compliance)
        effect = (
            f'IF(B{n}="binding",I{n},IF(B{n}="not_binding",'
            f'D{n}-D{n},"Indeterminate: "&M{n}))'
        )
        sheet.write_formula(n - 1, 11, "=" + effect, None, _cached(t.effect))
        # The reason follows a live change of conclusion, including a repaired raw fact.
        unknown = t.reason if not t.decisions else REASONS["indeterminate"]
        reason = (
            f'IF(B{n}="binding",{_literal(REASONS["binding"])},'
            f'IF(B{n}="not_binding",{_literal(REASONS["not_binding"])},'
            f"{_literal(unknown)}))"
        )
        sheet.write_formula(n - 1, 12, "=" + reason, None, t.reason)
        sheet.write(n - 1, 13, t.rule.operator)
        sheet.write(n - 1, 14, _tier_notes(t))
        sheet.write(n - 1, 21, t.rule.label)
        sheet.write(n - 1, 15, _source_text(t.effect.citations))
    sheet.write_row(
        12,
        0,
        (
            "limit",
            "opening",
            "closing",
            "direction",
            "change in observed adjustment",
            "change in limit effect",
            "evidence",
        ),
        fmt,
    )
    for n, change in enumerate(analysis.tier_changes, 14):
        before = indices[f"opening_{change.id}"]
        after = indices[f"closing_{change.id}"]
        sheet.write(n - 1, 0, change.id)
        sheet.write_formula(n - 1, 1, f"=B{before}", None, change.opening_status)
        sheet.write_formula(n - 1, 2, f"=B{after}", None, change.closing_status)
        direction = (
            f'IF(B{n}=C{n},"unchanged",IF(C{n}="indeterminate","became_indeterminate",'
            f'IF(B{n}="indeterminate","resolved_to_"&C{n},IF(C{n}="binding","newly_binding","released"))))'
        )
        sheet.write_formula(n - 1, 3, "=" + direction, None, change.direction)
        unknown = _literal(
            "Indeterminate: At least one period's limit effect is indeterminate."
        )
        observed = (
            f"IF(AND(ISNUMBER(I{before}),ISNUMBER(I{after})),"
            f"I{after}-I{before},{unknown})"
        )
        sheet.write_formula(
            n - 1, 4, "=" + observed, None, _cached(change.observed_adjustment_change)
        )
        effect = (
            f"IF(AND(ISNUMBER(L{before}),ISNUMBER(L{after})),"
            f"L{after}-L{before},{unknown})"
        )
        sheet.write_formula(n - 1, 5, "=" + effect, None, _cached(change.effect))
        sheet.write(n - 1, 6, _source_text(change.observed_adjustment_change.citations))
    sheet.freeze_panes(4, 2)
    sheet.set_column(0, 1, 32)
    sheet.set_column(2, 11, 23)
    sheet.set_column(12, 15, 65)
    sheet.write(3, 21, "Limit", fmt)
    sheet.write(3, 22, "Largest reportable amount within bound", fmt)
    sheet.set_column(16, 22, 25)


def _dashboard(sheet: Any, analysis: Analysis, fmt: Any) -> int:
    ledger = analysis.ledger
    sheet.write("A1", "Solvency II reconciliation")
    sheet.write_row(1, 0, ("Comparability gate", analysis.gate.status))
    sheet.write_row(
        2,
        0,
        (
            "Supplied in reverse chronological order",
            "yes" if ledger.supplied_reversed else "no",
        ),
    )
    sheet.write_row(
        4, 0, ("id", "status", "period", "finding", "affected detail", "evidence"), fmt
    )
    row = 5
    # Warnings and stops appear first even when many checks passed.
    for f in sorted(analysis.gate.findings, key=lambda f: f.status == "pass"):
        sheet.write_row(
            row,
            0,
            (
                f.id,
                f.status,
                f.period or "pair",
                f.message,
                ", ".join(f.detail),
                _source_text(f.citations),
            ),
        )
        row += 1
    row += 1
    sheet.write(row, 0, "Input files in chronological order")
    sheet.write_row(row + 1, 0, ("period", "file", "SHA-256", "variant"), fmt)
    row += 2
    for file in ledger.inputs:
        sheet.write_row(row, 0, (file.period, file.file_id, file.sha256, file.variant))
        row += 1
    row += 1
    sheet.write(row, 0, "Cited period metadata")
    sheet.write_row(
        row + 1,
        0,
        (
            "period",
            "field",
            "reported",
            "effective",
            "source",
            "corroborating filing facts",
            "correction evidence",
        ),
        fmt,
    )
    row += 2
    for m in ledger.metadata:
        sheet.write_row(
            row,
            0,
            (
                m.period,
                m.name,
                m.reported_value if m.reported_value is not None else m.value,
                m.value,
                _source_text([m.citation]),
                _source_text(m.corroboration),
                _source_text((m.correction.citation,)) if m.correction else "",
            ),
        )
        row += 1
    if ledger.conversions or ledger.corrections:
        row += 1
        sheet.write(row, 0, "Reviewer decisions and gate rerun")
        sheet.write_row(
            row + 1,
            0,
            (
                "period",
                "field",
                "original",
                "effective or factor",
                "result unit",
                "reviewer",
                "stated reason",
                "source evidence",
                "gate after rerun",
                "audit location",
            ),
            fmt,
        )
        row += 2
        for correction in ledger.corrections:
            currency = ledger.metadata_value(correction.period, "currency")
            scale = ledger.metadata_value(correction.period, "money_unit_scale")
            units = (
                f"{currency.value} × {scale.value}"
                if currency and scale
                else "Unavailable"
            )
            sheet.write_row(
                row,
                0,
                (
                    correction.period,
                    correction.name,
                    correction.original_value,
                    correction.corrected_value,
                    units,
                    correction.reviewer,
                    correction.reason,
                    correction.evidence,
                    analysis.gate.status,
                    _source_text((correction.citation,)),
                ),
            )
            row += 1
        for change in ledger.conversions:
            original = ledger.metadata_value(change.period, "money_unit_scale")
            currency = ledger.metadata_value(change.period, "currency")
            units = f"{currency.value if currency else ''} × {change.target_unit_scale}"
            sheet.write_row(
                row,
                0,
                (
                    change.period,
                    "scale conversion",
                    original.value if original else "Unavailable",
                    canonical_decimal(change.factor),
                    units,
                    change.reviewer,
                    change.reason,
                    change.evidence,
                    analysis.gate.status,
                    _source_text((change.citation,)),
                ),
            )
            row += 1
    return row + 1


def write_workbook(analysis: Analysis, path: Path) -> dict[str, int]:
    """Create the executive dashboard first, followed by raw and calculation tabs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with xlsxwriter.Workbook(
        str(path), {"strings_to_formulas": False, "strings_to_urls": False}
    ) as book:
        book.set_calc_mode("auto")
        fmt = book.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        summary = book.add_worksheet("Summary")
        start = _dashboard(summary, analysis, fmt)
        rows: RawRows = {}
        for period in ("opening", "closing"):
            _write_raw(book, period, analysis.ledger, rows, fmt)
        start, validation_rows = _write_ratio_validations(
            summary, start, analysis, rows, fmt
        )
        end, check_rows = _write_checks(summary, start, analysis, rows, fmt)
        check_rows.update(validation_rows)
        if analysis.gate.status != "blocked":
            summary.write_row(
                end + 1,
                0,
                (
                    "Bridge",
                    "residual status",
                    "signed discrepancy",
                    "tolerance",
                    "unit",
                ),
                fmt,
            )
            end += 2
            for index, b in enumerate(analysis.bridges):
                name = _sheet(b, index)
                n = _write_bridge(book, b, name, rows, check_rows, fmt)
                summary.write(end, 0, b.definition.label)
                summary.write_formula(
                    end, 1, f"='{name}'!D{n}", None, b.residual_status
                )
                summary.write_formula(
                    end, 2, f"='{name}'!C{n}", None, _cached(b.residual_discrepancy)
                )
                summary.write_formula(
                    end, 3, f"='{name}'!B2", None, float(b.tolerance.value)
                )
                summary.write(end, 4, b.tolerance.currency)
                end += 1
            _write_schedules(book, analysis, rows, check_rows, fmt)
            _write_tp_overviews(book, analysis, fmt)
            _write_pairing(book, analysis, rows, fmt)
            _write_tiers(book, analysis, rows, fmt)
            for split in analysis.unsupported_splits:
                summary.write_row(
                    end,
                    0,
                    (
                        split.id,
                        "Unavailable",
                        split.period,
                        split.reason,
                        _source_text(split.citations),
                    ),
                )
                end += 1
        else:
            summary.write(end + 1, 0, "Movements withheld")
            summary.write(end + 1, 1, "Resolve the cited stop and rerun the gate.")
        summary.freeze_panes(2, 0)
        summary.set_column(0, 0, 35)
        summary.set_column(1, 2, 23)
        summary.set_column(3, 3, 65)
        summary.set_column(4, 7, 27)
        summary.set_column(8, 13, 60)
    return check_rows


def write_outputs(analysis: Analysis, workbook_path: Path, json_path: Path) -> None:
    checks = write_workbook(analysis, workbook_path)
    write_json(analysis, json_path, checks)
