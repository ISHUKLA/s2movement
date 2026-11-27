"""Derive a single-declaration variant in a new directory outside the frozen inputs."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from bench_workbooks import HERE, sha
from openpyxl import load_workbook


def mutate(base: Path, out: Path, change: dict[str, Any]) -> None:
    """Keep broken dependencies observable. Never copy an answer key to a variant."""
    period = change["period"]
    if period not in ("opening", "closing"):
        raise ValueError("period must be opening or closing")
    base, out = base.resolve(), out.resolve()
    if (
        out.exists()
        or out.is_relative_to(base)
        or out.is_relative_to(HERE / "packages")
    ):
        raise ValueError("choose a new directory outside the base and frozen packages")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        staged = Path(temp) / "variant"
        staged.mkdir()
        hashes = {}
        for filename in ("opening.xlsx", "closing.xlsx", "confirmations.json"):
            if filename == "confirmations.json" and not (base / filename).exists():
                continue
            hashes[filename] = sha(base / filename)
            shutil.copyfile(base / filename, staged / filename)
        path = staged / f"{period}.xlsx"
        wb = load_workbook(path)
        try:
            op = change["operation"]
            location: str
            old: Any
            new = change.get("value")
            if op == "remove-template":
                sheet = change["template"]
                if sheet in ("Metadata", "Contexts"):
                    raise ValueError("select a template family")
                del wb[sheet]
                location, old, new = sheet, "present", "absent"
            elif op == "alter-metadata":
                ws = wb["Metadata"]
                targets = [r[1] for r in ws if r[0].value == change["field"]]
                if len(targets) != 1:
                    raise ValueError("expected one metadata declaration")
                cell = targets[0]
                location, old = f"Metadata!{cell.coordinate}", cell.value
                cell.value = new
            elif op == "alter-cell":
                table = change["table"]
                ws = wb[table[:7]]
                matches = []
                block = ctx = coord = None
                col_index = None
                for r in ws.iter_rows():
                    label = r[0].value
                    if label == "table":
                        block, ctx, coord, col_index = r[1].value, None, None, None
                    elif label == "context":
                        ctx = r[1].value
                    elif label == "coordinate_context":
                        coord = r[1].value
                    elif label == "row/column":
                        col_index = next(
                            (i for i, c in enumerate(r) if c.value == change["column"]),
                            None,
                        )
                    elif (
                        block == table
                        and label == change["row"]
                        and col_index is not None
                        and change.get("context_id", ctx) == ctx
                        and change.get("coordinate_context", coord) == coord
                        and r[col_index].value is not None
                    ):
                        matches.append(r[col_index])
                if len(matches) != 1:
                    raise ValueError(
                        "expected one populated cell; specify the full context"
                    )
                cell = matches[0]
                location, old = f"{ws.title}!{cell.coordinate}", cell.value
                cell.value = new
            else:
                raise ValueError(f"unknown mutation {op}")
            if old == new or ("old" in change and change["old"] != old):
                raise ValueError(
                    "mutation made no change or the original value differs"
                )
            wb.save(path)
        finally:
            wb.close()
        record = {
            "base_sha256": hashes,
            "change": change,
            "location": location,
            "old": old,
            "new": new,
            "variant_sha256": sha(path),
        }
        (staged / "mutation.json").write_text(json.dumps(record, indent=2) + "\n")
        staged.rename(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("declaration", type=Path, help="single JSON mutation object")
    args = parser.parse_args()
    mutate(args.base, args.out, json.loads(args.declaration.read_text()))
