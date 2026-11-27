"""Source-backed balance sheet, own funds, SCR and coverage bridges (R-016–R-021)."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from s2movement.bridge_dsl import (
    PUBLIC,
    component,
    divide,
    fact,
    neg,
    pp,
    residual_bridge,
    sub,
    summed,
)
from s2movement.check_catalog import ROOT
from s2movement.engine import (
    BridgeDefinition,
    Expr,
    LineDefinition,
    RatioValidation,
    UnsupportedSplit,
    _eval,
)
from s2movement.gate import PERIODS, metadata_citations
from s2movement.models import Ledger, Period

BALANCE = "S.02.01.01.01"
FUNDS = "S.23.01.01.01"
RESERVE = "S.23.01.01.02"
MODULES = "S.25.01.01.01"
ADJUSTMENTS = "S.25.01.01.02"


@dataclass(frozen=True)
class ReportedPart:
    id: str
    label: str
    table: str
    rows: tuple[str, ...]
    column: str = "C0010"
    deduction: bool = False
    subtract_row: str | None = None
    public_column: str | None = None
    covered_rows: tuple[str, ...] = ()

    def level(self, ledger: Ledger, period: Period) -> Expr:
        column = self.column
        if self.public_column:
            variant = ledger.metadata_value(period, "variant")
            if variant and variant.value == "public_disclosure":
                column = self.public_column
        amount = summed(
            fact(ledger, period, self.table, row, column) for row in self.rows
        )
        if self.subtract_row:
            amount = sub(
                amount, fact(ledger, period, self.table, self.subtract_row, self.column)
            )
        return neg(amount) if self.deduction else amount

    def line(
        self,
        ledger: Ledger,
        period: Period | None = None,
        dependencies: tuple[str, ...] = (),
    ) -> LineDefinition:
        value: Expr
        if period is None:
            value = sub(self.level(ledger, "closing"), self.level(ledger, "opening"))
        else:
            value = self.level(ledger, period)
        if self.subtract_row:
            sign = "eligible less available"
        elif self.deduction:
            sign = "deduct reported amount"
        else:
            sign = "as reported"
        if period is None:
            sign = "closing less opening, " + sign
        variants = {
            p: ledger.metadata_value(p, "variant")
            for p in ((period,) if period is not None else ("opening", "closing"))
        }
        coordinates = []
        for date, variant in variants.items():
            public = variant is not None and variant.value == "public_disclosure"
            table = PUBLIC.get(self.table, self.table) if public else self.table
            column = (
                self.public_column if public and self.public_column else self.column
            )
            for row in self.rows + ((self.subtract_row,) if self.subtract_row else ()):
                coordinates.append(f"{date} {table} {row}/{column}")
        return replace(
            component(self.id, self.label, value, sign, dependencies),
            component_rows=tuple(coordinates),
            covered_rows=self.covered_rows,
        )


def _balance_parts() -> tuple[ReportedPart, ...]:
    data = json.loads(
        (ROOT / "mappings/2.8.2/balance_sheet_buckets.json").read_text(encoding="utf-8")
    )
    return tuple(
        ReportedPart(
            b["id"],
            b["label"],
            BALANCE,
            tuple(b["reported_roots"]),
            deduction=b["sign"] == -1,
            covered_rows=tuple(b["rows"]),
        )
        for b in data["buckets"]
    )


BALANCE_PARTS = _balance_parts()


EXCESS = ReportedPart(
    "excess", "Excess of assets over liabilities", RESERVE, ("R0700",), "C0060"
)
OWN_FUNDS_PARTS = (
    ReportedPart(
        "foreseeable_dividends_distributions_charges",
        "Foreseeable dividends, distributions and charges",
        RESERVE,
        ("R0720",),
        "C0060",
        deduction=True,
    ),
    ReportedPart(
        "own_shares", "Own shares", RESERVE, ("R0710",), "C0060", deduction=True
    ),
    ReportedPart(
        "rff_map",
        "Restricted own fund items due to RFFs and MAPs",
        RESERVE,
        ("R0740",),
        "C0060",
        deduction=True,
    ),
    ReportedPart(
        "subordinated_liabilities", "Subordinated liabilities", FUNDS, ("R0140",)
    ),
    ReportedPart("ancillary_funds", "Ancillary own funds", FUNDS, ("R0400",)),
    # These are observed differences, not an attribution to any one legal limit.
    *(
        ReportedPart(
            "reported_eligibility_" + key,
            label + " eligible less available",
            FUNDS,
            ("R0540",),
            column,
            subtract_row="R0500",
        )
        for key, label, column in (
            ("unrestricted_t1", "Unrestricted Tier 1", "C0020"),
            ("restricted_t1", "Restricted Tier 1", "C0030"),
            ("tier2", "Tier 2", "C0040"),
            ("tier3", "Tier 3", "C0050"),
        )
    ),
)
SCR_PARTS = (
    *(
        ReportedPart(key, label, MODULES, (row,), "C0040", public_column="C0110")
        for key, label, row in (
            ("market", "Market risk", "R0010"),
            ("counterparty", "Counterparty default risk", "R0020"),
            ("life", "Life underwriting risk", "R0030"),
            ("health", "Health underwriting risk", "R0040"),
            ("nonlife", "Non-life underwriting risk", "R0050"),
            ("diversification", "Diversification", "R0060"),
            ("intangible", "Intangible asset risk", "R0070"),
        )
    ),
    # Diversification, LAC-TP and LAC-DT already carry their reported signs.
    *(
        ReportedPart(key, label, ADJUSTMENTS, (row,), "C0100")
        for key, label, row in (
            (
                "rff_map",
                "Adjustment for aggregation of notional SCRs in RFFs and MAPs",
                "R0120",
            ),
            ("operational", "Operational risk", "R0130"),
            ("lac_tp", "Loss-absorbing capacity of technical provisions", "R0140"),
            ("lac_dt", "Loss-absorbing capacity of deferred taxes", "R0150"),
            (
                "article_4",
                "Capital requirement under Article 4 of Directive 2003/41/EC",
                "R0160",
            ),
            ("add_ons", "Capital add-ons", "R0210"),
        )
    ),
)


def _period_own_funds(ledger: Ledger, period: Period) -> BridgeDefinition:
    return residual_bridge(
        f"{period}_excess_to_eligible",
        f"{period.capitalize()} excess to eligible own funds",
        EXCESS.level(ledger, period),
        fact(ledger, period, FUNDS, "R0540"),
        [part.line(ledger, period) for part in OWN_FUNDS_PARTS],
        residual_dependencies=(f"{period}_excess_consistency",),
        period=period,
    )


def _ratio(
    eligible0: Expr, eligible1: Expr, scr0: Expr, scr1: Expr
) -> BridgeDefinition:
    change = sub(eligible1, eligible0)
    funds = divide(change, scr0)
    scr = sub(divide(eligible0, scr1), divide(eligible0, scr0))
    interaction = sub(divide(change, scr1), divide(change, scr0))
    return residual_bridge(
        "solvency_ratio",
        "Solvency ratio decomposition (percentage points)",
        pp(divide(eligible0, scr0)),
        pp(divide(eligible1, scr1)),
        [
            component(
                "own_funds",
                "Own funds effect",
                pp(funds),
                "100 × (E1 − E0) / S0",
                ("ratio",),
            ),
            component(
                "scr", "SCR effect", pp(scr), "100 × E0 × (1/S1 − 1/S0)", ("ratio",)
            ),
            component(
                "interaction",
                "Interaction",
                pp(interaction),
                "100 × (E1 − E0) × (1/S1 − 1/S0)",
                ("ratio",),
            ),
        ],
        dependencies=("ratio",),
        unit="pp",
        formula_notes=(
            "D5. E is own funds eligible to meet the SCR (S.23.01 R0540/C0010); "
            "S is SCR (S.23.01 R0580/C0010). Subscripts 0 and 1 denote opening "
            "and closing. Both SCR amounts must be reported and strictly positive.",
            "Own funds effect = 100 × (E1 − E0) / S0 percentage points.",
            "SCR effect = 100 × E0 × (1/S1 − 1/S0) percentage points.",
            "Interaction = 100 × (E1 − E0) × (1/S1 − 1/S0) percentage points. "
            "It is a separate effect and is not allocated to either other line.",
            "The three effects sum exactly to 100 × (E1/S1 − E0/S0). The residual "
            "is an identity check and must equal zero. Python retains exact "
            "rational values; JSON preserves them as exact decimal or fraction "
            "strings. Excel displays six decimal places without rounding formulas.",
        ),
    )


def ratio_validations(ledger: Ledger) -> tuple[RatioValidation, ...]:
    """Validate the two denominators before exposing any D5 calculation."""
    results = []
    for period in PERIODS:
        ident = f"{period}_ratio_scr_positive"
        expression = fact(ledger, period, FUNDS, "R0580")
        amount = _eval(ledger, expression, "Reported SCR", ident)
        valid = amount.value is not None and amount.value > 0
        message = (
            f"{period} S.23.01 R0580/C0010 SCR must be reported and strictly "
            "positive for the D5 solvency-ratio calculation. "
            "Correct the cited SCR using source evidence and rerun."
        )
        results.append(
            RatioValidation(
                ident,
                period,
                "pass" if valid else "fail",
                amount,
                expression,
                message,
                amount.citations
                or metadata_citations(ledger, ("reference_date",), (period,)),
            )
        )
    return tuple(results)


def capital(ledger: Ledger) -> list[BridgeDefinition]:
    """Construct the formula trees once for Python, JSON evidence and Excel."""
    eligible0 = fact(ledger, "opening", FUNDS, "R0540")
    eligible1 = fact(ledger, "closing", FUNDS, "R0540")
    scr0 = fact(ledger, "opening", FUNDS, "R0580")
    scr1 = fact(ledger, "closing", FUNDS, "R0580")
    return [
        residual_bridge(
            "excess",
            "Excess of assets over liabilities",
            fact(ledger, "opening", BALANCE, "R1000"),
            fact(ledger, "closing", BALANCE, "R1000"),
            [
                part.line(ledger, dependencies=("excess_consistency",))
                for part in BALANCE_PARTS
            ],
            dependencies=("excess_consistency",),
        ),
        residual_bridge(
            "eligible_own_funds",
            "Eligible own funds to meet the SCR",
            eligible0,
            eligible1,
            [
                EXCESS.line(ledger, dependencies=("excess_consistency",)),
                *(part.line(ledger) for part in OWN_FUNDS_PARTS),
            ],
        ),
        _period_own_funds(ledger, "opening"),
        _period_own_funds(ledger, "closing"),
        residual_bridge(
            "headline_scr",
            "Reported SCR",
            scr0,
            scr1,
            [
                component(
                    "reported_scr_change",
                    "Change in reported SCR",
                    sub(scr1, scr0),
                    "closing less opening",
                )
            ],
        ),
        residual_bridge(
            "scr_modules",
            "SCR by gross risk module and reported adjustment",
            scr0,
            scr1,
            [part.line(ledger, dependencies=("scr",)) for part in SCR_PARTS],
            dependencies=("scr",),
            formula_notes=(
                "Each movement is closing less opening, in the common reported "
                "monetary unit. Modules use gross S.25.01 C0040 (supervisory) or "
                "C0110 (public disclosure). Diversification and LAC-TP/LAC-DT "
                "retain their reported signs. The R0120 RFF/MAP and R0160 Article 4 "
                "adjustments and R0210 capital add-ons are separate lines.",
                "The additive gross basis is documented in mappings/VERIFICATION.md "
                "under SCR bridge basis for R-019 (BV254_1-2-7 and BV134-1-6). "
                "S.26.01–S.26.03 are cited drill-down schedules only; no S.26 "
                "amount feeds a top-level S.25.01 result.",
                "Opening and closing SCR come from S.23.01. The separately displayed "
                "residual is closing less opening and all signed movements, assessed "
                "against D3. Missing S.25.01 leaves its module detail Unavailable "
                "and preserves the S.23.01 headline SCR movement.",
            ),
        ),
        _ratio(eligible0, eligible1, scr0, scr1),
    ]


def own_fund_splits(ledger: Ledger) -> list[UnsupportedSplit]:
    result = []
    for period in ("opening", "closing"):
        for ident, row, reason in (
            (
                "foreseeable_dividends_distributions_charges_split",
                "R0720",
                "S.23.01 reports foreseeable dividends, distributions "
                "and charges together.",
            ),
            (
                "rff_map_restrictions_split",
                "R0740",
                "S.23.01 reports restrictions for ring-fenced funds "
                "and matching adjustment portfolios together.",
            ),
        ):
            aggregate = _eval(
                ledger,
                fact(ledger, period, RESERVE, row, "C0060"),
                "Reported aggregate",
                ident,
            )
            result.append(
                UnsupportedSplit(ident, period, reason, "S.23.01", aggregate.citations)
            )
    return result
