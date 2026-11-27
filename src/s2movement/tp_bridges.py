"""Technical provision movements, reported detail and observed linked comparisons."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from functools import cache
from typing import Literal

from s2movement.bridge_dsl import (
    PUBLIC,
    add,
    component,
    fact,
    neg,
    residual_bridge,
    sub,
    summed,
)
from s2movement.check_catalog import ROOT, Address
from s2movement.engine import (
    BridgeDefinition,
    CellRef,
    Expr,
    FactExpr,
    LinkedMateriality,
    ScheduleDefinition,
    UnsupportedSplit,
    _eval,
)
from s2movement.gate import PERIODS, metadata
from s2movement.models import Ledger, Period

TP = "S.12.01.01.01"
LTG = "S.22.01.01.01"
BS = "S.02.01.01.01"
RECOVERABLES = {"R0020", "R0080"}
TP_ROWS = (
    ("tp_as_whole", "Technical provisions calculated as a whole", "R0010"),
    ("gross_bel", "Gross best estimate", "R0030"),
    ("risk_margin", "Risk margin", "R0100"),
    ("recoverables_as_whole", "Recoverables on TP calculated as a whole", "R0020"),
    ("bel_recoverables", "Recoverables on the best estimate", "R0080"),
)
TRANSITIONALS = (
    ("transitional_whole", "TMTP allocated to TP calculated as a whole", "R0110"),
    ("transitional_bel", "TMTP allocated to the best estimate", "R0120"),
    ("transitional_rm", "TMTP allocated to the risk margin", "R0130"),
)
DETAIL_ROWS = {row for _, _, row in TP_ROWS} | {"R0090", "R0200", "R0210"}
SCENARIOS = ("C0010", "C0030", "C0050", "C0070", "C0090")
LINKED = (
    ("R0220", "Assets held for index-linked and unit-linked contracts"),
    ("R0340", "Recoverables on index-linked and unit-linked contracts"),
    ("R0700", "Linked technical provisions calculated as a whole"),
    ("R0710", "Linked gross best estimate"),
    ("R0720", "Linked risk margin"),
)


@cache
def _labels() -> dict[Address, str]:
    with (ROOT / "mappings/2.8.2/cells.csv").open(encoding="utf-8") as stream:
        return {
            (
                r["table"],
                r["row"],
                r["column"],
            ): f"{r['column_label']} — {r['row_label']}"
            for r in csv.DictReader(stream)
        }


def _net_tp(ledger: Ledger, period: Period, col: str) -> Expr:
    if metadata(ledger, period, "variant") == "public_disclosure":
        # Disclosure contains the post-transition gross total and both after-default
        # recoverables, but no R0210 net total.
        gross = fact(ledger, period, TP, "R0200", col)
        return sub(
            sub(gross, fact(ledger, period, TP, "R0020", col)),
            fact(ledger, period, TP, "R0080", col),
        )
    return fact(ledger, period, TP, "R0210", col)


def _checks(row: str, col: str) -> tuple[str, ...]:
    health_tp = col == "C0210" and row not in RECOVERABLES
    checks = ("health_slt_tp",) if health_tp else ()
    if row in RECOVERABLES | {"R0090", "R0210"}:
        if col == "C0210":
            return checks + ("health_slt_recoverables",)
        if col == "C0150":
            return ("nonlinked_life_recoverables", "linked_recoverables")
        if col in {"C0030", "C0040", "C0050", "C0120"}:
            return ("linked_recoverables",)
    return checks


def _component_rows(ledger: Ledger, col: str) -> tuple[tuple[str, str, str], ...]:
    active = any(metadata(ledger, p, "tmtp_applied") != "no" for p in PERIODS)
    reported = any(
        f.template == "S.12.01"
        and f.row in {"R0110", "R0120", "R0130"}
        and f.column == col
        and f.reported_value != 0
        for f in ledger.facts
    )
    return TP_ROWS + (TRANSITIONALS if active or reported else ())


BUSINESSES = (
    ("life", "C0150", "Life other than health, including linked business"),
    ("health_slt", "C0210", "Health similar to life"),
)


def tp(ledger: Ledger) -> list[BridgeDefinition]:
    bridges = []
    for key, col, business in BUSINESSES:
        # S.12 components precede TMTP, whereas totals follow it.
        rows = _component_rows(ledger, col)
        movements = []
        for name, label, row in rows:
            before, after = (fact(ledger, p, TP, row, col) for p in PERIODS)
            change: Expr = sub(after, before)
            sign = "Closing minus opening, with reported sign"
            if row in RECOVERABLES:
                change = neg(change)
                sign = "An increase in recoverables reduces net technical provisions"
            movements.append(component(name, label, change, sign, _checks(row, col)))
        bridges.append(
            residual_bridge(
                f"{key}_net_tp",
                f"{business} — net technical provisions",
                _net_tp(ledger, "opening", col),
                _net_tp(ledger, "closing", col),
                movements,
            )
        )
    return bridges


def _overview(ledger: Ledger) -> list[ScheduleDefinition]:
    result = []
    for key, col, _ in BUSINESSES:
        rows = _component_rows(ledger, col)
        for name, label, row in rows:
            before, after = (fact(ledger, p, TP, row, col) for p in PERIODS)
            result.append(
                ScheduleDefinition(
                    f"tp/{key}/{name}",
                    label,
                    before,
                    after,
                    _checks(row, col),
                    bridge_id=f"{key}_net_tp",
                    category="tp_component",
                )
            )
        net_bel = {
            p: sub(fact(ledger, p, TP, "R0030", col), fact(ledger, p, TP, "R0080", col))
            for p in PERIODS
        }
        result.append(
            ScheduleDefinition(
                f"tp/{key}/net_bel",
                "Net best estimate — subtotal",
                net_bel["opening"],
                net_bel["closing"],
                _checks("R0090", col),
                bridge_id=f"{key}_net_tp",
                category="tp_subtotal",
            )
        )
        totals = {}
        for p in PERIODS:
            # Count net BEL once. Gross BEL and its recoverables are detail.
            total = add(
                sub(
                    fact(ledger, p, TP, "R0010", col), fact(ledger, p, TP, "R0020", col)
                ),
                add(net_bel[p], fact(ledger, p, TP, "R0100", col)),
            )
            if len(rows) > len(TP_ROWS):
                total = add(
                    total,
                    summed(fact(ledger, p, TP, r, col) for _, _, r in TRANSITIONALS),
                )
            totals[p] = total
        dependencies = tuple(
            dict.fromkeys(check for _, _, row in rows for check in _checks(row, col))
        )
        result.append(
            ScheduleDefinition(
                f"tp/{key}/components_total",
                "Net TP from components",
                totals["opening"],
                totals["closing"],
                dependencies,
                bridge_id=f"{key}_net_tp",
                category="tp_total",
            )
        )
    return result


def _reported_schedules(ledger: Ledger) -> list[ScheduleDefinition]:
    # Include a column that exists at either date, and the main components
    # even if both templates are missing. Keep unreported values explicit.
    labels = _labels()
    present = {
        (f.row, f.column)
        for f in ledger.facts
        if f.template == "S.12.01" and f.row in DETAIL_ROWS
    }
    columns = {col for _, col in present} | {"C0150", "C0210"}
    present.update((row, col) for row in DETAIL_ROWS for col in columns)
    coordinates = [(TP, row, col) for row, col in sorted(present)]
    coordinates.extend((LTG, "R0010", col) for col in SCENARIOS)
    public_only = all(
        metadata(ledger, p, "variant") == "public_disclosure" for p in PERIODS
    )
    result = []
    for table, row, col in coordinates:
        physical = PUBLIC[table] if public_only else table
        addr = (physical, row, col)
        if addr not in labels:
            continue
        before, after = (fact(ledger, p, table, row, col) for p in PERIODS)
        checks = _checks(row, col) if table == TP else ()
        result.append(
            ScheduleDefinition(
                "/".join(addr),
                labels[addr],
                before,
                after,
                checks,
                category="ltg_scenario" if table == LTG else "reported_detail",
            )
        )
    return result


def _risk_schedules(ledger: Ledger) -> list[ScheduleDefinition]:
    # The same physical cell can occur once per portfolio. Match dimensions
    # across dates, never local workbook context IDs or a row code alone.
    by_cell: defaultdict[Address, set[tuple[str, tuple[tuple[str, str], ...]]]]
    by_cell = defaultdict(set)
    for f in ledger.facts:
        if f.template in {"S.26.01", "S.26.02", "S.26.03"}:
            by_cell[f.table, f.row, f.column].add(
                (f.coordinate_context or "", tuple(sorted(f.dimensions.items())))
            )
    result = []
    for addr, contexts in sorted(by_cell.items()):
        for coordinate, dims in sorted(contexts):
            ident = "/".join(addr)
            label = _labels()[addr]
            if len(contexts) > 1:
                context_label = " ".join(f"{k}={v}" for k, v in dims)
                ident += f"/{coordinate}/{context_label}"
                label += f" ({coordinate} {context_label})"
            before, after = (
                FactExpr(CellRef(p, *addr, dict(dims), coordinate or None))
                for p in PERIODS
            )
            result.append(
                ScheduleDefinition(
                    ident,
                    label,
                    before,
                    after,
                    category="scr_drilldown",
                    bridge_id="scr_modules",
                )
            )
    return result


def linked_materiality(ledger: Ledger) -> tuple[LinkedMateriality, ...]:
    settings = json.loads(
        (ROOT / "tests/fixtures/thresholds.yaml").read_text(encoding="utf-8")
    )
    rule = settings["rules"]["linked_materiality"]["threshold"]
    floor = Decimal(str(rule["absolute_eur"]))
    fraction = Decimal(rule["fraction_of_total_assets"])
    results = []
    for period in PERIODS:
        linked_expr, total_expr = (
            fact(ledger, period, BS, r) for r in ("R0220", "R0500")
        )
        linked = _eval(
            ledger, linked_expr, "Reported linked assets", "linked_materiality"
        )
        total = _eval(ledger, total_expr, "Reported total assets", "linked_materiality")
        reason = total.reason or linked.reason
        if total.value is not None and total.value <= 0:
            reason = f"{period} total assets are nonpositive."
        if any(
            v.currency != settings["scope"]["currency"]
            for v in (linked, total)
            if v.status == "value"
        ):
            reason = "The frozen absolute materiality floor is specified in EUR."
        threshold = replace(
            total,
            status="indeterminate",
            value=None,
            currency="EUR",
            unit_scale=Decimal(1),
            precision=None,
            sign="max(absolute EUR floor, fraction × same-date total assets)",
            reason=reason,
        )
        status: Literal["material", "not_material", "indeterminate"] = "indeterminate"
        if reason is None and total.value is not None and linked.value is not None:
            assert total.unit_scale is not None and linked.unit_scale is not None
            limit = max(floor, fraction * total.value * total.unit_scale)
            threshold = replace(threshold, status="value", value=limit)
            status = (
                "material"
                if abs(linked.value * linked.unit_scale) > limit
                else "not_material"
            )
        results.append(
            LinkedMateriality(
                period,
                status,
                linked,
                total,
                threshold,
                linked_expr,
                total_expr,
                floor,
                fraction,
            )
        )
    return tuple(results)


def _pairing(
    ledger: Ledger, materiality: tuple[LinkedMateriality, ...]
) -> list[ScheduleDefinition]:
    # If materiality cannot be determined, show the observed components so a
    # missing denominator or a currency outside the EUR settings hides no data.
    if all(item.status == "not_material" for item in materiality):
        return []
    result = []
    for row, label in LINKED:
        before, after = (fact(ledger, p, BS, row) for p in PERIODS)
        deps = ("linked_recoverables",) if row == "R0340" else ()
        result.append(
            ScheduleDefinition(
                f"linked/{row}",
                label,
                before,
                after,
                deps,
                category="linked_movement",
            )
        )
        if row != "R0220":
            left, right = (
                sub(fact(ledger, p, BS, "R0220"), fact(ledger, p, BS, row))
                for p in PERIODS
            )
            result.append(
                ScheduleDefinition(
                    f"linked/assets_less_{row}",
                    "Difference between movements — linked assets minus "
                    + label.lower(),
                    left,
                    right,
                    deps,
                    sign="Change in linked assets minus change in the named comparator",
                    category="movement_difference",
                    operands=("linked/R0220", f"linked/{row}"),
                )
            )

    def balance(period: Period) -> Expr:
        assets, rec, whole, bel, rm = (fact(ledger, period, BS, r) for r, _ in LINKED)
        return sub(add(assets, rec), add(add(whole, bel), rm))

    result.append(
        ScheduleDefinition(
            "linked/observed_difference",
            "Linked assets plus recoverables less TP as a whole, "
            "gross BEL and risk margin — difference between aggregate movements",
            balance("opening"),
            balance("closing"),
            ("linked_recoverables",),
            category="linked_aggregate_difference",
        )
    )
    return result


def schedules(
    ledger: Ledger, materiality: tuple[LinkedMateriality, ...]
) -> list[ScheduleDefinition]:
    return (
        _reported_schedules(ledger)
        + _risk_schedules(ledger)
        + _overview(ledger)
        + _pairing(ledger, materiality)
    )


def unsupported_splits(ledger: Ledger) -> list[UnsupportedSplit]:
    result = []
    for period in PERIODS:
        aggregate = fact(ledger, period, TP, "R0100", "C0030")
        if not isinstance(aggregate, FactExpr):
            continue
        ref = aggregate.ref
        total = ledger.find_fact(
            period=period,
            table=ref.table,
            row=ref.row,
            column=ref.column,
            dimensions=ref.dimensions,
            coordinate_context=ref.coordinate_context,
        )
        result.append(
            UnsupportedSplit(
                "linked_risk_margin_by_guarantee_group",
                period,
                "S.12.01 reports one risk margin for Index-linked and unit-linked "
                "insurance. The guarantee-group split is unavailable.",
                "S.12.01",
                (total.citation,) if total else (),
            )
        )
    return result
