"""Write the synthetic workbooks from the normalized layout and sourced mappings."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import xlsxwriter
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
MAPPING = HERE.parents[1] / "mappings" / "2.8.2"
type Key = tuple[str, str, str]
type Cells = dict[Key, int | str]
type Citations = dict[tuple[str, ...], dict[str, Any]]
RUNS = {
    "1": ["01-clean"],
    "2a": ["02a-stop", "02a-confirmed"],
    "2b": ["02b-warn"],
    "3": ["03-missing-scr-detail"],
    "4": ["04-linked"],
    "5": ["05-tax-cliff"],
}
NAMES = (
    "Tern Lantern Life",
    "Copper Orchard Life",
    "Amber Heron Life",
    "Juniper Glass Life",
    "Silver Estuary Life",
    "Cobalt Meadow Life",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(case: str, period: str) -> dict[str, str]:
    index = list(RUNS).index(case)
    stem = f"999900TESTFIXT{index + 1:04d}"
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in stem)
    lei = f"{stem}{98 - int(digits + '00') % 97:02d}"
    return {
        "format_version": "0.1",
        "reference_date": "2024-12-31" if period == "opening" else "2025-12-31",
        "variant": "supervisory",
        "taxonomy_version": "2.8.2",
        "taxonomy_variant": "base",
        "perimeter": "solo",
        "frequency": "annual",
        "lei": lei,
        "undertaking_name": NAMES[index],
        "currency": "EUR",
        "money_unit_scale": "1000" if (case, period) == ("2a", "opening") else "1",
        "money_precision": "1",
        "scr_method": "standard_formula",
        "rff_indicator": "no",
        "map_indicator": "no",
        "ma_applied": "no",
        "va_applied": "yes" if (case, period) == ("2b", "closing") else "no",
        "tmir_applied": "no",
        "tmtp_applied": "no",
        "ratio_precision": "0.0001",
    }


def load_mapping() -> tuple[dict[Key, dict[str, str]], dict[Key, str]]:
    with (MAPPING / "cells.csv").open() as stream:
        cells = {
            (r["table"], r["row"], r["column"]): r
            for r in csv.DictReader(stream)
            if r["supervisory_ars"] == "yes"
        }
    with (MAPPING / "variant_equivalences.csv").open() as stream:
        contexts = {}
        for record in csv.DictReader(stream):
            key = tuple(record["supervisory_" + k] for k in ("table", "row", "column"))
            z = re.search(r"Z\d{4}", record["supervisory_coordinate_context"])
            if z:
                contexts[(key[0], key[1], key[2])] = z[0]
    return cells, contexts


def write_period(path: Path, case: str, period: str, amounts: Cells) -> Citations:
    records, zcontexts = load_mapping()
    head = metadata(case, period)
    # Fix core properties and traversal order for byte-for-byte rebuilds.
    book = xlsxwriter.Workbook(str(path), {"strings_to_urls": False})
    book.set_properties({"created": datetime(2024, 1, 1)})
    meta = book.add_worksheet("Metadata")
    meta.write_row(0, 0, ["field", "value"])
    refs: Citations = {}
    common = {
        "period": period,
        "reference_date": head["reference_date"],
        "file_id": path.name,
    }
    for number, (field, header_value) in enumerate(head.items(), start=1):
        meta.write_row(number, 0, [field, header_value])
        refs[period, "Metadata", field, "value"] = {
            **common,
            "template": "Metadata",
            "table": "Metadata",
            "row": field,
            "column": "value",
            "sheet": "Metadata",
            "cell": f"B{number + 1}",
            "reported_value": header_value,
            "context_id": None,
            "dimensions": {},
            "coordinate_context": None,
        }
    contexts = book.add_worksheet("Contexts")
    contexts.write_row(
        0, 0, ["context_id", "entity_lei", "reference_date", "dimensions"]
    )
    blocks: dict[tuple[str, str, str], list[Key]] = defaultdict(list)
    for key in sorted(amounts):
        record = records[key]
        dims = dict(
            re.findall(r"(s2c_\w+)\((s2c_\w+)\)", record["data_point_signature"])
        )
        coord = zcontexts.get(key, "")
        if "starting with x0 (No)" in record["axis_context"]:
            coord = "Z0010"
            dims["s2c_AO"] = "s2c_x0"
        blocks[
            key[0], json.dumps(dims, sort_keys=True, separators=(",", ":")), coord
        ].append(key)
    ids = {s: f"ctx-{i}" for i, s in enumerate(sorted({d for _, d, _ in blocks}), 1)}
    for number, (serialized, ctx) in enumerate(ids.items(), 1):
        contexts.write_row(
            number, 0, [ctx, head["lei"], head["reference_date"], serialized]
        )
    sheets: dict[str, Any] = {}
    cursors: dict[str, int] = defaultdict(int)
    for (table, dimensions, coord), keys in sorted(blocks.items()):
        family = table[:7]
        if family not in sheets:
            sheets[family] = book.add_worksheet(family)
        sheet = sheets[family]
        pos = cursors[family]
        sheet.write_row(pos, 0, ["table", table])
        sheet.write_row(pos + 1, 0, ["context", ids[dimensions]])
        pos += 2
        if coord:
            sheet.write_row(pos, 0, ["coordinate_context", coord])
            pos += 1
        cols = sorted({k[2] for k in keys})
        rows = sorted({k[1] for k in keys})
        sheet.write_row(pos, 0, ["row/column", *cols])
        for i, row in enumerate(rows, 1):
            sheet.write_string(pos + i, 0, row)
        for key in keys:
            _, row, col = key
            y, x = pos + 1 + rows.index(row), 1 + cols.index(col)
            monetary = records[key]["monetary"] == "yes"
            val = amounts[key]
            if monetary:
                scale = int(head["money_unit_scale"])
                if not isinstance(val, int) or val % scale:
                    raise ValueError(
                        f"{key} is not representable in displayed whole units: {val}"
                    )
                val //= scale
            if isinstance(val, int):
                sheet.write_number(y, x, val)
            else:
                sheet.write_string(y, x, val)
            is_ratio = row in {"R0620", "R0640"} and table.startswith("S.23.01")
            refs[period, *key] = {
                **common,
                "template": family,
                "table": table,
                "row": row,
                "column": col,
                "context_id": ids[dimensions],
                "coordinate_context": coord or None,
                "dimensions": json.loads(dimensions),
                "sheet": family,
                "cell": f"{get_column_letter(x + 1)}{y + 1}",
                "reported_value": str(val),
                "currency": "EUR" if monetary else None,
                "unit_scale": head["money_unit_scale"] if monetary else "1",
                "precision": head["money_precision"]
                if monetary
                else (head["ratio_precision"] if is_ratio else None),
            }
            if is_ratio and Decimal(str(val)) <= 0:
                raise ValueError("seed has nonpositive coverage")
        cursors[family] = pos + len(rows) + 2
    book.close()
    digest = sha(path)
    for ref in refs.values():
        ref["source_sha256"] = digest
    return refs
