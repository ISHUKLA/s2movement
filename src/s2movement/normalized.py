"""Read the documented normalized workbook format into a fact ledger."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from calendar import monthrange
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from pydantic import ValidationError

from s2movement.models import (
    MAX_EXACT_EXCEL_INTEGER,
    Citation,
    ContextRecord,
    ConversionConfirmation,
    InputFile,
    InputIssue,
    Ledger,
    LedgerFact,
    MetadataCorrection,
    MetadataFact,
    Period,
    ReportedDeclaration,
)

METADATA_FIELDS = (
    "format_version",
    "reference_date",
    "variant",
    "taxonomy_version",
    "taxonomy_variant",
    "perimeter",
    "frequency",
    "lei",
    "undertaking_name",
    "currency",
    "money_unit_scale",
    "money_precision",
    "scr_method",
    "rff_indicator",
    "map_indicator",
    "ma_applied",
    "va_applied",
    "tmir_applied",
    "tmtp_applied",
    "ratio_precision",
)
ROW_CODE = re.compile(r"R\d{4}\Z")
COLUMN_CODE = re.compile(r"C\d{4}\Z")
# Presence mappings from VERIFICATION §5, including the full SR inventory.
VARIATION_FAMILIES = frozenset({"S.29.01", "S.29.02", "S.29.03", "S.29.04"})
SR_FAMILIES = frozenset(
    {
        "SR.01.01",
        "SR.02.01",
        "SR.12.01",
        "SR.17.01",
        "SR.22.02",
        "SR.22.03",
        "SR.25.01",
        "SR.25.05",
        *(f"SR.26.{n:02}" for n in range(1, 9)),
    }
)
SIGNATURE_DIMENSION = re.compile(r"(s2c_[A-Z]{2})\((s2c_x\w+)\)")


class InputError(ValueError):
    """An input file does not follow the documented normalized format."""


def mapping_root() -> Path:
    """Return the repository's versioned mapping data directory."""
    return Path(__file__).resolve().parents[2] / "mappings"


def _text(value: object, *, label: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not value.is_integer():
            return str(value)
        return str(int(value))
    raise InputError(f"{label} must contain a non-empty literal value")


def _decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise InputError(f"{label} must be a literal decimal number")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise InputError(f"{label} is not a valid decimal number") from exc
    if not number.is_finite():
        raise InputError(f"{label} must be finite")
    return number


def _reject_formula_cells(workbook: Workbook, *, file_id: str) -> None:
    if getattr(workbook, "_external_links", []):
        raise InputError(f"{file_id} contains external workbook links")
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    raise InputError(
                        "formula cell is not allowed: "
                        f"{worksheet.title}!{cell.coordinate}"
                    )
                if cell.data_type == "e":
                    raise InputError(
                        "error-valued cell is not allowed: "
                        f"{worksheet.title}!{cell.coordinate}"
                    )


def _metadata_sheet(
    workbook: Workbook,
    *,
    path: Path,
    period: Period,
    digest: str,
    date_only: bool = False,
) -> tuple[dict[str, str], list[MetadataFact]]:
    if "Metadata" not in workbook.sheetnames:
        raise InputError(f"{path.name} is missing its Metadata sheet")
    sheet = workbook["Metadata"]
    if not date_only and (sheet["A1"].value != "field" or sheet["B1"].value != "value"):
        raise InputError(f"{path.name} Metadata!A1:B1 must be field/value headers")
    values: dict[str, str] = {}
    facts: list[MetadataFact] = []
    for row_number in range(2, sheet.max_row + 1):
        raw_name = sheet.cell(row_number, 1).value
        if raw_name is None or (date_only and raw_name != "reference_date"):
            continue
        name = _text(raw_name, label=f"Metadata!A{row_number}")
        if name not in METADATA_FIELDS:
            raise InputError(f"unsupported metadata field {name!r} in {path.name}")
        if name in values:
            raise InputError(f"duplicate metadata field {name!r} in {path.name}")
        value = _text(sheet.cell(row_number, 2).value, label=f"Metadata!B{row_number}")
        values[name] = value
        citation = Citation(
            period=period,
            file_id=path.name,
            sha256=digest,
            sheet="Metadata",
            cell=f"B{row_number}",
            metadata_field=name,
        )
        facts.append(
            MetadataFact(
                period=period,
                name=name,
                value=value,
                reported_value=value,
                citation=citation,
            )
        )
    if date_only:
        return values, facts
    missing = sorted(set(METADATA_FIELDS) - values.keys())
    if missing:
        raise InputError(
            f"{path.name} is missing metadata fields: {', '.join(missing)}"
        )
    if values["format_version"] != "0.1":
        raise InputError(
            f"unsupported normalized workbook format {values['format_version']!r}"
        )
    return values, facts


def _validate_metadata_values(values: dict[str, str], *, path: Path) -> None:
    try:
        date.fromisoformat(values["reference_date"])
    except ValueError as exc:
        raise InputError(f"{path.name} reference_date must be ISO YYYY-MM-DD") from exc
    if not values["money_unit_scale"].isdigit() or int(values["money_unit_scale"]) <= 0:
        raise InputError(
            "money_unit_scale must be a positive integer in the first slice"
        )
    if values["money_precision"] != "1":
        raise InputError("the first slice supports whole reporting-unit precision only")
    if values["variant"] not in {"supervisory", "public_disclosure"}:
        raise InputError(f"unknown reporting variant {values['variant']!r}")


def _context_sheet(
    workbook: Workbook,
    *,
    path: Path,
    header: dict[str, MetadataFact],
    issues: list[InputIssue],
) -> dict[str, ContextRecord]:
    if "Contexts" not in workbook.sheetnames:
        raise InputError(f"{path.name} is missing its Contexts sheet")
    sheet = workbook["Contexts"]
    expected = ("context_id", "entity_lei", "reference_date", "dimensions")
    if tuple(sheet.cell(1, column).value for column in range(1, 5)) != expected:
        raise InputError(f"{path.name} Contexts!A1:D1 must be {expected!r}")
    contexts: dict[str, ContextRecord] = {}
    for row_number in range(2, sheet.max_row + 1):
        context_id_value = sheet.cell(row_number, 1).value
        if context_id_value is None:
            continue
        context_id = _text(context_id_value, label=f"Contexts!A{row_number}")
        if context_id in contexts:
            raise InputError(f"duplicate context id {context_id!r} in {path.name}")
        try:
            dimensions_value = json.loads(
                _text(sheet.cell(row_number, 4).value, label=f"Contexts!D{row_number}")
            )
        except json.JSONDecodeError as exc:
            raise InputError(f"Contexts!D{row_number} must be a JSON object") from exc
        if not isinstance(dimensions_value, dict) or any(
            not isinstance(key, str) or not isinstance(member, str)
            for key, member in dimensions_value.items()
        ):
            raise InputError(
                f"Contexts!D{row_number} must map DPM dimension codes to member codes"
            )
        try:
            context = ContextRecord(
                context_id=context_id,
                entity_lei=_text(
                    sheet.cell(row_number, 2).value, label=f"Contexts!B{row_number}"
                ),
                reference_date=date.fromisoformat(
                    _text(
                        sheet.cell(row_number, 3).value, label=f"Contexts!C{row_number}"
                    )
                ),
                dimensions=dimensions_value,
            )
        except (ValueError, ValidationError) as exc:
            raise InputError(f"invalid context {context_id!r}: {exc}") from exc
        for name, value, column in (
            ("lei", context.entity_lei, "B"),
            ("reference_date", context.reference_date.isoformat(), "C"),
        ):
            declared = header[name]
            if value != declared.value and not any(
                item.id == f"{declared.period}_{name}_context" for item in issues
            ):
                evidence = declared.citation.model_copy(
                    update={
                        "sheet": "Contexts",
                        "cell": f"{column}{row_number}",
                        "context_id": context_id,
                        "metadata_field": name,
                    }
                )
                issues.append(
                    InputIssue(
                        id=f"{declared.period}_{name}_context",
                        message=(
                            f"{declared.period} {name}: Metadata "
                            f"{declared.value!r} differs from context {value!r} in "
                            f"{path.name}. Correct the metadata with source evidence "
                            "or supply the matching filing."
                        ),
                        citations=(declared.citation, evidence),
                    )
                )
        contexts[context_id] = context
    return contexts


def _read_mapping(
    version: str, root: Path
) -> dict[tuple[str, str, str], dict[str, str]]:
    mapping_file = root / version / "cells.csv"
    if not mapping_file.is_file():
        raise InputError(f"no local cell mapping is available for taxonomy {version}")
    with mapping_file.open(encoding="utf-8", newline="") as stream:
        return {
            (row["table"], row["row"], row["column"]): row
            for row in csv.DictReader(stream)
        }


def _expected_dimensions(signature: str) -> dict[str, str]:
    return {
        dimension: member
        for dimension, member in SIGNATURE_DIMENSION.findall(signature)
    }


def _parse_template_sheets(
    workbook: Workbook,
    *,
    path: Path,
    period: Period,
    digest: str,
    metadata: dict[str, str],
    contexts: dict[str, ContextRecord],
    cell_mappings: dict[tuple[str, str, str], dict[str, str]],
) -> tuple[
    list[LedgerFact],
    list[ReportedDeclaration],
    dict[str, Citation],
    tuple[Citation, ...],
]:
    facts: list[LedgerFact] = []
    declarations: list[ReportedDeclaration] = []
    presence: dict[str, Citation] = {}
    portfolios: dict[tuple[str, str], Citation] = {}
    template_sheets = [
        name for name in workbook.sheetnames if name not in {"Metadata", "Contexts"}
    ]
    for sheet_name in template_sheets:
        sheet = workbook[sheet_name]
        row_index = 1
        while row_index <= sheet.max_row:
            if sheet.cell(row_index, 1).value != "table":
                row_index += 1
                continue
            table = _text(
                sheet.cell(row_index, 2).value, label=f"{sheet_name}!B{row_index}"
            )
            family = ".".join(table.split(".")[:3])
            if family != sheet_name:
                raise InputError(
                    f"table {table} must be in the {family} sheet, not {sheet_name}"
                )
            context_row = row_index + 1
            if sheet.cell(context_row, 1).value != "context":
                raise InputError(f"{table} block is missing its context row")
            context_id = _text(
                sheet.cell(context_row, 2).value, label=f"{sheet_name}!B{context_row}"
            )
            context = contexts.get(context_id)
            if context is None:
                raise InputError(f"unknown context {context_id!r} in {path.name}")
            header_row = context_row + 1
            coordinate_context: str | None = None
            if sheet.cell(header_row, 1).value == "coordinate_context":
                coordinate_context = _text(
                    sheet.cell(header_row, 2).value, label=f"{sheet_name}!B{header_row}"
                )
                header_row += 1
            if sheet.cell(header_row, 1).value != "row/column":
                raise InputError(f"{table} block is missing its row/column header")
            column_codes: dict[int, str] = {}
            for column_index in range(2, sheet.max_column + 1):
                raw_column = sheet.cell(header_row, column_index).value
                if raw_column is None:
                    continue
                column_code = _text(
                    raw_column,
                    label=(
                        f"{sheet_name}!"
                        f"{sheet.cell(header_row, column_index).coordinate}"
                    ),
                )
                if not COLUMN_CODE.fullmatch(column_code):
                    raise InputError(f"invalid column code {column_code!r} in {table}")
                if column_code in column_codes.values():
                    raise InputError(
                        f"duplicate column code {column_code!r} in {table}"
                    )
                column_codes[column_index] = column_code
            data_row = header_row + 1
            while (
                data_row <= sheet.max_row and sheet.cell(data_row, 1).value is not None
            ):
                row_code = _text(
                    sheet.cell(data_row, 1).value, label=f"{sheet_name}!A{data_row}"
                )
                if not ROW_CODE.fullmatch(row_code):
                    raise InputError(f"invalid row code {row_code!r} in {table}")
                for column_index, column_code in column_codes.items():
                    cell = sheet.cell(data_row, column_index)
                    if cell.value is None:
                        continue
                    citation = Citation(
                        period=period,
                        file_id=path.name,
                        sha256=digest,
                        sheet=sheet_name,
                        cell=cell.coordinate,
                        template=family,
                        table=table,
                        row=row_code,
                        column=column_code,
                        context_id=context_id,
                        dimensions=context.dimensions,
                        coordinate_context=coordinate_context,
                    )
                    presence.setdefault(family, citation)
                    if family in SR_FAMILIES:
                        portfolios.setdefault((table, context_id), citation)
                    if (
                        family in VARIATION_FAMILIES
                        or family in SR_FAMILIES
                        or family == "S.25.05"
                        or table in {"S.32.01.04.01", "S.32.01.22.01"}
                    ):
                        # Preserve presence with the actual locator. These amounts
                        # are outside the supported financial comparisons.
                        continue
                    key = (table, row_code, column_code)
                    mapping = cell_mappings.get(key)
                    if mapping is None:
                        raise InputError(
                            f"unmapped cell {table} {row_code}/{column_code}"
                        )
                    variant_key = (
                        "supervisory_ars"
                        if metadata["variant"] == "supervisory"
                        else "public_aps"
                    )
                    if mapping[variant_key] != "yes":
                        raise InputError(
                            f"{table} {row_code}/{column_code} is not mapped "
                            f"for {metadata['variant']}"
                        )
                    expected = _expected_dimensions(mapping["data_point_signature"])
                    if not expected.items() <= context.dimensions.items():
                        raise InputError(
                            f"context {context_id!r} dimensions do not match "
                            f"{table} {row_code}/{column_code}: "
                            f"expected {expected}, got {context.dimensions}"
                        )
                    monetary = mapping["monetary"] == "yes"
                    is_ratio = family == "S.23.01" and row_code in {"R0620", "R0640"}
                    if not monetary and not is_ratio:
                        declarations.append(
                            ReportedDeclaration(
                                value=_text(
                                    cell.value, label=f"{sheet_name}!{cell.coordinate}"
                                ),
                                citation=citation,
                            )
                        )
                        continue
                    precision = metadata[
                        "money_precision" if monetary else "ratio_precision"
                    ]
                    numeric_value = _decimal(
                        cell.value, label=f"{sheet_name}!{cell.coordinate}"
                    )
                    try:
                        facts.append(
                            LedgerFact(
                                period=period,
                                template=family,
                                table=table,
                                row=row_code,
                                column=column_code,
                                context_id=context_id,
                                dimensions=context.dimensions,
                                coordinate_context=coordinate_context,
                                reported_value=numeric_value,
                                kind="money" if monetary else "ratio",
                                currency=metadata["currency"] if monetary else "ratio",
                                unit_scale=Decimal(metadata["money_unit_scale"])
                                if monetary
                                else Decimal(1),
                                reported_precision=(
                                    None
                                    if precision == "unknown"
                                    else _decimal(precision, label=f"{table} precision")
                                ),
                                citation=citation,
                            )
                        )
                    except ValidationError as exc:
                        raise InputError(
                            f"invalid monetary cell {table} "
                            f"{row_code}/{column_code}: {exc}"
                        ) from exc
                data_row += 1
            row_index = data_row + 1
    keys = [
        (
            c.table,
            c.row,
            c.column,
            tuple(sorted(c.dimensions.items())),
            c.coordinate_context,
        )
        for c in [f.citation for f in facts] + [d.citation for d in declarations]
    ]
    if len(keys) != len(set(keys)):
        raise InputError(
            f"{path.name} contains a duplicate table/row/column/context fact"
        )
    return facts, declarations, presence, tuple(portfolios.values())


def _read_confirmations(path: Path | None) -> list[ConversionConfirmation]:
    if path is None:
        return []
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(
            "conversion confirmation file must be valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "0.1":
        raise InputError("conversion confirmation file must have schema_version 0.1")
    items = payload.get("confirmations")
    if not isinstance(items, list):
        raise InputError(
            "conversion confirmation file must contain a confirmations list"
        )
    confirmations: list[ConversionConfirmation] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise InputError("each conversion confirmation must be an object")
        try:
            citation = Citation(
                period=item["period"],
                file_id=path.name,
                sha256=digest,
                sheet="JSON",
                cell=f"/confirmations/{index}",
                metadata_field="scale_conversion_confirmation",
            )
            confirmations.append(
                ConversionConfirmation(
                    period=item["period"],
                    file_id=item["file_id"],
                    factor=_decimal(item["factor"], label="factor"),
                    target_unit_scale=_decimal(
                        item["target_unit_scale"], label="target_unit_scale"
                    ),
                    reason=_text(item["reason"], label="reason"),
                    reviewer=_text(item["reviewer"], label="reviewer"),
                    evidence=_text(item["evidence"], label="evidence"),
                    citation=citation,
                )
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise InputError(
                f"invalid conversion confirmation at index {index}: {exc}"
            ) from exc
    return confirmations


def _read_metadata_corrections(path: Path | None) -> list[MetadataCorrection]:
    if path is None:
        return []
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("metadata corrections must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "0.1":
        raise InputError("metadata correction file must have schema_version 0.1")
    items = payload.get("corrections")
    if not isinstance(items, list):
        raise InputError("metadata correction file must contain a corrections list")
    corrections: list[MetadataCorrection] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise InputError("each metadata correction must be an object")
        try:
            name = _text(item["field"], label=f"corrections[{index}].field")
            if name not in METADATA_FIELDS or name == "format_version":
                raise InputError(f"unsupported metadata correction field {name!r}")
            citation = Citation(
                period=item["period"],
                file_id=path.name,
                sha256=digest,
                sheet="JSON",
                cell=f"/corrections/{index}",
                metadata_field=name,
            )
            corrections.append(
                MetadataCorrection(
                    period=item["period"],
                    file_id=_text(
                        item["file_id"], label=f"corrections[{index}].file_id"
                    ),
                    name=name,
                    original_value=_text(
                        item["original_value"],
                        label=f"corrections[{index}].original_value",
                    ),
                    corrected_value=_text(
                        item["corrected_value"],
                        label=f"corrections[{index}].corrected_value",
                    ),
                    reason=_text(item["reason"], label=f"corrections[{index}].reason"),
                    reviewer=_text(
                        item["reviewer"], label=f"corrections[{index}].reviewer"
                    ),
                    evidence=_text(
                        item["evidence"], label=f"corrections[{index}].evidence"
                    ),
                    citation=citation,
                )
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise InputError(
                f"invalid metadata correction at index {index}: {exc}"
            ) from exc
    return corrections


@dataclass
class PeriodSource:
    path: Path
    digest: str
    workbook: Workbook | None
    period: Period = "opening"
    header: dict[str, MetadataFact] = field(default_factory=dict)
    facts: list[LedgerFact] = field(default_factory=list)
    declarations: list[ReportedDeclaration] = field(default_factory=list)
    presence: dict[str, Citation] = field(default_factory=dict)
    sr_contexts: tuple[Citation, ...] = ()

    def descriptor(self) -> InputFile:
        variant = self.header.get("variant")
        return InputFile(
            period=self.period,
            file_id=self.path.name,
            sha256=self.digest,
            variant=variant.value if variant else "unknown",
            templates=tuple(sorted(self.presence)),
            presence=self.presence,
            sr_contexts=self.sr_contexts,
        )


def _source(path: Path, stack: ExitStack) -> PeriodSource:
    contents = path.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    if path.suffix.lower() == ".pdf" or contents.startswith(b"%PDF-"):
        return PeriodSource(path, digest, None)
    if path.suffix.lower() != ".xlsx":
        raise InputError(f"normalized input must be .xlsx: {path.name}")
    # Random-access cells in a read-only streaming worksheet repeatedly re-parse
    # the XML. Take one snapshot and read/hash that same version of the file.
    workbook = load_workbook(BytesIO(contents), data_only=False, keep_links=True)
    stack.callback(workbook.close)
    return PeriodSource(path, digest, workbook)


def _reported_date(source: PeriodSource) -> date:
    workbook = source.workbook
    assert workbook is not None
    if "Metadata" not in workbook.sheetnames:
        raise InputError(
            f"{source.path.name} has no Metadata sheet with a reference date"
        )
    rows = [
        r
        for r in workbook["Metadata"].iter_rows(min_col=1, max_col=2)
        if r[0].value == "reference_date"
    ]
    if len(rows) != 1:
        raise InputError(f"{source.path.name} must declare one reference_date")
    cell = rows[0][1]
    try:
        return date.fromisoformat(
            _text(cell.value, label=f"Metadata!{cell.coordinate}")
        )
    except ValueError as exc:
        raise InputError(
            f"{source.path.name} Metadata!{cell.coordinate} requires an ISO date"
        ) from exc


def _order_date(source: PeriodSource, corrections: list[MetadataCorrection]) -> date:
    reported = _reported_date(source)
    for item in corrections:
        if (
            item.file_id == source.path.name
            and item.name == "reference_date"
            and item.original_value == reported.isoformat()
        ):
            return date.fromisoformat(item.corrected_value)
    return reported


def _successive(a: date, b: date) -> bool:
    if b.year != a.year + 1 or b.month != a.month:
        return False
    # Annual month ends remain consecutive across a leap year.
    return b.day == a.day or (
        a.day == monthrange(a.year, a.month)[1]
        and b.day == monthrange(b.year, b.month)[1]
    )


def _read_header(
    source: PeriodSource,
    corrections: list[MetadataCorrection],
    *,
    date_only: bool = False,
) -> None:
    if source.workbook is None:
        return
    _, items = _metadata_sheet(
        source.workbook,
        path=source.path,
        digest=source.digest,
        period=source.period,
        date_only=date_only,
    )
    source.header = {item.name: item for item in items}
    for correction in corrections:
        if correction.period != source.period or (
            date_only and correction.name != "reference_date"
        ):
            continue
        if correction.file_id != source.path.name:
            raise InputError(
                f"metadata correction file_id differs from the {source.period} input"
            )
        item = source.header[correction.name]
        if item.value != correction.original_value:
            raise InputError(
                f"{source.period} metadata correction for {item.name} expected "
                f"{correction.original_value!r}, found {item.value!r}"
            )
        source.header[item.name] = item.model_copy(
            update={"value": correction.corrected_value, "correction": correction}
        )


# Direct supervisory locations and display values from VERIFICATION §1 and
# metadata_enumerations.csv. MAP activity remains a distinct declaration.
DIRECT_METADATA = {
    "R0010": "undertaking_name",
    "R0020": "lei",
    "R0090": "reference_date",
    "R0110": "currency",
    "R0130": "scr_method",
    "R0150": "rff_indicator",
    "R0170": "ma_applied",
    "R0180": "va_applied",
    "R0190": "tmir_applied",
    "R0200": "tmtp_applied",
}


def _corroborate(source: PeriodSource, issues: list[InputIssue], root: Path) -> None:
    with (root / "2.8.2" / "metadata_enumerations.csv").open(encoding="utf-8") as f:
        meanings = {
            (r["row"], r[k]): r["meaning"]
            for r in csv.DictReader(f)
            for k in ("legal_display_code", "xbrl_member")
        }
    for declaration in source.declarations:
        c = declaration.citation
        row = c.row or ""
        if (
            c.table != "S.01.02.01.01"
            or c.column != "C0010"
            or row not in DIRECT_METADATA
        ):
            continue
        name = DIRECT_METADATA[row]
        value = declaration.value
        meaning = meanings.get((row, value))
        if meaning is not None:
            value = (
                meaning.replace(" ", "_")
                if name == "scr_method"
                else "no"
                if meaning.startswith(("not ", "no "))
                else "yes"
            )
        stated = source.header[name]
        if value != stated.value:
            issues.append(
                InputIssue(
                    id=f"{source.period}_{name}_declarations",
                    message=(
                        f"{source.period} {name}: {stated.citation.sheet}!"
                        f"{stated.citation.cell} declares {stated.value!r}; {c.sheet}!"
                        f"{c.cell} reports {declaration.value!r} ({value}). Supply "
                        "consistent metadata with source evidence or a matching filing."
                    ),
                    citations=(stated.citation, c),
                )
            )
        else:
            source.header[name] = stated.model_copy(
                update={"corroboration": (*stated.corroboration, c)}
            )


def _parse_source(source: PeriodSource, issues: list[InputIssue], root: Path) -> None:
    workbook = source.workbook
    assert workbook is not None
    values = {k: item.value for k, item in source.header.items()}
    if values["taxonomy_version"] != "2.8.2":
        # The gate cites the actual version. Never interpret it using a 2.8.2 grid.
        return
    _validate_metadata_values(values, path=source.path)
    _reject_formula_cells(workbook, file_id=source.path.name)
    contexts = _context_sheet(
        workbook, path=source.path, header=source.header, issues=issues
    )
    mappings = _read_mapping(values["taxonomy_version"], root)
    (source.facts, source.declarations, source.presence, source.sr_contexts) = (
        _parse_template_sheets(
            workbook,
            path=source.path,
            period=source.period,
            digest=source.digest,
            metadata=values,
            contexts=contexts,
            cell_mappings=mappings,
        )
    )
    # An inventory declaration can evidence an observational template even when
    # a normalizer omits that template's unused data. Financial templates must
    # contain actual facts to support a comparison.
    for item in source.declarations:
        c = item.citation
        if (
            c.table != "S.01.01.01.01"
            or c.column != "C0010"
            or item.value.casefold() != "reported"
        ):
            continue
        record = mappings.get((c.table, c.row or "", c.column), {})
        match = re.search(r"\b(SR?\.\d{2}\.\d{2})\.", record.get("row_label", ""))
        if match and match[1] in VARIATION_FAMILIES | SR_FAMILIES | {"S.25.05"}:
            source.presence.setdefault(match[1], c)
    _corroborate(source, issues, root)


def _load_sources(
    first: PeriodSource,
    second: PeriodSource,
    corrections: list[MetadataCorrection],
    root: Path,
    confirmation_path: Path | None,
) -> Ledger:
    pair = [first, second]
    issues: list[InputIssue] = []
    reversed_pair = False
    dates: list[date] = []
    if all(source.workbook is not None for source in pair):
        dates = [_order_date(source, corrections) for source in pair]
        if dates[0] > dates[1]:
            dates.reverse()
            pair.reverse()
            reversed_pair = True
    pair[0].period, pair[1].period = "opening", "closing"
    invalid_dates = bool(dates and not _successive(*dates))
    for source in pair:
        if source.workbook is None:
            issues.append(
                InputIssue(
                    id=f"{source.period}_pdf_input",
                    message=(
                        f"{source.period} {source.path.name} is a PDF. Supply the "
                        "normalized reporting workbook for that filing."
                    ),
                    citations=(
                        Citation(
                            period=source.period,
                            file_id=source.path.name,
                            sha256=source.digest,
                            sheet="File",
                            cell="document",
                        ),
                    ),
                )
            )
        else:
            _read_header(source, corrections, date_only=invalid_dates)
    if invalid_dates:
        a, b = (source.header["reference_date"] for source in pair)
        issues.append(
            InputIssue(
                id="consecutive_annual_periods",
                message=(
                    f"Opening reference date {a.value} and closing reference date "
                    f"{b.value} must be distinct successive annual dates. Supply "
                    "the adjoining annual filing or correct a misreported date "
                    "with source evidence."
                ),
                citations=(a.citation, b.citation),
            )
        )
    confirmations: list[ConversionConfirmation] = []
    if not issues:
        for source in pair:
            _parse_source(source, issues, root)
        confirmations = _attach_conversions(pair, confirmation_path)
    return Ledger(
        inputs=tuple(s.descriptor() for s in pair),
        metadata=tuple(f for s in pair for f in s.header.values()),
        facts=tuple(f for s in pair for f in s.facts),
        declarations=tuple(d for s in pair for d in s.declarations),
        input_issues=tuple(issues),
        supplied_reversed=reversed_pair,
        corrections=tuple(corrections),
        conversions=tuple(confirmations),
    )


def _attach_conversions(
    pair: list[PeriodSource], path: Path | None
) -> list[ConversionConfirmation]:
    confirmations = _read_confirmations(path)
    seen: set[Period] = set()
    sources = {source.period: source for source in pair}
    for item in confirmations:
        source = sources[item.period]
        scale = Decimal(source.header["money_unit_scale"].value)
        if item.period in seen or source.path.name != item.file_id:
            raise InputError("duplicate or misaddressed scale confirmation")
        seen.add(item.period)
        if (
            pair[0].header["money_unit_scale"].value
            == pair[1].header["money_unit_scale"].value
            or scale == 1
            or item.factor != scale
            or item.target_unit_scale != 1
        ):
            raise InputError(
                f"{item.period} confirmation requires unequal scales and factor "
                f"{scale} into currency units"
            )
        for i, fact in enumerate(source.facts):
            if fact.kind != "money":
                continue
            if abs(fact.reported_value * item.factor) > MAX_EXACT_EXCEL_INTEGER:
                raise InputError(
                    f"{source.period} converted value exceeds exact Excel range"
                )
            source.facts[i] = fact.model_copy(update={"conversion": item})
    return confirmations


def load_ledger(
    opening_path: Path,
    closing_path: Path,
    *,
    mapping_directory: Path | None = None,
    confirmation_path: Path | None = None,
    correction_path: Path | None = None,
) -> Ledger:
    """Order the filings and retain both the reported evidence and reviewer actions."""
    corrections = _read_metadata_corrections(correction_path)
    keys = [(item.period, item.name) for item in corrections]
    if len(set(keys)) != len(keys):
        raise InputError("duplicate metadata correction for one period and field")
    with ExitStack() as stack:
        return _load_sources(
            _source(opening_path, stack),
            _source(closing_path, stack),
            corrections,
            mapping_directory or mapping_root(),
            confirmation_path,
        )
