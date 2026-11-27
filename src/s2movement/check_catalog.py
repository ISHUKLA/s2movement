"""Read the versioned R-008 equations and source-backed context selectors."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
type Address = tuple[str, str, str]


@dataclass(frozen=True)
class CheckRule:
    id: str
    label: str
    left: list[str]
    right: list[str]
    tolerance: str
    withholds: list[str]
    message: str
    source: str
    right_operation: str = "sum"
    gap: str = ""
    public_gap: str = ""
    required_tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextSelector:
    dimensions: dict[str, str]
    coordinate: str | None


@dataclass(frozen=True)
class Catalog:
    tables: dict[str, list[str]]
    checks: tuple[CheckRule, ...]
    selectors: dict[Address, ContextSelector]

    def address(self, token: str, public: bool) -> Address:
        alias, row, column = token.lstrip("-").split()
        return self.tables[alias][int(public)], row, column


@cache
def catalog() -> Catalog:
    directory = ROOT / "mappings/2.8.2"
    data = json.loads((directory / "consistency.json").read_text(encoding="utf-8"))
    coordinates: dict[Address, str] = {}
    with (directory / "variant_equivalences.csv").open(encoding="utf-8") as stream:
        for record in csv.DictReader(stream):
            for prefix in ("public_", "supervisory_"):
                match = re.search(r"\bZ\d{4}\b", record[prefix + "coordinate_context"])
                if match:
                    coordinates[
                        record[prefix + "table"],
                        record[prefix + "row"],
                        record[prefix + "column"],
                    ] = match[0]
    selectors = {}
    with (directory / "cells.csv").open(encoding="utf-8") as stream:
        for record in csv.DictReader(stream):
            address = record["table"], record["row"], record["column"]
            dimensions = dict(
                re.findall(r"(s2c_\w+)\((s2c_\w+)\)", record["data_point_signature"])
            )
            coord = coordinates.get(address)
            if "starting with x0 (No)" in record["axis_context"]:
                dimensions["s2c_AO"] = "s2c_x0"
                coord = "Z0010"
            selectors[address] = ContextSelector(dimensions, coord)
    return Catalog(
        data["tables"], tuple(CheckRule(**item) for item in data["checks"]), selectors
    )
