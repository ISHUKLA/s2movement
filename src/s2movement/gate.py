"""The chronological, scope, comparability and presence gates (R-001–R-007)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from s2movement.check_catalog import ROOT, catalog
from s2movement.models import Citation, InputFile, Ledger, LedgerFact, Period

PERIODS: tuple[Period, Period] = ("opening", "closing")
OPTIONAL_DETAILS = {
    "S.12.01": ("life_net_tp", "health_slt_net_tp", "linked_detail"),
    "S.25.01": ("scr_modules",),
    "S.05.01": ("premiums_and_claims",),
    "S.22.01": ("ltg_impacts",),
}
INVENTORY = {
    "S.02.01": "R0030",
    "S.05.01": "R0110",
    "S.12.01": "R0220",
    "S.22.01": "R0370",
    "S.23.01": "R0410",
    "S.25.01": "R0460",
}
type FindingStatus = Literal["pass", "blocked", "warning", "info"]


@dataclass(frozen=True)
class GateFinding:
    id: str
    status: FindingStatus
    message: str
    citations: tuple[Citation, ...] = ()
    period: Period | None = None
    missing_template: str | None = None
    detail: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gate:
    status: Literal["pass", "blocked"]
    findings: tuple[GateFinding, ...]


def metadata(ledger: Ledger, period: Period, name: str) -> str | None:
    item = ledger.metadata_value(period, name)
    return item.value if item is not None else None


def metadata_citations(
    ledger: Ledger, names: tuple[str, ...], periods: tuple[Period, ...] = PERIODS
) -> tuple[Citation, ...]:
    return tuple(
        c
        for f in ledger.metadata
        if f.name in names and f.period in periods
        for c in (
            f.citation,
            *f.corroboration,
            *((f.correction.citation,) if f.correction else ()),
        )
    )


def _pair(ledger: Ledger, field: str) -> str:
    return ", ".join(
        f"{p} {field}={metadata(ledger, p, field) or 'Unavailable'}" for p in PERIODS
    )


def _inventory(ledger: Ledger, inp: InputFile, family: str) -> tuple[Citation, ...]:
    cites = tuple(
        d.citation
        for d in ledger.declarations
        if d.citation.period == inp.period
        and d.citation.table == "S.01.01.01.01"
        and d.citation.row == INVENTORY.get(family)
        and d.citation.column == "C0010"
    )
    if family in inp.presence:
        return (inp.presence[family], *cites)
    return cites or metadata_citations(ledger, ("reference_date",), (inp.period,))


def _impact(ledger: Ledger, period: Period, col: str) -> LedgerFact | None:
    table = (
        "S.22.01.21.01"
        if metadata(ledger, period, "variant") == "public_disclosure"
        else "S.22.01.01.01"
    )
    address = (table, "R0010", col)
    selector = catalog().selectors[address]
    return ledger.find_fact(
        period=period,
        table=table,
        row="R0010",
        column=col,
        dimensions=selector.dimensions,
        coordinate_context=selector.coordinate,
    )


def _ltg_findings(ledger: Ledger) -> list[GateFinding]:
    result = []
    settings = json.loads(
        (ROOT / "tests/fixtures/thresholds.yaml").read_text(encoding="utf-8")
    )
    impact_threshold = settings["rules"]["measure_impact"]["threshold"]
    fraction = Decimal(impact_threshold["fraction_of_abs_opening_with_measures_tp"])
    floor = Decimal(impact_threshold["absolute_eur"])
    opening_tp = _impact(ledger, "opening", "C0010")
    for measure, col in (
        ("va", "C0070"),
        ("ma", "C0090"),
        ("tmtp", "C0030"),
        ("tmir", "C0050"),
    ):
        field = measure + "_applied"
        before, after = (metadata(ledger, p, field) for p in PERIODS)
        if before in {"yes", "no"} and after in {"yes", "no"} and before != after:
            result.append(
                GateFinding(
                    measure + "_status_changed",
                    "warning",
                    f"{measure.upper()} basis changed. {_pair(ledger, field)}.",
                    metadata_citations(ledger, (field,)),
                )
            )
        elif before not in {"yes", "no"} or after not in {"yes", "no"}:
            result.append(
                GateFinding(
                    measure + "_status_unknown",
                    "info",
                    f"Indeterminate {measure.upper()} status change. "
                    f"{_pair(ledger, field)}.",
                    metadata_citations(ledger, (field,)),
                )
            )
        left, right = (_impact(ledger, p, col) for p in PERIODS)
        if not (left and right and opening_tp):
            for inp in ledger.inputs:
                absent = (
                    not left or not opening_tp if inp.period == "opening" else not right
                )
                if absent and "S.22.01" in inp.templates:
                    result.append(
                        GateFinding(
                            f"{inp.period}_{measure}_impact_unavailable",
                            "info",
                            f"{inp.period.title()} {measure.upper()}: Unavailable. "
                            f"Supply S.22.01 R0010/{col} in its scenario context "
                            "and opening with-measures TP.",
                            _inventory(ledger, inp, "S.22.01"),
                            inp.period,
                            "S.22.01",
                            ("ltg_impacts",),
                        )
                    )
            continue
        refs = (
            left.citation,
            right.citation,
            opening_tp.citation,
            *metadata_citations(ledger, ("currency", "money_unit_scale")),
            *(c.citation for c in ledger.conversions),
        )
        if left.currency != settings["scope"]["currency"]:
            result.append(
                GateFinding(
                    measure + "_impact_threshold_unavailable",
                    "info",
                    f"Indeterminate {measure.upper()} impact. The floor is EUR; "
                    f"the filings use {left.currency}.",
                    refs,
                )
            )
            continue
        base = opening_tp.resolved_value * opening_tp.resolved_unit_scale
        delta = (
            right.resolved_value * right.resolved_unit_scale
            - left.resolved_value * left.resolved_unit_scale
        )
        limit = max(floor, abs(base) * fraction)
        if abs(delta) > limit:
            result.append(
                GateFinding(
                    measure + "_tp_impact_material_shift",
                    "warning",
                    f"{measure.upper()} reported TP impact changed by {delta:+f} EUR "
                    f"(threshold {limit:f} EUR, thresholds.yaml#rules/measure_impact).",
                    refs,
                )
            )
    return result


def evaluate_gate(ledger: Ledger) -> Gate:
    findings = [
        GateFinding(i.id, "blocked", i.message, i.citations)
        for i in ledger.input_issues
    ]
    if any(f.id == "consecutive_annual_periods" for f in findings) or any(
        f.id.endswith("_pdf_input") for f in findings
    ):
        return Gate("blocked", tuple(findings))
    if not all(ledger.metadata_value(p, "reference_date") for p in PERIODS):
        return Gate("blocked", tuple(findings))
    findings.append(
        GateFinding(
            "consecutive_annual_periods",
            "pass",
            f"Successive annual dates. {_pair(ledger, 'reference_date')}.",
            metadata_citations(ledger, ("reference_date",)),
        )
    )
    if ledger.supplied_reversed:
        findings.append(
            GateFinding(
                "supplied_reversed",
                "info",
                "Closing was supplied first. Results use chronological order.",
                metadata_citations(ledger, ("reference_date",)),
            )
        )
    for field, required, remedy in (
        ("taxonomy_version", "2.8.2", "Supply a taxonomy 2.8.2 filing"),
        ("perimeter", "solo", "Supply a solo filing for the same undertaking"),
        ("frequency", "annual", "Supply an annual filing"),
        ("scr_method", "standard_formula", "Supply a Standard Formula filing"),
    ):
        for period in PERIODS:
            if metadata(ledger, period, field) != required:
                findings.append(
                    GateFinding(
                        f"{period}_{field}_scope",
                        "blocked",
                        f"{period.title()} is outside the supported scope. "
                        f"{_pair(ledger, field)}. {remedy}.",
                        metadata_citations(ledger, (field,)),
                        period,
                    )
                )
    for field, remedy in (
        ("lei", "Supply filings for one legal entity"),
        ("currency", "Supply filings in the same reported currency"),
    ):
        a, b = (metadata(ledger, p, field) for p in PERIODS)
        if a != b or not a:
            findings.append(
                GateFinding(
                    f"incompatible_{field}",
                    "blocked",
                    f"{_pair(ledger, field)}. {remedy}.",
                    metadata_citations(ledger, (field,)),
                )
            )
    revision = tuple(metadata(ledger, p, "taxonomy_variant") for p in PERIODS)
    if (
        all(v in {"base", "nace_2_1_hotfix"} for v in revision)
        and revision[0] != revision[1]
    ):
        findings.append(
            GateFinding(
                "taxonomy_variant_changed",
                "warning",
                f"2.8.2 revisions differ. {_pair(ledger, 'taxonomy_variant')}.",
                metadata_citations(ledger, ("taxonomy_version", "taxonomy_variant")),
            )
        )
    if any(v not in {"base", "nace_2_1_hotfix"} for v in revision):
        findings.append(
            GateFinding(
                "taxonomy_variant_unverified",
                "info",
                f"Indeterminate revisions. {_pair(ledger, 'taxonomy_variant')}.",
                metadata_citations(ledger, ("taxonomy_variant",)),
            )
        )
    scales = {p: metadata(ledger, p, "money_unit_scale") for p in PERIODS}
    if scales["opening"] != scales["closing"]:
        confirmed = {c.period for c in ledger.conversions}
        if any(Decimal(scales[p] or 0) != 1 and p not in confirmed for p in PERIODS):
            findings.append(
                GateFinding(
                    "unit_scale_mismatch",
                    "blocked",
                    f"{_pair(ledger, 'money_unit_scale')}. Confirm a scale conversion "
                    "or correct the declared units with source evidence.",
                    metadata_citations(ledger, ("money_unit_scale", "currency")),
                )
            )
    for inp in ledger.inputs:
        if metadata(ledger, inp.period, "taxonomy_version") != "2.8.2":
            continue
        if "S.32.01" in inp.templates:
            findings.append(
                GateFinding(
                    f"{inp.period}_group_filing",
                    "blocked",
                    f"{inp.period.title()} {inp.file_id} reports the S.32.01 group "
                    "template. Supply a solo filing.",
                    _inventory(ledger, inp, "S.32.01"),
                    inp.period,
                )
            )
        if "S.25.05" in inp.templates:
            findings.append(
                GateFinding(
                    f"{inp.period}_internal_model_filing",
                    "blocked",
                    f"{inp.period.title()} {inp.file_id} reports Internal Model "
                    "template S.25.05. Supply a Standard Formula filing.",
                    _inventory(ledger, inp, "S.25.05"),
                    inp.period,
                )
            )
        for family in ("S.02.01", "S.23.01", *OPTIONAL_DETAILS):
            if family in inp.templates:
                continue
            detail = OPTIONAL_DETAILS.get(family, ())
            findings.append(
                GateFinding(
                    f"{inp.period}_missing_{family}",
                    "warning" if detail else "blocked",
                    (
                        f"{inp.period.title()} {family} is missing from {inp.file_id}. "
                        + (
                            "Unavailable: " + ", ".join(detail) + "."
                            if detail
                            else f"Supply the required {family} template."
                        )
                    ),
                    _inventory(ledger, inp, family),
                    inp.period,
                    family,
                    detail,
                )
            )
        for family in sorted(set(inp.templates) & {f"S.29.0{i}" for i in range(1, 5)}):
            findings.append(
                GateFinding(
                    f"{inp.period}_{family}_unused",
                    "info",
                    f"{inp.period.title()} {family}: present, not used.",
                    _inventory(ledger, inp, family),
                    inp.period,
                )
            )
        for indicator, member in (
            ("rff_indicator", "s2c_x96"),
            ("map_indicator", "s2c_x53"),
        ):
            if metadata(ledger, inp.period, indicator) != "yes":
                continue
            sources = [c for c in inp.sr_contexts if c.template != "SR.01.01"]
            supported = any(
                c.dimensions.get("s2c_PO") == member
                and (c.dimensions.get("s2c_FN") or c.dimensions.get("s2c_NF"))
                for c in sources
            )
            if not supported:
                findings.append(
                    GateFinding(
                        f"{inp.period}_{indicator}_without_sr",
                        "warning",
                        f"{inp.period.title()} {indicator}=yes. Supply a matching "
                        "SR disclosure with the portfolio type and identifier.",
                        metadata_citations(ledger, (indicator,), (inp.period,))
                        + tuple(sources),
                        inp.period,
                    )
                )
    blocked = any(f.status == "blocked" for f in findings)
    if not blocked:
        findings.extend(_ltg_findings(ledger))
    return Gate("blocked" if blocked else "pass", tuple(findings))
