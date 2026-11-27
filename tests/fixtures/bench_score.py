"""Score the seven black-box CLI runs against the independent R-032/R-033 keys."""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from bench_integrity import verify
from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.formula.tokenizer import Tokenizer
from openpyxl.workbook import Workbook

type Obj = dict[str, Any]
HERE = Path(__file__).resolve().parent
CASES = ("1", "2a", "2b", "3", "4", "5")
LO = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


def number(x: object) -> Fraction | None:
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        return None
    try:
        return Fraction(str(x))
    except (ValueError, ZeroDivisionError):
        return None


def objects(value: object) -> list[Obj]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def normalized(x: object) -> str:
    return str(x or "").strip().lower().replace(" ", "_").replace("-", "_")


def unit_name(unit: object) -> str:
    if isinstance(unit, dict):
        if unit.get("kind") == "money" and number(unit.get("scale")) == 1:
            return str(unit.get("currency"))
        unit = unit.get("kind")
    return {"percentage_points": "pp", "ratio_units": "ratio"}.get(str(unit), str(unit))


SLICE_EXCESS = "s02_excess_assets_over_liabilities"
SLICE_LINES = {
    "opening_excess": "opening",
    "closing_excess": "closing",
    "investments_movement": "investments",
    "linked_assets_movement": "linked_assets",
}
SLICE_COMPARISONS = {
    f"{p}_excess_consistency": f"{p}_excess" for p in ("opening", "closing")
}


def indexed(items: object, aliases: Mapping[str, str] | None = None) -> dict[str, Obj]:
    # Duplicate IDs cannot earn credit by replacing another item with the same ID.
    result: dict[str, Obj] = {}
    for item in objects(items):
        key = str(item.get("id", ""))
        key = (aliases or {}).get(key, key)
        result[key] = {} if key in result else item
    return result


@dataclass
class Score:
    matched: Counter[str] = field(default_factory=Counter)
    expected: Counter[str] = field(default_factory=Counter)
    issues: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    false_abstentions: list[str] = field(default_factory=list)
    open_dependencies: list[str] = field(default_factory=list)

    def measure(self, metric: str, ok: bool) -> None:
        self.expected[metric] += 1
        self.matched[metric] += int(ok)

    def report(self) -> Obj:
        names = (
            "bridges_tied",
            "numeric_values",
            "citations",
            "gates",
            "stops",
            "unavailable",
            "withheld",
            "comparisons",
            "tier_limits",
            "flags",
        )
        return {
            "metrics": {
                k: {
                    "validated": self.matched[k],
                    "expected": self.expected[k],
                    "rate": self.matched[k] / self.expected[k]
                    if self.expected[k]
                    else "not applicable",
                }
                for k in names
            },
            "sign_inversions": len(self.issues.get("sign_inversions", [])),
            "findings": dict(self.issues),
            "false_abstentions": {
                "count": len(self.false_abstentions),
                "ids": self.false_abstentions,
            },
            "R-034": "not yet measured",
            "open_benchmark_dependencies": self.open_dependencies,
            "deterministic_gates_pass": not any(self.issues.values())
            and not self.open_dependencies
            and self.expected["bridges_tied"] > 0
            and self.expected["citations"] > 0
            and all(self.matched[k] == n for k, n in self.expected.items()),
        }


def norm_dimensions(value: object) -> object:
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def get_hash(cite: Obj) -> object:
    return cite.get("source_sha256", cite.get("sha256"))


class Sources:
    """Index populated physical template intersections in their declared blocks."""

    def __init__(self, package: Path) -> None:
        self.cells: dict[tuple[str, str, str], Obj] = {}
        self.package = package
        self.confirmation: Obj | None = None
        for period in ("opening", "closing"):
            path = package / f"{period}.xlsx"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            book = load_workbook(path)
            meta = {str(row[0].value): row[1].value for row in book["Metadata"].rows}
            contexts = {
                str(row[0]): norm_dimensions(row[3])
                for row in list(book["Contexts"].values)[1:]
            }
            for sheet in book:
                table = context = coord = ""
                columns: tuple[Any, ...] = ()
                for row in sheet.iter_rows():
                    key = str(row[0].value or "")
                    if sheet.title == "Metadata" and len(row) >= 2:
                        self.cells[period, sheet.title, row[1].coordinate] = {
                            "file_id": path.name,
                            "hash": digest,
                            "reference_date": str(meta.get("reference_date")),
                            "row": key,
                            "column": "value",
                            "value": row[1].value,
                            "template": "Metadata",
                        }
                    elif key == "table":
                        table, context, coord, columns = str(row[1].value), "", "", ()
                    elif key == "context":
                        context = str(row[1].value)
                    elif key == "coordinate_context":
                        coord = str(row[1].value)
                    elif key == "row/column":
                        columns = tuple(c.value for c in row)
                    elif key.startswith("R") and columns:
                        for cell in row[1:]:
                            if cell.value is not None:
                                col = columns[cell.column - 1]
                                self.cells[period, sheet.title, cell.coordinate] = {
                                    "file_id": path.name,
                                    "hash": digest,
                                    "reference_date": str(meta.get("reference_date")),
                                    "row": key,
                                    "column": col,
                                    "template": sheet.title,
                                    "table": table,
                                    "context_id": context,
                                    "coordinate_context": coord,
                                    "dimensions": contexts[context],
                                    "value": cell.value,
                                    "currency": meta.get("currency"),
                                    "unit_scale": meta.get("money_unit_scale"),
                                }
            book.close()

    def valid(self, exp: Obj, act: Obj) -> bool:
        loc = ("period", "sheet", "cell")
        if any(exp.get(k) != act.get(k) for k in loc):
            return False
        raw = self.cells.get((exp["period"], exp["sheet"], exp["cell"]))
        if raw is None:
            return False
        if exp["sheet"] == "Metadata" and "metadata_field" in act:
            act = {
                **act,
                "row": act["metadata_field"],
                "column": "value",
                "template": "Metadata",
            }
        keys = ["row", "column", "template", "file_id"]
        if exp["sheet"] != "Metadata":
            keys.extend(("table", "context_id"))
            for c in (exp, act):
                if norm_dimensions(c.get("dimensions")) != raw["dimensions"]:
                    return False
                if (c.get("coordinate_context") or "") != raw["coordinate_context"]:
                    return False
        for c in (exp, act):
            if any(c.get(k) != raw[k] for k in keys) or get_hash(c) != raw["hash"]:
                return False
            if "reference_date" in c and c["reference_date"] != raw["reference_date"]:
                return False
            for k in ("currency", "unit_scale", "precision"):
                if k in c and k in exp and str(c[k]) != str(exp[k]):
                    return False
            if "reported_value" in c:
                value = c["reported_value"]
                if str(value) != str(raw["value"]) and (
                    number(value) is None or number(value) != number(raw["value"])
                ):
                    return False
        return True


def excel_equal(cell: object, wanted: Fraction, unit: str) -> bool:
    if isinstance(cell, bool) or not isinstance(cell, (int, float)):
        return False
    if unit == "EUR" or wanted == 0:
        return number(cell) == wanted
    # Spreadsheet doubles carry at most 15 significant decimal digits.
    return math.isclose(cell, float(wanted), rel_tol=1e-14, abs_tol=0)


@dataclass
class Excel:
    formulas: Workbook
    values: Workbook

    def locate(
        self, owner: str, item: str, field_name: str, explicit: object, section: str
    ) -> Cell | None:
        if isinstance(explicit, Mapping):
            sheet, pos = explicit.get("sheet"), explicit.get("cell")
            if (
                isinstance(sheet, str)
                and sheet in self.formulas.sheetnames
                and isinstance(pos, str)
            ):
                if re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]*", pos):
                    located = self.formulas[sheet][pos]
                    return located if isinstance(located, Cell) else None
        candidates = []
        for ws in self.formulas:
            if ws.title.startswith("Raw_") or (
                section == "comparison" and ws.title != "Summary"
            ):
                continue
            if section == "bridge" and ws.title == "Summary":
                continue
            headers: dict[int, str] = {}
            for row in ws.iter_rows():
                vals = [str(c.value or "") for c in row]
                if any(
                    normalized(v) in {"line_id", "comparison_id", "id", "bridge_id"}
                    for v in vals
                ):
                    headers = {i: normalized(v) for i, v in enumerate(vals)}
                if item not in vals and f"{owner}.{item}" not in vals:
                    continue
                aliases = {field_name}
                if field_name == "value":
                    aliases.update(("result", "amount", "calculated_value"))
                if field_name == "left":
                    aliases.add("s.02.01_reported")
                if field_name == "right":
                    aliases.add("s.23.01_reported")
                for i, col in headers.items():
                    if col in aliases:
                        candidates.append(
                            (normalized(owner) in normalized(ws.title), row[i])
                        )
        preferred = [c for match, c in candidates if match]
        choices = preferred or [c for _, c in candidates]
        return (
            choices[0] if len(choices) == 1 and isinstance(choices[0], Cell) else None
        )

    def cached(self, cell: Cell) -> object:
        return self.values[cell.parent.title][cell.coordinate].value

    def traces_sources(
        self, cell: Cell, citations: list[Obj], sources: Sources
    ) -> bool:
        """Follow formula operands to the reported values in the raw ledger."""
        wanted = {(c["period"], c["sheet"], c["cell"]) for c in citations}
        found: set[tuple[str, str, str]] = set()
        todo = [cell]
        seen = set()
        while todo:
            current = todo.pop()
            ws = self.formulas[current.parent.title]
            key = ws.title, current.coordinate
            if key in seen:
                continue
            seen.add(key)
            if current.data_type != "f":
                if ws.title.startswith("Raw_"):
                    headers = {
                        normalized(c.value): c.column
                        for c in ws[1]
                        if isinstance(c, Cell)
                    }

                    value_columns = {
                        headers[k]
                        for k in (
                            "reported",
                            "reported_value",
                            "original",
                            "original_value",
                            "original_reported_value",
                        )
                        if k in headers
                    }
                    if current.column not in value_columns:
                        continue
                    period = ws.title.removeprefix("Raw_")
                    row_fields = {
                        h: ws.cell(current.row, col).value for h, col in headers.items()
                    }
                    sheet = str(
                        next(
                            (
                                row_fields[h]
                                for h in ("sheet", "source_sheet", "input_sheet")
                                if h in row_fields
                            ),
                            None,
                        )
                    )
                    addr = str(
                        next(
                            (
                                row_fields[h]
                                for h in ("cell", "source_cell", "input_cell")
                                if h in row_fields
                            ),
                            None,
                        )
                    )
                    physical = sources.cells.get((period, sheet, addr))
                    if physical and (
                        str(current.value) == str(physical["value"])
                        or number(current.value) is not None
                        and number(current.value) == number(physical["value"])
                    ):
                        found.add((period, sheet, addr))
                continue
            for token in Tokenizer(str(current.value)).items:
                if token.subtype != "RANGE":
                    continue
                sheet, bang, address = token.value.rpartition("!")
                title = sheet.strip("'").replace("''", "'") if bang else key[0]
                addr = address.replace("$", "")
                if title not in self.formulas.sheetnames or not re.fullmatch(
                    r"[A-Z]{1,3}[1-9][0-9]*(?::[A-Z]{1,3}[1-9][0-9]*)?", addr
                ):
                    continue
                target = self.formulas[title]
                if ":" in addr:
                    todo.extend(
                        c for row in target[addr] for c in row if isinstance(c, Cell)
                    )
                else:
                    todo.append(target[addr])
        return bool(wanted) and wanted <= found


def recalculate(path: Path, tmp: Path, executable: str) -> Excel:
    dest = tmp / "recalculated"
    dest.mkdir()
    proc = subprocess.run(
        [
            executable,
            f"-env:UserInstallation={(tmp / 'lo_profile').as_uri()}",
            "--headless",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(dest),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    target = dest / path.name
    if proc.returncode or not target.is_file():
        raise ValueError(f"LibreOffice recalculation failed: {proc.stderr.strip()}")
    return Excel(load_workbook(path), load_workbook(target, data_only=True))


def check_citations(
    score: Score, sources: Sources, expected: object, actual: object, label: str
) -> bool:
    remaining = objects(actual).copy()
    wanted = objects(expected)
    ok = bool(wanted)
    for exp in wanted:
        index = next(
            (i for i, c in enumerate(remaining) if sources.valid(exp, c)), None
        )
        score.measure("citations", index is not None)
        if index is None:
            ok = False
        else:
            remaining.pop(index)
    # A converted financial value also depends on the frozen reviewer decision.
    # Precision operands for mixed-unit tolerances use the same factor.
    decision = sources.confirmation
    opening_money = any(
        c.get("period") == "opening"
        and c.get("currency") == "EUR"
        and str(c.get("unit_scale")) == "1000"
        for c in wanted
    )
    opening_precision = label.endswith("/tolerance") and any(
        c.get("period") == "opening" and c.get("row") == "money_unit_scale"
        for c in wanted
    )
    if decision is not None and (opening_money or opening_precision):
        pointer = next(
            (
                i
                for i, c in enumerate(remaining)
                if c.get("file_id") == decision["file"]
                and get_hash(c) == decision["sha256"]
                and c.get("period") == "opening"
                and c.get("sheet") == "JSON"
                and c.get("cell") == "/confirmations/0"
            ),
            None,
        )
        score.measure("citations", pointer is not None)
        if pointer is None:
            ok = False
        else:
            remaining.pop(pointer)
    if remaining or not ok:
        score.issues["citation_errors"].append(label)
    return ok and not remaining


def structural_ids(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        str(x.get("id", x.get("movement_id", ""))) if isinstance(x, dict) else str(x)
        for x in value
    }


def tagged_ids(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        if (
            "abstention" in {normalized(value.get(k)) for k in ("status", "tag")}
            or value.get("abstain") is True
            or value.get("abstention") is True
        ):
            yield str(value.get("movement_id", value.get("id", "")))
        for k, v in value.items():
            if k in ("abstentions", "abstention_ids"):
                yield from structural_ids(v)
            else:
                yield from tagged_ids(v)
    elif isinstance(value, list):
        for element in value:
            yield from tagged_ids(element)


def status_matches(exp: Obj, act: Obj) -> bool:
    expected = normalized(exp.get("status"))
    if normalized(act.get("status")) != expected:
        return False
    if expected in ("unavailable", "withheld", "indeterminate"):
        if act.get("value") is not None:
            return False
        for k in ("period", "missing_template", "dependency"):
            if k in exp and act.get(k) != exp[k]:
                return False
    return True


def resolved_value(node: Obj) -> Obj:
    result = node.get("result", node)
    return result if isinstance(result, dict) else {}


def scan_extra(score: Score, actual: object, accounted: set[int], prefix: str) -> None:
    if isinstance(actual, dict):
        if number(actual.get("value")) is not None and id(actual) not in accounted:
            score.issues["unsupported_numbers"].append(prefix)
        for key, val in actual.items():
            scan_extra(score, val, accounted, f"{prefix}/{key}")
    elif isinstance(actual, list):
        for i, val in enumerate(actual):
            scan_extra(score, val, accounted, f"{prefix}/{i}")


@dataclass
class Audit:
    score: Score
    sources: Sources
    excel: Excel | None
    run: str
    accounted: set[int] = field(default_factory=set)

    def amount(self, label: str, exp: Obj, act: Obj, cell: Cell | None) -> bool:
        wanted, observed = number(exp.get("value")), number(act.get("value"))
        unit = unit_name(exp.get("unit"))
        sign_error = (
            observed is not None and wanted is not None and observed * wanted < 0
        )
        if sign_error:
            self.score.issues["sign_inversions"].append(label)
        valid = (
            wanted is not None
            and observed == wanted
            and act.get("status") == "value"
            and unit_name(act.get("unit")) == unit
        )
        citations = check_citations(
            self.score, self.sources, exp.get("citations"), act.get("citations"), label
        )
        wb = self.excel
        both_views = (
            wb is not None
            and cell is not None
            and wanted is not None
            and cell.data_type == "f"
            and wb.traces_sources(cell, objects(exp.get("citations")), self.sources)
            and excel_equal(wb.cached(cell), wanted, unit)
        )
        self.accounted.add(id(act))
        ok = valid and both_views and citations
        self.score.measure("numeric_values", ok)
        if not ok:
            self.score.issues["wrong_or_missing_values"].append(label)
        return ok and citations

    def cell(
        self, owner: str, item: str, field_name: str, node: Obj, section: str
    ) -> Cell | None:
        if self.excel is None:
            return None
        return self.excel.locate(owner, item, field_name, node.get("excel"), section)

    def tolerance(self, label: str, exp: Obj, actual: Obj, cell: Cell | None) -> bool:
        val = number(exp["value"])
        ok = val is not None and val == number(actual.get("value"))
        ok = ok and unit_name(exp.get("unit")) == unit_name(actual.get("unit"))
        if exp.get("citations"):
            cites_ok = check_citations(
                self.score,
                self.sources,
                exp["citations"],
                actual.get("citations"),
                label,
            )
            ok = ok and cites_ok
        else:
            ok = (
                ok
                and exp.get("unit") == "pp"
                and val == 0
                and bool(actual.get("source") or actual.get("policy"))
            )
        ok = ok and self.excel is not None and cell is not None and val is not None
        if self.excel is not None and cell is not None and val is not None:
            ok = ok and excel_equal(
                self.excel.cached(cell), val, unit_name(exp.get("unit"))
            )
        self.accounted.add(id(actual))
        self.score.measure("numeric_values", ok)
        if not ok:
            self.score.issues["wrong_or_missing_values"].append(label)
        return ok

    def bridge(self, exp: Obj, actual: Obj) -> None:
        key = exp["id"]
        label = f"{self.run}/{key}"
        lines = indexed(actual.get("lines"), SLICE_LINES if key == "excess" else None)
        key_lines = exp["lines"]
        roles: dict[str, list[Fraction]] = defaultdict(list)
        validate = True
        if not actual:
            category = (
                "omitted_bridges"
                if exp.get("residual_status") in {"pass", "fail"}
                else "omitted_partial_bridges"
            )
            self.score.issues[category].append(label)
        for line in key_lines:
            lid = line["id"]
            ref = f"{label}/{lid}"
            act = resolved_value(lines.get(lid, {}))
            if lid not in lines:
                self.score.issues["omitted_lines"].append(ref)
            public_id = lines.get(lid, {}).get("id", lid)
            cell = self.cell(key, public_id, "value", act, "bridge")
            status = normalized(line.get("status"))
            if status == "value":
                if not self.amount(ref, line, act, cell):
                    validate = False
                n = number(act.get("value"))
                if n is not None:
                    roles[line["role"]].append(n)
            else:
                ok = status_matches(line, act)
                if self.excel and cell:
                    display = str(self.excel.cached(cell)).lower()
                    ok = ok and display.startswith(status)
                    if line.get("missing_template"):
                        ok = ok and line["missing_template"].lower() in display
                else:
                    ok = False
                if status in ("unavailable", "withheld"):
                    self.score.measure(status, ok)
                if not ok:
                    self.score.issues["incorrect_line_status"].append(ref)
                    validate = False
        for lid in sorted(set(lines) - {ln["id"] for ln in key_lines}):
            self.score.issues["unexpected_lines"].append(f"{label}/{lid}")
        check = actual.get("residual_check", {})
        residual_status = exp.get("residual_status")
        if residual_status in ("pass", "fail"):
            tol = number(exp.get("tolerance"))
            o, r, c = (roles[k] for k in ("opening", "residual", "closing"))
            tied = False
            if len(o) == len(r) == len(c) == 1 and tol is not None:
                tied = c[0] - o[0] - sum(roles["movement"]) == r[0] and abs(r[0]) <= tol
                if exp.get("unit") == "pp":
                    tied = tied and r[0] == 0
            if not isinstance(check, dict):
                check = {}
            discrepancy = resolved_value(check.get("signed_discrepancy", {}))
            tolerance = resolved_value(check.get("tolerance", {}))
            residual_line: Obj = next(
                (ln for ln in key_lines if ln["role"] == "residual"), {}
            )
            if discrepancy and residual_line:
                self.accounted.add(id(discrepancy))
                validate = validate and number(discrepancy.get("value")) == number(
                    residual_line["value"]
                )
                if not check_citations(
                    self.score,
                    self.sources,
                    residual_line["citations"],
                    discrepancy.get("citations"),
                    f"{label}/signed_discrepancy",
                ):
                    validate = False
            else:
                if residual_line:
                    check_citations(
                        self.score,
                        self.sources,
                        residual_line["citations"],
                        [],
                        f"{label}/signed_discrepancy",
                    )
                validate = False
            self.accounted.add(id(tolerance))
            if "tolerance_evidence" in exp:
                cell = self.cell(
                    key, str(actual.get("id", key)), "tolerance", tolerance, "bridge"
                )
                if (
                    not cell
                    and key == "excess"
                    and self.excel
                    and "Bridge" in self.excel.formulas
                ):
                    ws = self.excel.formulas["Bridge"]
                    if normalized(ws["A2"].value) == "bridge_tolerance":
                        cell = ws["B2"]
                if not self.tolerance(
                    f"{label}/tolerance", exp["tolerance_evidence"], tolerance, cell
                ):
                    validate = False
            validate = validate and check.get("status") == residual_status
            validate = (
                validate and tol is not None and number(tolerance.get("value")) == tol
            )
            self.score.measure("bridges_tied", validate and tied)
            if not (validate and tied):
                self.score.issues["failed_bridges"].append(label)
        elif actual and normalized(check.get("status")) != normalized(residual_status):
            self.score.issues["incorrect_bridge_status"].append(label)

    def comparison(self, exp: Obj, act: Obj) -> None:
        key = exp["id"]
        ref = f"{self.run}/{key}"
        ok = status_matches(exp, act)
        for name in ("left", "right", "signed_discrepancy", "tolerance"):
            obj = exp.get(name)
            observed = act.get(name, {})
            if not isinstance(observed, dict):
                observed = {}
            if isinstance(obj, dict) and obj.get("value") is not None:
                cell = self.cell(
                    "Summary", str(act.get("id", key)), name, observed, "comparison"
                )
                if not self.amount(f"{ref}/{name}", obj, observed, cell):
                    ok = False
            elif name == "tolerance" and exp.get("tolerance_evidence"):
                cell = self.cell(
                    "Summary", str(act.get("id", key)), name, observed, "comparison"
                )
                if not self.tolerance(
                    f"{ref}/tolerance", exp["tolerance_evidence"], observed, cell
                ):
                    ok = False
            elif name == "tolerance" and number(obj) is not None:
                self.accounted.add(id(observed))
                ok = ok and number(observed.get("value")) == number(obj)
        if exp.get("status") in ("unavailable", "withheld"):
            self.score.measure(exp["status"], ok)
        self.score.measure("comparisons", ok)
        if not ok:
            self.score.issues["incorrect_comparisons"].append(ref)
        if exp.get("benchmark_dependency_open"):
            self.score.open_dependencies.append(ref)


def score_run(
    score: Score, sources: Sources, key: Obj, out: Obj, excel: Excel | None
) -> None:
    rid = key["id"]
    sources.confirmation = None
    if key["gate"].get("rerun_after_confirmed_conversion"):
        declaration = key["gate"].get("confirmation", {})
        path = sources.package / "confirmations.json"
        if (
            declaration.get("file") == path.name
            and path.is_file()
            and (
                hashlib.sha256(path.read_bytes()).hexdigest()
                == declaration.get("sha256")
            )
        ):
            sources.confirmation = declaration
    audit = Audit(score, sources, excel, rid)
    gate = out.get("gate", {})
    gate_status = normalized(gate.get("status"))
    expected_gate = normalized(key["gate"]["status"])
    ok = gate_status == expected_gate
    if expected_gate == "warn" and gate_status == "pass":
        ok = bool(out.get("warnings"))
    warnings = structural_ids(out.get("warnings")) | structural_ids(
        gate.get("warnings")
    )
    if key["gate"].get("warnings"):
        ok = ok and set(key["gate"]["warnings"]) == warnings
    if expected_gate == "pass" and warnings:
        ok = False
    if key["gate"].get("rerun_after_confirmed_conversion"):
        records = objects(gate.get("conversions")) or objects(out.get("conversions"))
        ok = ok and any(
            c.get("period") == "opening"
            and number(c.get("factor")) == 1000
            and number(c.get("target_unit_scale")) == 1
            and c.get("reason")
            and c.get("evidence")
            for c in records
        )
    if expected_gate == "blocked":
        reasons = structural_ids(gate.get("stops")) | structural_ids(out.get("stops"))
        reasons.update(
            str(c["id"])
            for c in objects(gate.get("checks"))
            if normalized(c.get("status")) in {"blocked", "hard_stop", "fail"}
            and "id" in c
        )
        if "compatible_scale" in reasons:
            reasons.remove("compatible_scale")
            reasons.add("unit_scale_mismatch")
        ok = ok and set(key["gate"].get("stops", [])) == reasons
        leaked = any(
            number(resolved_value(line).get("value")) is not None
            for b in objects(out.get("bridges"))
            for line in objects(b.get("lines"))
            if line.get("id")
            not in ("opening", "closing", "opening_excess", "closing_excess")
        )
        ok = ok and not leaked
        score.measure("stops", ok)
    score.measure("gates", ok)
    if not ok:
        score.issues["incorrect_gate"].append(rid)
    meta = {(m.get("period"), m.get("name")): m for m in objects(out.get("metadata"))}
    for cite in objects(key["gate"].get("metadata")):
        ref = f"{rid}/Metadata/{cite['period']}/{cite['row']}"
        observed = meta.get((cite["period"], cite["row"]), {})
        check_citations(score, sources, [cite], observed.get("citations"), ref)
        if str(observed.get("reported_value")) != str(cite["reported_value"]):
            score.issues["incorrect_metadata"].append(ref)
    actual = indexed(out.get("bridges"), {SLICE_EXCESS: "excess"})
    if expected_gate != "blocked":
        for extra in sorted(set(actual) - structural_ids(key.get("bridges"))):
            score.issues["unexpected_bridges"].append(f"{rid}/{extra}")
    for b in objects(key.get("bridges")):
        audit.bridge(b, actual.get(b["id"], {}))
    actual = indexed(out.get("comparisons"), SLICE_COMPARISONS)
    for c in objects(key.get("comparisons")):
        audit.comparison(c, actual.get(c["id"], {}))
    for section in ("tier_limits", "tier_changes", "schedules", "flags"):
        expected_records = objects(key.get(section))
        actual_records = indexed(out.get(section))
        for rec in expected_records:
            ident = rec["id"]
            ref = f"{rid}/{section}/{ident}"
            item = actual_records.get(ident, {})
            if section == "tier_limits":
                ok = status_matches(rec, item) and all(
                    item.get(k) == rec.get(k)
                    for k in (
                        "operator",
                        "rule_source",
                        "reported_amounts_comply",
                        "compliance_with_rounding",
                    )
                )
                score.measure("tier_limits", ok)
                if not ok:
                    score.issues["incorrect_tier_limits"].append(ref)
            if rec.get("benchmark_dependency_open"):
                score.open_dependencies.append(ref)
            amounts = {
                k: v
                for k, v in rec.items()
                if isinstance(v, dict) and "value" in v and "unit" in v
            }
            if section == "flags":
                for k in (
                    "signed_statistic",
                    "size_factor",
                    "pre_tax_scr_change",
                    "threshold",
                ):
                    if number(rec.get(k)) is not None:
                        unit = (
                            "factor"
                            if k == "size_factor"
                            or (
                                k == "threshold"
                                and rec.get("rule") == "premium_claim_scale"
                            )
                            else rec["unit"]
                        )
                        amounts[k] = {
                            "value": rec[k],
                            "unit": unit,
                            "citations": rec.get("citations", []),
                        }
            for k, exp_amount in amounts.items():
                node = item.get(k)
                observed = resolved_value(node) if isinstance(node, dict) else {}
                cell = audit.cell(section, ident, k, observed, section)
                audit.amount(f"{ref}/{k}", exp_amount, observed, cell)
        if section == "flags":
            expected_flags = structural_ids(expected_records)
            actual_flags = set(actual_records)
            matches = expected_flags == actual_flags and bool(out)
            score.measure("flags", matches)
            if not matches:
                score.issues["incorrect_flags"].append(
                    f"{rid}: missing {sorted(expected_flags - actual_flags)}, "
                    f"unexpected {sorted(actual_flags - expected_flags)}"
                )
    for section in ("withheld", "unsupported_splits"):
        observed_items = indexed(out.get(section))
        for expected_item in objects(key.get(section)):
            ident = expected_item["id"]
            tag = expected_item["status"]
            item = observed_items.get(ident, {})
            matched = status_matches(expected_item, item)
            score.measure(tag, matched)
            if not matched:
                score.issues["incorrect_line_status"].append(f"{rid}/{section}/{ident}")
    classified = structural_ids(key.get("accounted"))
    score.false_abstentions.extend(
        f"{rid}/{i}" for i in sorted(classified & set(tagged_ids(out)))
    )
    # A claimed amount with no expected counterpart is a finding, even if its
    # citations appear plausible. Input metadata and confirmed factors are not
    # bridge outputs; they are checked at their physical source when referenced.
    known = {
        "bridges",
        "comparisons",
        "schedules",
        "tier_limits",
        "tier_changes",
        "flags",
        "schema_version",
        "inputs",
        "metadata",
        "gate",
        "warnings",
        "unimplemented",
        "conversions",
        "corrections",
        "withheld",
        "unsupported_splits",
        "abstentions",
        "accounted",
        "commentary",
        "exclusions",
        "joint_questions",
    }
    for extra in set(out) - known:
        scan_extra(score, out[extra], audit.accounted, f"{rid}/{extra}")
        if number(out[extra]) is not None:
            score.issues["unsupported_numbers"].append(f"{rid}/{extra}")
    for section in (
        "bridges",
        "comparisons",
        "schedules",
        "tier_limits",
        "tier_changes",
        "flags",
    ):
        scan_extra(score, out.get(section), audit.accounted, f"{rid}/{section}")


def run_cli(
    package: Path,
    key: Obj,
    target: Path,
    cli: str,
    env: Mapping[str, str],
    engine: str,
    score: Score,
    sources: Sources,
) -> None:
    out_path = target / "result"
    args = [
        cli,
        "compare",
        str(package / "opening.xlsx"),
        str(package / "closing.xlsx"),
        "--output-dir",
        str(out_path),
    ]
    if key["id"] == "02a-confirmed":
        args.extend(["--confirmations", str(package / "confirmations.json")])
    out: Obj = {}
    excel = None
    try:
        proc = subprocess.run(
            args,
            env=env,
            cwd=target,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode and (
            key["gate"]["status"] != "blocked"
            or not (out_path / "summary.json").is_file()
        ):
            message = (proc.stderr or proc.stdout).strip()
            score.issues["cli_errors"].append(
                f"{key['id']}: exit {proc.returncode}: {message}"
            )
        if (out_path / "summary.json").is_file():
            with (out_path / "summary.json").open() as f:
                document = json.load(f)
                if not isinstance(document, dict):
                    raise ValueError("JSON summary must be an object")
                out = document
            paths = list(out_path.glob("*.xlsx"))
            if len(paths) == 1:
                excel = recalculate(paths[0], target, engine)
            else:
                score.issues["workbook_errors"].append(
                    f"{key['id']}: missing/ambiguous workbook"
                )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        score.issues["execution_errors"].append(f"{key['id']}: {exc}")
    try:
        score_run(score, sources, key, out, excel)
    finally:
        if excel:
            excel.formulas.close()
            excel.values.close()


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packages", type=Path, default=HERE / "packages")
    p.add_argument("--cli", default=str(Path(sys.executable).parent / "s2movement"))
    p.add_argument("--soffice", default=shutil.which("soffice") or str(LO))
    a = p.parse_args(argv)
    digest = verify() if a.packages.resolve() == HERE / "packages" else None
    score = Score()
    env = dict(os.environ)
    project = HERE.parents[1]
    # Installed entry point is the sole interface to the product.
    env["PYTHONPATH"] = str(project / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    runs = []
    for case in CASES:
        package = a.packages.resolve() / case
        data = json.loads((package / "expected.yaml").read_text())
        sources = Sources(package)
        for key in data["runs"]:
            runs.append(key["id"])
            with tempfile.TemporaryDirectory(prefix="s2-benchmark-") as tmp:
                run_cli(package, key, Path(tmp), a.cli, env, a.soffice, score, sources)
    if len(runs) != 7 or len(set(runs)) != 7:
        score.issues["population_errors"].append(str(runs))
    report = score.report()
    report["manifest_sha256"] = digest
    report["mode"] = "diagnostic"
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["deterministic_gates_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
