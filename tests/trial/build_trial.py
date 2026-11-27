"""Build two fresh blinded trial cases from the independent fixture builder.

This module deliberately has no dependency on src/ or the product's outputs.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
sys.path.insert(0, str(FIXTURES))

import bench_cases as cases  # noqa: E402
import bench_workbooks as workbooks  # noqa: E402
from build_benchmark import with_inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
M = cases.M
DEFECT = 6 * M


def lei(stem: str) -> str:
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in stem)
    return f"{stem}{98 - int(digits + '00') % 97:02d}"


def statement(case: str, period: str) -> cases.Statement:
    base = cases.Statement()
    if case == "A":
        return replace(
            base,
            bonds=(523 if period == "opening" else 535) * M,
            linked_assets=(126 if period == "opening" else 131) * M,
            life_bel=(307 if period == "opening" else 312) * M,
            market=(84 if period == "opening" else 88) * M,
            va_impact=0 if period == "opening" else 5 * M,
        )
    return replace(
        base,
        bonds=(487 if period == "opening" else 496) * M,
        linked_assets=(117 if period == "opening" else 124) * M,
        life_bel=(292 if period == "opening" else 299) * M,
        market=(78 if period == "opening" else 82) * M,
        va_impact=0 if period == "opening" else 5 * M,
    )


def financial_cells(case: str, period: str) -> cases.Cells:
    p = statement(case, period)
    life = cases.Provision(p.life_whole, p.life_bel, p.life_rec, p.life_rm)
    linked = cases.Provision(
        p.linked_whole, p.linked_no_options + p.linked_with_options, 4 * M, p.linked_rm
    )
    health = cases.Provision(p.health_whole, p.health_bel, 3 * M, p.health_rm)
    cells: cases.Cells = {}
    excess = cases._balance_sheet(cells, p, life, linked, health)
    cases._provisions(cells, p, life, linked, health)
    cases._flows(cells, p)
    scr = cases._capital(cells, p, has_scr=True, has_detail=True)
    cases._funds(cells, p, excess, scr)
    # The only cross-template defect: S.25.01 final SCR differs from S.23.01.
    if (case, period) == ("A", "closing"):
        value = cells[cases.SCR, "R0220", "C0100"]
        assert isinstance(value, int)
        cells[cases.SCR, "R0220", "C0100"] = value + DEFECT
    if (case, period) == ("B", "opening"):
        value = cells[cases.SCR, "R0220", "C0100"]
        assert isinstance(value, int)
        cells[cases.SCR, "R0220", "C0100"] = value - DEFECT
    return cells


def header(case: str, period: str) -> dict[str, str]:
    head = workbooks.metadata("1", period).copy()
    head["lei"] = lei("999900TRIALCASEA00" if case == "A" else "999900TRIALCASEB00")
    head["undertaking_name"] = (
        "Marble Finch Life" if case == "A" else "Willow Beacon Life"
    )
    # Each case changes the reported VA basis between successive periods.
    head["va_applied"] = "yes" if period == "closing" else "no"
    return head


def build() -> None:
    for case in ("A", "B"):
        root = HERE / "materials" / case
        root.mkdir(parents=True, exist_ok=True)
        diff: dict[tuple[str, str, str], dict[str, int | str]] = {}
        metadata: dict[str, dict[str, str]] = {}
        for period in ("opening", "closing"):
            head = header(case, period)
            metadata[period] = head
            cells = with_inventory(financial_cells(case, period), head)
            for address, value in cells.items():
                diff.setdefault(address, {})[period] = value
            with patch.object(workbooks, "metadata", return_value=head):
                workbooks.write_period(root / f"{period}.xlsx", "1", period, cells)
        records = [
            {"template": t, "row": r, "column": c, **values}
            for (t, r, c), values in sorted(diff.items())
        ]
        intermediate = HERE / "build-data"
        intermediate.mkdir(exist_ok=True)
        (intermediate / f"{case}.json").write_text(
            json.dumps({"metadata": metadata, "cells": records}, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    build()
