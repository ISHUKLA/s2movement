"""Independent synthetic financial statements, in whole EUR before workbook scaling."""

import csv
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import cache
from pathlib import Path

type Address = tuple[str, str, str]
type Cells = dict[Address, int | str]

BS = "S.02.01.01.01"
FLOW = "S.05.01.01.02"
LIFE = "S.12.01.01.01"
LTG = "S.22.01.01.01"
FUNDS = "S.23.01.01.01"
RESERVE = "S.23.01.01.02"
MODULE = "S.25.01.01.01"
SCR = "S.25.01.01.02"
MARKET = "S.26.01.01.02"
DEFAULT = "S.26.02.01.01"
UNDERWRITING = "S.26.03.01.04"
M = 1_000_000


@cache
def _coordinates() -> frozenset[Address]:
    mapping = Path(__file__).resolve().parents[2] / "mappings/2.8.2/cells.csv"
    with mapping.open(encoding="utf-8", newline="") as source:
        return frozenset(
            (row["table"], row["row"], row["column"])
            for row in csv.DictReader(source)
            if row["supervisory_ars"] == "yes"
        )


@dataclass(frozen=True)
class Statement:
    """Independently specified levels before aggregating the reported schedules."""

    bonds: int = 500 * M
    linked_assets: int = 120 * M
    cash: int = 33 * M
    tax_asset: int = 8 * M
    payables: int = 15 * M
    life_whole: int = 20 * M
    life_bel: int = 300 * M
    life_rec: int = 12 * M
    life_rm: int = 10 * M
    linked_whole: int = 5 * M
    linked_no_options: int = 60 * M
    linked_with_options: int = 50 * M
    linked_rm: int = 5 * M
    health_whole: int = M
    health_bel: int = 30 * M
    health_rm: int = 4 * M
    debt_restricted: int = 0
    debt_tier2: int = 5 * M
    available_tier2: int = 5 * M
    dividends: int = 0
    market: int = 80 * M
    default: int = 12 * M
    life_risk: int = 48 * M
    health_risk: int = 15 * M
    diversification: int = -45 * M
    operational: int = 8 * M
    tax_relief: int = -18 * M
    mcr: int = 40 * M
    linked_written: int = 50_000
    health_claims: int = 40_000
    va_impact: int = 0


def _statement(case: str, closing: bool) -> Statement:
    base = Statement()
    match case:
        case "1":
            other = replace(
                base,
                bonds=509 * M,
                life_bel=303 * M,
                health_bel=30_700_000,
                payables=15_400_000,
            )
        case "2a":
            base = replace(base, cash=18_250_000)
            other = replace(
                base,
                bonds=540 * M,
                cash=18_375_250,
                health_bel=36 * M,
                health_rm=3 * M,
                life_rec=36 * M,
                operational=10 * M,
            )
        case "2b":
            base = replace(
                base,
                bonds=418_000_003,
                debt_tier2=0,
                available_tier2=0,
                debt_restricted=10 * M,
                market=68 * M,
                mcr=35 * M,
            )
            other = replace(
                base,
                bonds=433_000_003,
                debt_restricted=25 * M,
                available_tier2=5 * M,
                life_whole=24 * M,
                life_rec=16 * M,
                life_risk=55 * M,
                default=9 * M,
                va_impact=15 * M,
            )
        case "3":
            base = replace(base, dividends=5 * M)
            other = replace(
                base,
                dividends=18 * M,
                bonds=482 * M,
                life_bel=280 * M,
                linked_no_options=61 * M,
                health_bel=31 * M,
                market=92 * M,
                linked_written=400_000,
                health_claims=350_000,
            )
        case "4":
            other = replace(
                base,
                linked_assets=140 * M,
                linked_no_options=68 * M,
                linked_with_options=43 * M,
                linked_rm=6 * M,
                linked_written=20 * M,
            )
        case "5":
            base = replace(
                base, debt_tier2=20 * M, available_tier2=20 * M, mcr=40_000_004
            )
            other = replace(
                base,
                tax_asset=32 * M,
                bonds=476 * M,
                market=95_000_006,
                health_risk=12 * M,
                tax_relief=-10 * M,
            )
        case _:
            raise ValueError(f"Unknown benchmark case {case!r}")
    return other if closing else base


@dataclass(frozen=True)
class Provision:
    whole: int
    bel: int
    rec: int  # All ceded recoverables relate to BEL; the whole contracts have none.
    rm: int

    @property
    def gross(self) -> int:
        return self.whole + self.bel + self.rm

    def __add__(self, other: "Provision") -> "Provision":
        return Provision(
            self.whole + other.whole,
            self.bel + other.bel,
            self.rec + other.rec,
            self.rm + other.rm,
        )


def _column(cells: Cells, table: str, column: str, amounts: dict[str, int]) -> None:
    for row, value in amounts.items():
        cells[table, row, column] = value


def _balance_sheet(
    cells: Cells, p: Statement, life: Provision, linked: Provision, health: Provision
) -> int:
    # Only Solvency II values are reported. Statutory accounts are a separate basis.
    cells.update(
        dict.fromkeys((k for k in _coordinates() if k[0] == BS and k[2] == "C0010"), 0)
    )
    recovery = life.rec + health.rec + linked.rec
    debt = p.debt_restricted + p.debt_tier2
    assets = p.tax_asset + p.bonds + p.linked_assets + recovery + p.cash
    liabilities = life.gross + health.gross + linked.gross + p.payables + debt
    _column(
        cells,
        BS,
        "C0010",
        {
            "R0040": p.tax_asset,
            "R0070": p.bonds,
            "R0130": p.bonds,
            "R0140": p.bonds,
            "R0220": p.linked_assets,
            "R0270": recovery,
            "R0310": life.rec + health.rec,
            "R0320": health.rec,
            "R0330": life.rec,
            "R0340": linked.rec,
            "R0410": p.cash,
            "R0500": assets,
            "R0600": life.gross + health.gross,
            "R0610": health.gross,
            "R0620": health.whole,
            "R0630": health.bel,
            "R0640": health.rm,
            "R0650": life.gross,
            "R0660": life.whole,
            "R0670": life.bel,
            "R0680": life.rm,
            "R0690": linked.gross,
            "R0700": linked.whole,
            "R0710": linked.bel,
            "R0720": linked.rm,
            "R0840": p.payables,
            "R0850": debt,
            "R0870": debt,
            "R0900": liabilities,
            "R1000": assets - liabilities,
        },
    )
    return assets - liabilities


def _provisions(
    cells: Cells, p: Statement, life: Provision, linked: Provision, health: Provision
) -> None:
    # Whole and RM reside on the LoB total; BEL and recoverables on its option groups.
    parts = {
        "C0020": life,
        "C0030": linked,
        "C0040": Provision(0, p.linked_no_options, 3 * M, 0),
        "C0050": Provision(0, p.linked_with_options, M, 0),
        "C0150": life + linked,
        "C0160": health,
        "C0170": health,
        "C0210": health,
    }
    for table, row, col in _coordinates():
        if table != LIFE:
            continue
        item = parts.get(col, Provision(0, 0, 0, 0))
        # No default adjustment is seeded. Pre/post-default amounts therefore agree.
        amounts = {
            "R0010": item.whole,
            "R0020": 0,
            "R0030": item.bel,
            "R0040": item.rec,
            "R0050": item.rec,
            "R0060": 0,
            "R0070": 0,
            "R0080": item.rec,
            "R0090": item.bel - item.rec,
            "R0100": item.rm,
            "R0110": 0,
            "R0120": 0,
            "R0130": 0,
            "R0200": item.gross,
            "R0210": item.gross - item.rec,
        }
        if row in amounts:
            cells[table, row, col] = amounts[row]
    total = life.gross + linked.gross + health.gross
    for col in ("C0010", "C0020", "C0040"):
        cells[LTG, "R0010", col] = total
    for col in ("C0060", "C0080"):
        cells[LTG, "R0010", col] = total + p.va_impact
    for col in ("C0030", "C0050", "C0090"):
        cells[LTG, "R0010", col] = 0
    for col in ("C0070", "C0100"):
        cells[LTG, "R0010", col] = p.va_impact


def _flows(cells: Cells, p: Statement) -> None:
    # Recognition is on the accounting basis. These rows do not represent cash flows.
    direct = {
        "C0210": (60_000, p.health_claims),
        "C0220": (80_000, 60_000),
        "C0230": (p.linked_written, 40_000),
    }
    for row_gross, row_ceded, row_net, position in (
        ("R1410", "R1420", "R1500", 0),
        ("R1510", "R1520", "R1600", 0),
        ("R1610", "R1620", "R1700", 1),
    ):
        gross_total = ceded_total = 0
        for n in range(21, 29):
            col = f"C{n:03}0"
            gross = direct.get(col, (0, 0))[position]
            ceded = gross // 10
            gross_total += gross
            ceded_total += ceded
            _column(
                cells,
                FLOW,
                col,
                {
                    row_gross: gross,
                    row_ceded: ceded,
                    row_net: gross - ceded,
                },
            )
        _column(
            cells,
            FLOW,
            "C0300",
            {
                row_gross: gross_total,
                row_ceded: ceded_total,
                row_net: gross_total - ceded_total,
            },
        )


def _capital(cells: Cells, p: Statement, has_scr: bool, has_detail: bool) -> int:
    modules = {
        "R0010": p.market,
        "R0020": p.default,
        "R0030": p.life_risk,
        "R0040": p.health_risk,
        "R0050": 0,
        "R0060": p.diversification,
        "R0070": 0,
    }
    basic = sum(modules.values())
    scr = basic + p.operational + p.tax_relief
    if has_scr:
        for col in ("C0030", "C0040"):
            _column(cells, MODULE, col, {**modules, "R0100": basic})
        for row in ("R0010", "R0020", "R0030", "R0040", "R0050"):
            cells[MODULE, row, "C0050"] = 0
        _column(
            cells,
            SCR,
            "C0100",
            {
                "R0120": 0,
                "R0130": p.operational,
                "R0140": 0,
                "R0150": p.tax_relief,
                "R0160": 0,
                "R0200": scr,
                "R0210": 0,
                "R0220": scr,
            },
        )
    if has_detail:
        for table, row, col in _coordinates():
            if table == MARKET:
                cells[table, row, col] = (
                    p.market
                    if row
                    in {
                        "R0100",
                        "R0110",
                        "R0800",
                    }
                    else 0
                )
            elif table == UNDERWRITING:
                cells[table, row, col] = p.life_risk if row in {"R0200", "R0900"} else 0
        _column(
            cells,
            DEFAULT,
            "C0080",
            {
                "R0100": p.default,
                "R0300": 0,
                "R0330": 0,
                "R0400": p.default,
            },
        )
        cells[DEFAULT, "R0400", "C0070"] = p.default
    return scr


def _funds(cells: Cells, p: Statement, excess: int, scr: int) -> None:
    # Four liquidity/eligibility tiers in the order shown on S.23.01.
    tiers = ("C0020", "C0030", "C0040", "C0050")
    equity = 25 * M
    other_basic = equity + p.tax_asset
    reserve = excess - p.dividends - other_basic
    t1u = equity + reserve
    basic = (t1u, p.debt_restricted, p.debt_tier2, p.tax_asset)
    # The synthetic source reports a sole restricted instrument and capped tiers.
    # Tier 2 availability is observed in aggregate. There is no separate transfer cell.
    t1r = min(p.debt_restricted, (t1u - 1) // 4)
    t2 = p.available_tier2
    available = (t1u, t1r, t2, p.tax_asset)
    t3 = min(p.tax_asset, (3 * scr - 1) // 20)
    eligible = (t1u, t1r, t2, t3)
    eligible_mcr = (t1u, t1r, min(t2, p.mcr // 5), 0)
    _column(
        cells,
        RESERVE,
        "C0060",
        {
            "R0700": excess,
            "R0710": 0,
            "R0720": p.dividends,
            "R0730": other_basic,
            "R0740": 0,
            "R0760": reserve,
        },
    )
    for table, row, col in _coordinates():
        if table == FUNDS and row <= "R0400":
            cells[table, row, col] = 0
    items = {
        "R0010": (equity, 0, 0, 0),
        "R0130": (reserve, 0, 0, 0),
        "R0140": (0, p.debt_restricted, p.debt_tier2, 0),
        "R0160": (0, 0, 0, p.tax_asset),
        "R0290": basic,
        "R0500": available,
        "R0540": eligible,
        "R0510": (t1u, t1r, t2, 0),
        "R0550": eligible_mcr,
    }
    for row, amounts in items.items():
        cells[FUNDS, row, "C0010"] = sum(amounts)
        for col, quantity in zip(tiers, amounts, strict=True):
            if (FUNDS, row, col) in _coordinates():
                cells[FUNDS, row, col] = quantity
    cells[FUNDS, "R0580", "C0010"] = scr
    cells[FUNDS, "R0600", "C0010"] = p.mcr
    for row, amounts, denominator in (
        ("R0620", eligible, scr),
        ("R0640", eligible_mcr, p.mcr),
    ):
        ratio = Decimal(sum(amounts)) / denominator
        cells[FUNDS, row, "C0010"] = format(ratio, ".4f")


def period_cells(case: str, closing: bool) -> Cells:
    """Build financial facts for one annual solo supervisory period."""
    p = _statement(case, closing)
    life = Provision(p.life_whole, p.life_bel, p.life_rec, p.life_rm)
    linked = Provision(
        p.linked_whole,
        p.linked_no_options + p.linked_with_options,
        4 * M,
        p.linked_rm,
    )
    health = Provision(p.health_whole, p.health_bel, 3 * M, p.health_rm)
    cells: Cells = {}
    excess = _balance_sheet(cells, p, life, linked, health)
    _provisions(cells, p, life, linked, health)
    _flows(cells, p)
    scr = _capital(
        cells, p, has_scr=(case, closing) != ("3", True), has_detail=case == "1"
    )
    _funds(cells, p, excess, scr)
    unknown = cells.keys() - _coordinates()
    if unknown:
        raise ValueError(f"Unmapped or grey supervisory cell(s): {sorted(unknown)}")
    return cells
