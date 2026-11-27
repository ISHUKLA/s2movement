"""Independent Step 4 answer key. All monetary operands are exact euros."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from functools import partial
from typing import Any

type Cells = dict[tuple[str, str, str], int | str]
type Source = tuple[str, str, str, str]
type Record = dict[str, Any]
type Number = Decimal | Fraction

BS = "S.02.01.01.01"
TP = "S.12.01.01.01"
OF = "S.23.01.01.01"
RR = "S.23.01.01.02"
MODULE = "S.25.01.01.01"
ADJUST = "S.25.01.01.02"
IMPACT = "S.22.01.01.01"


def canonical(value: Number) -> str:
    if isinstance(value, Fraction):
        return str(value)
    return format(value.normalize(), "f") if value else "0"


@dataclass(frozen=True)
class Amount:
    n: Number
    sources: tuple[Source, ...]

    def combined(self, other: Amount, n: Number) -> Amount:
        return Amount(n, tuple(dict.fromkeys((*self.sources, *other.sources))))

    def __add__(self, other: Amount) -> Amount:
        if isinstance(self.n, Decimal) and isinstance(other.n, Decimal):
            return self.combined(other, self.n + other.n)
        return self.combined(other, Fraction(self.n) + Fraction(other.n))

    def __sub__(self, other: Amount) -> Amount:
        return self + other.times(-1)

    def times(self, factor: int) -> Amount:
        return Amount(self.n * factor, self.sources)

    def quotient(self, other: Amount) -> Amount:
        return self.combined(other, Fraction(self.n) / Fraction(other.n))

    def encoded(self, unit: str = "EUR") -> Record:
        return {
            "value": canonical(self.n),
            "unit": unit,
            "sign": "positive" if self.n > 0 else "negative" if self.n < 0 else "zero",
            "citations": [list(source) for source in self.sources],
        }


@dataclass(frozen=True)
class Date:
    period: str
    cells: Cells

    def fact(self, table: str, row: str, col: str = "C0010") -> Amount:
        value = self.cells[table, row, col]
        return Amount(Decimal(str(value)), ((self.period, table, row, col),))


def total(values: Iterable[Amount]) -> Amount:
    return sum(values, start=Amount(Decimal(0), ()))


def tolerance_evidence(periods: tuple[str, ...], value: str, unit: str) -> Record:
    fields = (
        ("ratio_precision",)
        if unit == "ratio"
        else (
            "money_unit_scale",
            "money_precision",
        )
    )
    return {
        "value": value,
        "unit": unit,
        "source": "docs/spec.md D3",
        "citations": [
            [p, "Metadata", field, "value"] for p in periods for field in fields
        ],
    }


def compare(
    day: Date,
    name: str,
    left: Amount,
    right: Amount,
    tolerance: str,
    evidence: str,
    unit: str = "EUR",
    gap: str = "",
) -> Record:
    diff = left - right
    observation = {
        "left": left.encoded(unit),
        "right": right.encoded(unit),
        "signed_discrepancy": diff.encoded(unit),
        "tolerance": tolerance,
        "operator": "absolute_discrepancy_less_than_or_equal",
        "tolerance_evidence": tolerance_evidence((day.period,), tolerance, unit),
    }
    record: Record = {
        "id": f"{day.period}_{name}",
        "period": day.period,
        "requirements": ["R-008", "R-022"],
        "source": evidence,
    }
    if gap:
        record.update(
            status="indeterminate",
            benchmark_dependency_open=True,
            reason=gap,
            fixture_arithmetic=observation,
        )
    else:
        record.update(observation)
        record["status"] = (
            "pass" if abs(Fraction(diff.n)) <= Fraction(tolerance) else "fail"
        )
    return record


def overlap_checks(day: Date, tolerance: str) -> list[Record]:
    f = day.fact
    health_rec = f(TP, "R0020", "C0210") + f(TP, "R0080", "C0210")
    linked_rec = total(
        f(TP, row, col)
        for row, col in [
            ("R0020", "C0030"),
            ("R0080", "C0040"),
            ("R0080", "C0050"),
            ("R0020", "C0120"),
            ("R0080", "C0120"),
        ]
    )
    items = [
        compare(
            day,
            "excess",
            f(BS, "R1000"),
            f(RR, "R0700", "C0060"),
            tolerance,
            "VERIFICATION §2, identical data point 7142772",
        ),
        compare(
            day,
            "health_slt_tp",
            f(BS, "R0610"),
            f(TP, "R0200", "C0210"),
            tolerance,
            "VERIFICATION §2, identical data point 7142834",
        ),
        compare(
            day,
            "health_slt_recoverables",
            f(BS, "R0320"),
            health_rec,
            tolerance,
            "VERIFICATION §2, BV379_1-1",
        ),
        compare(
            day,
            "linked_recoverables",
            f(BS, "R0340"),
            linked_rec,
            tolerance,
            "VERIFICATION §2, BV381_1-1",
        ),
        compare(
            day,
            "life_and_health_tp",
            f(BS, "R0600") + f(BS, "R0690"),
            f(TP, "R0200", "C0150") + f(TP, "R0200", "C0210"),
            tolerance,
            "VERIFICATION §2",
            gap="Complete life TP coverage and basis remain unverified.",
        ),
        compare(
            day,
            "ratio",
            f(OF, "R0620"),
            f(OF, "R0540").quotient(f(OF, "R0580")),
            "0.0001",
            "VERIFICATION §§2,6, BV87-1",
            "ratio",
        ),
    ]
    # In this portfolio all non-linked recoverables arise in direct
    # profit participation. The full official BV380 equation is not transcribed
    # in the versioned mapping. Do not certify this simplified identity.
    items.append(
        compare(
            day,
            "nonlinked_life_recoverables",
            f(BS, "R0330"),
            f(TP, "R0020", "C0020") + f(TP, "R0080", "C0020"),
            tolerance,
            "VERIFICATION §2, BV380_1-1",
            gap="Only the synthetic direct profit-participation subtotal is compared. "
            "The full BV380_1-1 operands are absent from the versioned mapping.",
        )
    )
    if (ADJUST, "R0220", "C0100") in day.cells:
        items.append(
            compare(
                day,
                "scr",
                f(OF, "R0580"),
                f(ADJUST, "R0220", "C0100"),
                tolerance,
                "VERIFICATION §2",
                gap="Whole-undertaking Article 112 context "
                "selection remains an open regulatory dependency.",
            )
        )
    else:
        items.append(
            {
                "id": f"{day.period}_scr",
                "period": day.period,
                "status": "unavailable",
                "missing_template": "S.25.01",
                "requirements": ["R-007", "R-008"],
                "reason": "No reported SCR in the missing template.",
            }
        )
    return items


def line(name: str, role: str, value: Amount, unit: str) -> Record:
    return {"id": name, "role": role, "status": "value", **value.encoded(unit)}


def bridge(
    name: str,
    requirements: list[str],
    opening: Amount,
    closing: Amount,
    movements: dict[str, Amount],
    tolerance: str,
    unit: str = "EUR",
) -> Record:
    residual = closing - opening - total(movements.values())
    return {
        "id": name,
        "requirements": requirements,
        "unit": unit,
        "tolerance": tolerance,
        "residual_status": "pass"
        if abs(Fraction(residual.n)) <= Fraction(tolerance)
        else "fail",
        "lines": [
            line("opening", "opening", opening, unit),
            *(line(key, "movement", val, unit) for key, val in movements.items()),
            line("residual", "residual", residual, unit),
            line("closing", "closing", closing, unit),
        ],
    }


def movement_bridge(
    name: str,
    requirements: list[str],
    days: tuple[Date, Date],
    endpoints: Callable[[Date], Amount],
    components: Callable[[Date], dict[str, Amount]],
    tolerance: str,
) -> Record:
    start, end = days
    a, b = components(start), components(end)
    result = bridge(
        name,
        requirements,
        endpoints(start),
        endpoints(end),
        {k: b[k] - v for k, v in a.items()},
        tolerance,
    )
    # Component levels document the sign and base used for the movement.
    for item in result["lines"]:
        key = item["id"]
        if item["role"] == "movement":
            item["opening_level"] = a[key].encoded()
            item["closing_level"] = b[key].encoded()
    return result


def excess_components(day: Date) -> dict[str, Amount]:
    def rows(row_ids: str) -> Amount:
        return total(day.fact(BS, row) for row in row_ids.split())

    return {
        "investments": rows("R0070"),
        "linked_assets": rows("R0220"),
        "deferred_tax_assets": rows("R0040"),
        "other_assets": rows(
            "R0030 R0050 R0060 R0230 R0270 R0350 R0360 R0370 "
            "R0380 R0390 R0400 R0410 R0420"
        ),
        "technical_provisions": rows("R0510 R0600 R0690").times(-1),
        "deferred_tax_liabilities": rows("R0780").times(-1),
        "other_liabilities": rows(
            "R0740 R0750 R0760 R0770 R0790 R0800 R0810 R0820 R0830 R0840 R0850 R0880"
        ).times(-1),
    }


def equity_components(day: Date) -> dict[str, Amount]:
    f = day.fact
    result = {
        "excess": f(RR, "R0700", "C0060"),
        "foreseeable_dividends_distributions_charges": f(RR, "R0720", "C0060").times(
            -1
        ),
        "own_shares": f(RR, "R0710", "C0060").times(-1),
        "rff_map": f(RR, "R0740", "C0060").times(-1),
        "subordinated_liabilities": f(OF, "R0140"),
        "ancillary_funds": f(OF, "R0400"),
    }
    for name, col in [
        ("unrestricted_t1", "C0020"),
        ("restricted_t1", "C0030"),
        ("tier2", "C0040"),
        ("tier3", "C0050"),
    ]:
        result[f"reported_eligibility_{name}"] = f(OF, "R0540", col) - f(
            OF, "R0500", col
        )
    return result


def scr_components(day: Date) -> dict[str, Amount]:
    return {
        **{
            name: day.fact(MODULE, row, "C0040")
            for name, row in [
                ("market", "R0010"),
                ("counterparty", "R0020"),
                ("life", "R0030"),
                ("health", "R0040"),
                ("nonlife", "R0050"),
                ("diversification", "R0060"),
                ("intangible", "R0070"),
            ]
        },
        **{
            name: day.fact(ADJUST, row, "C0100")
            for name, row in [
                ("rff_map", "R0120"),
                ("operational", "R0130"),
                ("lac_tp", "R0140"),
                ("lac_dt", "R0150"),
                ("article_4", "R0160"),
                ("add_ons", "R0210"),
            ]
        },
    }


def ratio_bridge(days: tuple[Date, Date]) -> Record:
    a, b = days
    e0, e1 = a.fact(OF, "R0540"), b.fact(OF, "R0540")
    s0, s1 = a.fact(OF, "R0580"), b.fact(OF, "R0580")
    de = e1 - e0
    return bridge(
        "solvency_ratio",
        ["R-011", "R-021", "R-032"],
        e0.quotient(s0).times(100),
        e1.quotient(s1).times(100),
        {
            "own_funds": de.quotient(s0).times(100),
            "scr": (e0.quotient(s1) - e0.quotient(s0)).times(100),
            "interaction": (de.quotient(s1) - de.quotient(s0)).times(100),
        },
        "0",
        "pp",
    )


def net_tp(day: Date, col: str) -> Amount:
    return day.fact(TP, "R0210", col)


def tp_components(day: Date, col: str) -> dict[str, Amount]:
    def at(row: str) -> Amount:
        return day.fact(TP, row, col)

    return {
        "tp_as_whole": at("R0010"),
        "gross_bel": at("R0030"),
        "risk_margin": at("R0100"),
        "recoverables_as_whole": at("R0020").times(-1),
        "bel_recoverables": at("R0080").times(-1),
    }


def schedules(days: tuple[Date, Date]) -> list[Record]:
    a, b = days
    result = []
    for table, row, col in sorted(a.cells.keys() & b.cells.keys()):
        # Keep each reportable LoB (including total LoBs and the option groups),
        # without adding a subtotal or a scenario to primary bridge movements.
        if not (
            (
                table == TP
                and row
                in {
                    "R0010",
                    "R0020",
                    "R0030",
                    "R0080",
                    "R0090",
                    "R0100",
                    "R0200",
                    "R0210",
                }
            )
            or (
                table == IMPACT
                and row == "R0010"
                and col in {"C0010", "C0030", "C0050", "C0070", "C0090"}
            )
            or table.startswith("S.26.")
        ):
            continue
        if table.startswith("S.26.") and not isinstance(a.cells[table, row, col], int):
            continue
        start, end = a.fact(table, row, col), b.fact(table, row, col)
        result.append(
            {
                "id": f"{table}/{row}/{col}",
                "requirements": [
                    "R-013" if table == TP else "R-014" if table == IMPACT else "R-019"
                ],
                "opening": start.encoded(),
                "closing": end.encoded(),
                "movement": (end - start).encoded(),
            }
        )
    return result


def tier_limits(day: Date, precision: Decimal) -> list[Record]:
    f = day.fact

    def tier(row: str, number: int) -> Amount:
        return f(OF, row, f"C00{number}0")

    def t1(row: str) -> Amount:
        return tier(row, 2) + tier(row, 3)

    scr = f(OF, "R0580")
    mcr = f(OF, "R0600")
    # Only the subordinated liability is a restricted instrument in these
    # packages. Available Tier 1 can already exclude amounts above the limit.
    instrument = tier("R0140", 3)
    eligible1r = tier("R0540", 3)
    eligible3 = tier("R0540", 5)
    available3 = tier("R0500", 5)
    eligible23 = tier("R0540", 4) + eligible3
    available23 = tier("R0500", 4) + available3
    comparisons = [
        ("article82_1_a", ">=", "0.50", t1("R0540"), scr, t1("R0500")),
        ("article82_1_b", "<", "0.15", eligible3, scr, available3),
        ("article82_1_c", "<=", "0.50", eligible23, scr, available23),
        ("article82_2_a", ">=", "0.80", t1("R0550"), mcr, t1("R0510")),
        ("article82_2_b", "<=", "0.20", tier("R0550", 4), mcr, tier("R0510", 4)),
        ("article82_3", "<", "0.20", eligible1r, t1("R0540"), instrument),
    ]
    result = []
    for rule, op, fraction, eligible, denominator, supply in comparisons:
        ceiling = Amount(
            Decimal(fraction) * Decimal(str(denominator.n)), denominator.sources
        )
        margin = (eligible - ceiling) if op == ">=" else (ceiling - eligible)
        haircut = supply - eligible
        # Round-off uncertainty of reported amounts is measured before inferring
        # eligibility. For Art. 82(3) the restricted amount occurs on both sides.
        ratio = Decimal(fraction)
        if rule == "article82_3":
            uncertainty = precision / 2
        else:
            uncertainty = (len(eligible.sources) + ratio) * precision / 2
        if denominator.n <= 0:
            compliance = "indeterminate"
        elif margin.n > uncertainty:
            compliance = "pass"
        elif margin.n < -uncertainty:
            compliance = "fail"
        else:
            compliance = "indeterminate"
        exact_compliant = margin.n > 0 if op == "<" else margin.n >= 0
        if compliance != "pass":
            status = "breach" if compliance == "fail" else "indeterminate"
        elif op == ">=":
            status = "slack"
        elif margin.n < precision and haircut.n > precision:
            status = "binding"
        elif margin.n > 0 and supply.n <= ceiling.n:
            status = "slack"
        else:
            status = "indeterminate"
        result.append(
            {
                "id": f"{day.period}_{rule}",
                "period": day.period,
                "rule": rule,
                "requirements": ["R-018", "R-022", "R-024"],
                "operator": op,
                "fraction": fraction,
                "precision_eur": canonical(precision),
                "rule_source": f"mappings/2.8.2/legal_limits.csv#{rule}",
                "supply": supply.encoded(),
                "eligible": eligible.encoded(),
                "denominator": denominator.encoded(),
                "legal_bound": ceiling.encoded(),
                "margin_to_legal_bound": margin.encoded(),
                "supply_less_eligible": haircut.encoded(),
                "reported_amounts_comply": exact_compliant,
                "compliance_with_rounding": compliance,
                "status": status,
            }
        )
    for item in result:
        if item["rule"] not in {"article82_3", "article82_1_b"}:
            continue
        restricted = item["rule"] == "article82_3"
        col = "C0030" if restricted else "C0050"
        instrument_row = "R0140" if restricted else "R0160"
        # Cite separately reported competing basic instruments and deductions.
        # The total rows for basic, available and eligible funds are controls.
        others = total(
            f(table, row, col)
            for table, row, column in sorted(day.cells)
            if table == OF and column == col and row < "R0290" and row != instrument_row
        )
        item["available_at_tier"] = f(OF, "R0500", col).encoded()
        item["reported_instrument"] = f(OF, instrument_row, col).encoded()
        item["other_basic_tier_items"] = others.encoded()
        item["basic_at_tier"] = f(OF, "R0290", col).encoded()
        item["combined_tier_headroom"] = (
            Amount(Decimal("0.50") * Decimal(str(scr.n)), scr.sources) - eligible23
        ).encoded()
        if item["status"] == "binding" and (
            others.n != 0
            or f(OF, instrument_row, col).n != f(OF, "R0290", col).n
            or eligible23.n >= Fraction(scr.n) / 2
        ):
            item["status"] = "indeterminate"
    return result


def tier_movements(items: list[Record], days: tuple[Date, Date]) -> list[Record]:
    by_date = {(t["period"], t["rule"]): t for t in items}
    result = []
    for rule, row, col in [
        ("article82_3", "R0140", "C0030"),
        ("article82_1_b", "R0500", "C0050"),
        ("article82_1_c", "R0500", "C0040"),
    ]:
        opening, closing = (by_date[d.period, rule]["status"] for d in days)
        observed = []
        for d in days:
            demand = d.fact(OF, row, col)
            eligible = d.fact(OF, "R0540", col)
            if rule == "article82_1_c":
                demand = demand + d.fact(OF, "R0500", "C0050")
                eligible = eligible + d.fact(OF, "R0540", "C0050")
            observed.append(demand - eligible)
        transition = {
            ("slack", "binding"): "newly_binding",
            ("binding", "slack"): "released",
            ("binding", "binding"): "persistent",
            ("slack", "slack"): "slack",
        }.get((opening, closing), "indeterminate")
        result.append(
            {
                "id": rule,
                "requirements": ["R-017", "R-018"],
                "transition": transition,
                "opening_status": opening,
                "closing_status": closing,
                "change_in_reported_supply_less_eligible": (
                    observed[1] - observed[0]
                ).encoded(),
                "source": "mappings/2.8.2/legal_limits.csv#" + rule,
            }
        )
    return result


def scr_detail_missing(start: Date, end: Date, tolerance: str) -> Record:
    missing = {
        "status": "unavailable",
        "period": "closing",
        "missing_template": "S.25.01",
        "reason": "Closing module and adjustment detail is absent.",
    }
    return {
        "id": "scr_modules",
        "requirements": ["R-007", "R-019", "R-020"],
        "residual_status": "unavailable",
        "tolerance": tolerance,
        "unit": "EUR",
        "lines": [
            line("opening", "opening", start.fact(OF, "R0580"), "EUR"),
            *(
                {
                    "id": key,
                    "role": "movement",
                    "opening_level": val.encoded(),
                    **missing,
                }
                for key, val in scr_components(start).items()
            ),
            {"id": "residual", "role": "residual", **missing},
            line("closing", "closing", end.fact(OF, "R0580"), "EUR"),
        ],
    }


def expected_run(case: str, run_id: str, opening: Cells, closing: Cells) -> Record:
    days = Date("opening", opening), Date("closing", closing)
    a, b = days
    is_stop = case == "2a" and run_id.endswith("stop")
    scale = "1000" if case == "2a" else "1"
    warnings: list[str] = []
    if case == "2b":
        warnings = ["va_status_changed", "va_tp_impact_material_shift"]
    if case == "3":
        warnings = ["closing_missing_S.25.01"]
    gate: Record = {
        "status": "blocked" if is_stop else "warn" if warnings else "pass",
        "requirements": ["R-004", "R-005", "R-006", "R-007", "R-031"],
        "warnings": warnings,
        "stops": ["unit_scale_mismatch"] if is_stop else [],
        "rerun_after_confirmed_conversion": case == "2a" and not is_stop,
    }
    result: Record = {
        "id": run_id,
        "gate": gate,
        "comparisons": [],
        "bridges": [],
        "tier_limits": [],
        "schedules": [],
        "unsupported_splits": [],
    }
    if is_stop:
        result["withheld"] = [
            {
                "id": "all_cross_period_movements",
                "status": "withheld",
                "dependency": "R-005/unit_scale_mismatch",
                "reason": "Unconfirmed opening thousands and closing units.",
            }
        ]
        return result
    result["comparisons"] = overlap_checks(a, scale) + overlap_checks(b, "1")
    result["tier_limits"] = tier_limits(a, Decimal(scale)) + tier_limits(b, Decimal(1))
    bridges = [
        movement_bridge(
            "excess",
            ["R-011", "R-016"],
            days,
            lambda d: d.fact(BS, "R1000"),
            excess_components,
            scale,
        ),
        movement_bridge(
            "eligible_own_funds",
            ["R-011", "R-017"],
            days,
            lambda d: d.fact(OF, "R0540"),
            equity_components,
            scale,
        ),
        ratio_bridge(days),
    ]
    for day, tolerance in zip(days, (scale, "1"), strict=True):
        components = equity_components(day)
        excess = components.pop("excess")
        bridges.append(
            bridge(
                f"{day.period}_excess_to_eligible",
                ["R-011", "R-017", "R-018"],
                excess,
                day.fact(OF, "R0540"),
                components,
                tolerance,
            )
        )
    for name, col in (("life", "C0150"), ("health_slt", "C0210")):
        bridges.append(
            movement_bridge(
                f"{name}_net_tp",
                ["R-011", "R-012", "R-013"],
                days,
                partial(net_tp, col=col),
                partial(tp_components, col=col),
                scale,
            )
        )
    start, end = a.fact(OF, "R0580"), b.fact(OF, "R0580")
    bridges.append(
        bridge(
            "headline_scr",
            ["R-019", "R-020"],
            start,
            end,
            {"reported_scr_change": end - start},
            scale,
        )
    )
    if (ADJUST, "R0220", "C0100") in closing:
        bridges.append(
            movement_bridge(
                "scr_modules",
                ["R-011", "R-019"],
                days,
                lambda d: d.fact(OF, "R0580"),
                scr_components,
                scale,
            )
        )
    else:
        bridges.append(scr_detail_missing(a, b, scale))
    for br in bridges:
        if br["unit"] == "pp":
            br["tolerance_evidence"] = {
                "value": "0",
                "unit": "pp",
                "source": "docs/spec.md D5: exact identity",
            }
        else:
            periods = (
                ("opening",)
                if br["id"].startswith("opening_")
                else ("closing",)
                if br["id"].startswith("closing_")
                else ("opening", "closing")
            )
            br["tolerance_evidence"] = tolerance_evidence(
                periods, br["tolerance"], "EUR"
            )
    result["tier_changes"] = tier_movements(result["tier_limits"], days)
    result["bridges"] = bridges
    result["schedules"] = schedules(days)
    if case == "2b":
        result["unsupported_splits"].append(
            {
                "id": "restricted_tier1_excess_reclassified_to_tier2",
                "period": "closing",
                "status": "unavailable",
                "requirements": ["R-017", "R-018"],
                "reason": "S.23.01 has no separately reported transfer. The standalone "
                "eligible Tier 2 change cannot establish the amount reclassified.",
                "source": "mappings/VERIFICATION.md §3",
            }
        )
    return result
