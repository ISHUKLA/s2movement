"""Validated evidence models shared by adapters and downstream calculations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Period = Literal["opening", "closing"]
MAX_EXACT_EXCEL_INTEGER = Decimal("999999999999999")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Citation(StrictModel):
    period: Period
    file_id: str
    sha256: str
    sheet: str
    cell: str
    template: str | None = None
    table: str | None = None
    row: str | None = None
    column: str | None = None
    context_id: str | None = None
    dimensions: dict[str, str] = Field(default_factory=dict)
    coordinate_context: str | None = None
    metadata_field: str | None = None


class InputFile(StrictModel):
    period: Period
    file_id: str
    sha256: str
    variant: str
    templates: tuple[str, ...] = ()
    sr_contexts: tuple[Citation, ...] = ()
    presence: dict[str, Citation] = Field(default_factory=dict)


class MetadataCorrection(StrictModel):
    period: Period
    file_id: str
    name: str
    original_value: str
    corrected_value: str
    reason: str
    reviewer: str
    evidence: str
    citation: Citation


class MetadataFact(StrictModel):
    period: Period
    name: str
    value: str
    reported_value: str | None = None
    citation: Citation
    correction: MetadataCorrection | None = None
    corroboration: tuple[Citation, ...] = ()


class ConversionConfirmation(StrictModel):
    period: Period
    file_id: str
    factor: Decimal
    target_unit_scale: Decimal
    reason: str
    reviewer: str
    evidence: str
    citation: Citation

    @field_validator("factor", "target_unit_scale")
    @classmethod
    def positive_factor(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError(
                "conversion factors and unit scales must be positive and finite"
            )
        return value


class ReportedDeclaration(StrictModel):
    value: str
    citation: Citation


class InputIssue(StrictModel):
    id: str
    message: str
    citations: tuple[Citation, ...]


class LedgerFact(StrictModel):
    """One reported numeric cell, retaining its exact source and context."""

    period: Period
    template: str
    table: str
    row: str
    column: str
    context_id: str
    dimensions: dict[str, str]
    coordinate_context: str | None = None
    kind: Literal["money", "ratio"] = "money"
    reported_value: Decimal
    currency: str
    unit_scale: Decimal
    reported_precision: Decimal | None
    citation: Citation
    conversion: ConversionConfirmation | None = None

    @model_validator(mode="after")
    def supported_number(self) -> LedgerFact:
        value = self.reported_value
        if not value.is_finite() or abs(value) > MAX_EXACT_EXCEL_INTEGER:
            raise ValueError("numeric fact exceeds the supported Excel range")
        if self.kind == "money" and value != value.to_integral_value():
            raise ValueError("monetary amounts must use whole reporting units")
        if self.kind == "ratio" and self.conversion is not None:
            raise ValueError("a currency scale conversion cannot apply to a ratio")
        return self

    @field_validator("unit_scale", "reported_precision")
    @classmethod
    def positive_unit_data(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= 0):
            raise ValueError("unit scale and precision must be positive and finite")
        return value

    @property
    def resolved_value(self) -> Decimal:
        if self.conversion is None:
            return self.reported_value
        return self.reported_value * self.conversion.factor

    @property
    def resolved_unit_scale(self) -> Decimal:
        if self.conversion is None:
            return self.unit_scale
        return self.conversion.target_unit_scale

    @property
    def resolved_precision(self) -> Decimal | None:
        if self.conversion is None or self.reported_precision is None:
            return self.reported_precision
        return (
            self.reported_precision
            * self.unit_scale
            / self.conversion.target_unit_scale
        )


class ContextRecord(StrictModel):
    context_id: str
    entity_lei: str
    reference_date: date
    dimensions: dict[str, str] = Field(default_factory=dict)


class Ledger(StrictModel):
    supplied_reversed: bool = False
    declarations: tuple[ReportedDeclaration, ...] = ()
    input_issues: tuple[InputIssue, ...] = ()
    inputs: tuple[InputFile, ...]
    metadata: tuple[MetadataFact, ...]
    facts: tuple[LedgerFact, ...]
    conversions: tuple[ConversionConfirmation, ...] = ()
    corrections: tuple[MetadataCorrection, ...] = ()

    def metadata_value(self, period: Period, name: str) -> MetadataFact | None:
        matches = [
            item
            for item in self.metadata
            if item.period == period and item.name == name
        ]
        return matches[0] if len(matches) == 1 else None

    def find_fact(
        self,
        *,
        period: Period,
        table: str,
        row: str,
        column: str,
        dimensions: dict[str, str],
        coordinate_context: str | None = None,
    ) -> LedgerFact | None:
        matches = [
            fact
            for fact in self.facts
            if fact.period == period
            and fact.table == table
            and fact.row == row
            and fact.column == column
            and fact.dimensions == dimensions
            and fact.coordinate_context == coordinate_context
        ]
        return matches[0] if len(matches) == 1 else None
