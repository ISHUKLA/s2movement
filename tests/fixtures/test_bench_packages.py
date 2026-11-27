"""R-031–R-034: exercise the frozen workbooks, answer keys and one-change variants."""

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from bench_mutate import mutate
from openpyxl import load_workbook

PACKAGES = Path(__file__).resolve().parent / "packages"
CASES = ("1", "2a", "2b", "3", "4", "5")
BS, TP, OF, RR = "S.02.01.01.01", "S.12.01.01.01", "S.23.01.01.01", "S.23.01.01.02"
FLOW, SCR, MODULE = "S.05.01.01.02", "S.25.01.01.02", "S.25.01.01.01"
type Key = tuple[str, str, str]


@dataclass(frozen=True)
class Physical:
    cell: str
    value: str
    context_id: str | None
    coordinate_context: str | None


def read_sources(path: Path) -> tuple[dict[Key, Physical], dict[str, object]]:
    """Resolve the address from the headings physically above and beside each cell."""
    wb = load_workbook(path)
    try:
        result = {
            ("Metadata", str(row[0].value), "value"): Physical(
                row[1].coordinate, str(row[1].value), None, None
            )
            for row in wb["Metadata"].iter_rows(min_row=2)
        }
        lei = result["Metadata", "lei", "value"].value
        day = result["Metadata", "reference_date", "value"].value
        contexts: dict[str, object] = {}
        for ctx, entity, ref_date, dimensions in wb["Contexts"].values:
            if ctx == "context_id":
                continue
            assert entity == lei and ref_date == day and str(ctx) not in contexts
            contexts[str(ctx)] = json.loads(str(dimensions))
        for ws in wb.worksheets:
            if not ws.title.startswith("S."):
                continue
            table = ""
            context_id = coordinate_context = None
            cols: list[str] = []
            for row in ws:
                label = str(row[0].value)
                if label == "table":
                    table = str(row[1].value)
                    assert table.startswith(ws.title + ".")
                    context_id = coordinate_context = None
                    cols = []
                elif label == "context":
                    context_id = str(row[1].value)
                    assert context_id in contexts
                elif label == "coordinate_context":
                    coordinate_context = str(row[1].value)
                elif label == "row/column":
                    cols = [str(c.value) for c in row[1:]]
                elif label.startswith("R"):
                    for col, cell in zip(cols, row[1:], strict=True):
                        if cell.value is None:
                            continue
                        k = table, label, col
                        assert k not in result and context_id is not None
                        assert cell.data_type not in {"f", "e"}
                        result[k] = Physical(
                            cell.coordinate,
                            str(cell.value),
                            context_id,
                            coordinate_context,
                        )
        return result, contexts
    finally:
        wb.close()


def citations(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "source_sha256" in value and "cell" in value:
            yield value
        else:
            for child in value.values():
                yield from citations(child)
    elif isinstance(value, list):
        for child in value:
            yield from citations(child)


@pytest.mark.parametrize("case", CASES)
def test_r031_r033_frozen_references_and_period_arithmetic(case: str) -> None:
    directory = PACKAGES / case
    key = json.loads((directory / "expected.yaml").read_text())
    refs = list(citations(key))
    assert refs and key["case"] == case
    for period in ("opening", "closing"):
        path = directory / f"{period}.xlsx"
        values, contexts = read_sources(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        period_refs = [c for c in refs if c["period"] == period]
        assert period_refs
        for cite in period_refs:
            assert cite["file_id"] == path.name and cite["source_sha256"] == digest
            physical = values[cite["table"], cite["row"], cite["column"]]
            family = "Metadata" if cite["table"] == "Metadata" else cite["table"][:7]
            assert cite["sheet"] == cite["template"] == family
            assert cite["cell"] == physical.cell
            assert cite["context_id"] == physical.context_id
            assert cite["coordinate_context"] == physical.coordinate_context
            assert cite["dimensions"] == contexts.get(physical.context_id or "", {})
            assert str(cite["reported_value"]) == physical.value
        check_arithmetic(case, period, values)


def check_arithmetic(case: str, period: str, values: dict[Key, Physical]) -> None:
    lei = values["Metadata", "lei", "value"].value
    assert len(lei) == 20 and lei.isalnum()
    assert int("".join(str(int(x, 36)) for x in lei)) % 97 == 1
    scale = int(values["Metadata", "money_unit_scale", "value"].value)
    assert scale == (1000 if (case, period) == ("2a", "opening") else 1)

    def amount(t: str, r: str, c: str = "C0010") -> Decimal:
        return Decimal(values[t, r, c].value)

    # C0010 excludes goodwill and deferred acquisition costs (grey cells).
    assets = (
        "R0030 R0040 R0050 R0060 R0070 R0220 R0230 R0270 R0350 R0360 "
        "R0370 R0380 R0390 R0400 R0410 R0420"
    ).split()
    liabilities = (
        "R0510 R0600 R0690 R0740 R0750 R0760 R0770 R0780 R0790 "
        "R0800 R0810 R0820 R0830 R0840 R0850 R0880"
    ).split()
    assert amount(BS, "R0500") == sum(amount(BS, r) for r in assets)
    assert amount(BS, "R0900") == sum(amount(BS, r) for r in liabilities)
    assert amount(BS, "R0500") - amount(BS, "R0900") == amount(BS, "R1000")
    assert amount(BS, "R1000") == amount(RR, "R0700", "C0060")
    for r, col in (("R0610", "C0210"), ("R0650", "C0020"), ("R0690", "C0030")):
        assert amount(BS, r) == amount(TP, "R0200", col)
    # The above life-TP identities hold by construction for this synthetic
    # portfolio only. They do not promote a deactivated BV to an official check.
    assert amount(BS, "R0340") == sum(
        amount(TP, r, c)
        for r, c in (
            ("R0020", "C0030"),
            ("R0080", "C0040"),
            ("R0080", "C0050"),
            ("R0020", "C0120"),
            ("R0080", "C0120"),
        )
    )
    for r, c in (("R0320", "C0210"), ("R0330", "C0020")):
        assert amount(BS, r) == amount(TP, "R0020", c) + amount(TP, "R0080", c)
    for r in ("R0500", "R0540"):
        assert amount(OF, r) == sum(amount(OF, r, f"C00{n}0") for n in range(2, 6))
    assert amount(OF, "R0500") == (
        amount(BS, "R1000")
        - sum(amount(RR, r, "C0060") for r in ("R0710", "R0720", "R0740"))
        + amount(BS, "R0870")
        + amount(OF, "R0400")
    )
    tolerance = Decimal(values["Metadata", "ratio_precision", "value"].value)
    assert tolerance == Decimal("0.0001")
    assert (
        abs(amount(OF, "R0620") - amount(OF, "R0540") / amount(OF, "R0580"))
        <= tolerance
    )
    has_scr = (SCR, "R0220", "C0100") in values
    assert has_scr == ((case, period) != ("3", "closing"))
    assert values["S.01.01.01.01", "R0460", "C0010"].value == (
        "reported" if has_scr else "not reported"
    )
    if has_scr:
        assert amount(OF, "R0580") == amount(SCR, "R0220", "C0100")
        assert amount(OF, "R0580") == amount(MODULE, "R0100", "C0030") + sum(
            amount(SCR, r, "C0100")
            for r in ("R0120", "R0130", "R0140", "R0150", "R0160", "R0210")
        )
    for table, module, total, net in (
        ("S.26.01.01.02", "R0010", "R0800", "C0060"),
        ("S.26.02.01.01", "R0020", "R0400", "C0070"),
        ("S.26.03.01.04", "R0030", "R0900", "C0060"),
    ):
        assert ((table, total, net) in values) == (case == "1")
        if case == "1":
            assert amount(table, total, net) == amount(MODULE, module, "C0030")
            assert amount(table, total, "C0080") == amount(MODULE, module, "C0040")
    for gross, ceded, net in (
        ("R1410", "R1420", "R1500"),
        ("R1510", "R1520", "R1600"),
        ("R1610", "R1620", "R1700"),
    ):
        for col in [*(f"C{n:03}0" for n in range(21, 29)), "C0300"]:
            assert amount(FLOW, net, col) == amount(FLOW, gross, col) - amount(
                FLOW, ceded, col
            )


def test_r031_r034_scored_population_and_design_seeds() -> None:
    abstained: list[str] = []
    accounted: list[str] = []
    runs: list[str] = []
    identities: set[str] = set()
    for case in CASES:
        key = json.loads((PACKAGES / case / "expected.yaml").read_text())
        for run in key["runs"]:
            leis = {
                c["reported_value"]
                for c in run["gate"]["metadata"]
                if c["row"] == "lei"
            }
            assert len(leis) == 1
            identities.update(leis)
            runs.append(run["id"])
            abstained.extend(a["id"] for a in run["abstentions"])
            accounted.extend(a["id"] for a in run["accounted"])
            flags = {f["rule"] for f in run["flags"]}
            if run["id"] == "02a-stop":
                assert run["gate"]["status"] == "blocked" and not run["bridges"]
            elif case == "2a":
                assert run["gate"]["status"] == "pass"
                bridge = next(b for b in run["bridges"] if b["id"] == "excess")
                assert (
                    bridge["tolerance"] == "1000"
                    and bridge["residual_status"] == "pass"
                )
            elif case == "2b":
                assert run["gate"]["status"] == "warn"
                assert {"measure_status", "measure_impact", "tier_constraints"} <= flags
            elif case == "3":
                assert "closing_missing_S.25.01" in run["gate"]["warnings"]
            elif case == "4":
                assert {
                    "linked_divergence",
                    "premium_claim_scale",
                    "premium_claim_vs_bel",
                } <= flags and run["joint_questions"]
            elif case == "5":
                assert {"lac_dt_direction", "tier_constraints"} <= flags
                assert run["joint_questions"]
    assert len(set(runs)) == len(runs) == 7
    assert len(identities) == len(CASES)
    assert sorted(abstained) == [f"A{i:02}" for i in range(1, 21)]
    assert sorted(accounted) == [f"F{i:02}" for i in range(1, 5)]


@pytest.mark.parametrize(
    "change",
    [
        {"operation": "remove-template", "template": "S.25.01"},
        {
            "operation": "alter-cell",
            "table": BS,
            "row": "R1000",
            "column": "C0010",
            "value": 123456,
        },
        {"operation": "alter-metadata", "field": "currency", "value": "GBP"},
    ],
)
def test_r005_r007_r008_single_declared_mutation(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    package = PACKAGES / "1"
    dest = tmp_path / "derived"
    mutate(package, dest, dict(change, period="closing"))
    assert not (dest / "expected.yaml").exists()
    assert (package / "opening.xlsx").read_bytes() == (
        dest / "opening.xlsx"
    ).read_bytes()
    original, ctx1 = read_sources(package / "closing.xlsx")
    modified, ctx2 = read_sources(dest / "closing.xlsx")
    assert ctx1 == ctx2
    edited = {
        k
        for k in original.keys() | modified.keys()
        if original.get(k) != modified.get(k)
    }
    if change["operation"] == "remove-template":
        assert edited == {k for k in original if k[0].startswith("S.25.01.")}
    else:
        field = (
            (BS, "R1000", "C0010")
            if "row" in change
            else ("Metadata", "currency", "value")
        )
        assert edited == {field} and modified[field].value == str(change["value"])
    record = json.loads((dest / "mutation.json").read_text())
    assert (
        record["variant_sha256"]
        == hashlib.sha256((dest / "closing.xlsx").read_bytes()).hexdigest()
    )
