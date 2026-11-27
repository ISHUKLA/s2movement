"""Optional, fail-closed drafting from citation-validated JSON only."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from docx import Document
from docx.document import Document as WordDocument
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from pydantic import BaseModel, ConfigDict, Field

MODEL = "claude-sonnet-4-6"
REF = re.compile(r"\{ref:([^{}]+)\}")
NUMBER = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)?%?(?![A-Za-z0-9])")
CODE = re.compile(r"\b(?:S|SR)\.\d{2}\.\d{2}(?:\.\d{2}){0,2}\b|\b[RC]\d{4}\b")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b")
ARTICLE = re.compile(r"\bArticle\s+\d+(?:\(\d+\))?", re.IGNORECASE)
TIER = re.compile(r"\bTier\s+[123]\b", re.IGNORECASE)
CAUSAL = re.compile(
    r"\b(?:driven by|caused by|due to|because of|attributable to|resulted from)\b",
    re.IGNORECASE,
)
SPLIT = re.compile(r"\b(?:percent|percentage|share of|portion of|allocated to)\b", re.I)


class PackWithheld(ValueError):
    """A source or drafting gate prevented delivery of the optional pack."""


class DraftItem(BaseModel):
    """One model-selected, typed review item."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "fact", "triage_question", "hypothesis", "abstention", "verification_check"
    ]
    text: str
    reference_ids: list[str] = Field(default_factory=list)
    catalogue_id: str | None = None
    flag_ids: list[str] = Field(default_factory=list)
    movement_id: str | None = None


class Draft(BaseModel):
    """Provider response schema; semantic checks run after parsing."""

    model_config = ConfigDict(extra="forbid")
    items: list[DraftItem]


class Provider(Protocol):
    """The sole network-capable boundary for optional drafting."""

    def draft(self, system_prompt: str, request: dict[str, Any]) -> Draft: ...


class AnthropicProvider:
    """Anthropic structured-output adapter, constructed only after opt-in."""

    def __init__(self, model: str = MODEL) -> None:
        self.model = model

    def draft(self, system_prompt: str, request: dict[str, Any]) -> Draft:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise PackWithheld("ANTHROPIC_API_KEY is not configured")
        from anthropic import Anthropic

        response = Anthropic().messages.parse(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        request, sort_keys=True, separators=(",", ":")
                    ),
                }
            ],
            output_format=Draft,
        )
        if response.parsed_output is None:
            raise PackWithheld("provider returned no structured draft")
        return cast(Draft, response.parsed_output)


@dataclass(frozen=True)
class Evidence:
    id: str
    label: str
    value: str
    unit: dict[str, Any]
    sign: str
    citations: tuple[dict[str, Any], ...]

    def request_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "sign": self.sign,
            "citations": list(self.citations),
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _numeric(value: object) -> bool:
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _evidence(summary: Mapping[str, Any]) -> dict[str, Evidence]:
    result: dict[str, Evidence] = {}
    for bridge in summary.get("bridges", []):
        if not isinstance(bridge, dict):
            raise PackWithheld("invalid bridge entry in JSON")
        for line in bridge.get("lines", []):
            if not isinstance(line, dict):
                raise PackWithheld("invalid bridge line in JSON")
            amount = line.get("result", {})
            if not isinstance(amount, dict) or amount.get("status") != "value":
                continue
            if not _numeric(amount.get("value")) or not amount.get("citations"):
                raise PackWithheld("bridge value has no cited JSON evidence")
            key = f"bridge:{bridge['id']}:{line['id']}"
            if key in result:
                raise PackWithheld(f"duplicate evidence id {key}")
            result[key] = Evidence(
                id=key,
                label=str(line.get("label", key)),
                value=str(amount["value"]),
                unit=dict(amount.get("unit", {})),
                sign=str(amount.get("sign", line.get("sign", ""))),
                citations=tuple(amount["citations"]),
            )
    return result


def _flag_ids(summary: Mapping[str, Any]) -> set[str]:
    return {str(item["id"]) for item in summary["flags"] if isinstance(item, dict)}


def _condition_holds(
    condition: Mapping[str, Any], summary: Mapping[str, Any], flags: set[str]
) -> bool:
    kind = condition.get("kind")
    if kind == "flag_present":
        return bool(flags)
    if kind == "missing_template":
        template = condition.get("template")
        return any(
            isinstance(item, dict) and item.get("missing_template") == template
            for item in summary.get("affected_detail", [])
        )
    if kind == "nonzero_either":
        conditions = summary.get("reported_conditions", {})
        if not isinstance(conditions, dict):
            return False
        record = conditions.get(condition.get("condition_id"))
        if not isinstance(record, dict):
            return False
        values = (record.get("opening"), record.get("closing"))
        try:
            return all(value is not None for value in values) and any(
                Decimal(str(value)) != 0 for value in values
            )
        except (InvalidOperation, TypeError, ValueError):
            return False
    return False


def _filtered_catalogue(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = json.loads((_repo_root() / "prompts" / "catalogue.json").read_text())
    flags = _flag_ids(summary)
    result: dict[str, dict[str, Any]] = {}
    covered: set[str] = set()
    for entry in catalog["entries"]:
        prefixes = entry.get("flag_prefixes", [])
        matched = {flag for flag in flags if any(flag.startswith(p) for p in prefixes)}
        if not matched:
            continue
        conditions = entry.get("conditions", [])
        if not conditions or not all(
            _condition_holds(c, summary, matched) for c in conditions
        ):
            continue
        if not entry.get("artifact") or not entry.get("comparison"):
            raise PackWithheld(f"catalogue entry {entry['id']} has no concrete check")
        result[entry["id"]] = entry
        covered.update(matched)
    uncovered = flags - covered
    if uncovered:
        raise PackWithheld(
            "material flags lack a specific catalogue check: "
            + ", ".join(sorted(uncovered))
        )
    return result


def _preflight(summary: Mapping[str, Any]) -> None:
    gate = summary.get("gate", {})
    if not isinstance(gate, dict) or gate.get("status") != "pass":
        raise PackWithheld("comparability gate did not pass")
    validation = summary.get("citation_validation", {})
    if not isinstance(validation, dict) or validation.get("status") != "pass":
        raise PackWithheld("JSON lacks a passing source citation validation")
    if not isinstance(summary.get("flags"), list):
        raise PackWithheld("JSON lacks deterministic flags")
    if not isinstance(summary.get("abstentions"), list):
        raise PackWithheld("JSON lacks deterministic abstention tags")
    evidence = _evidence(summary)
    for tagged in summary["abstentions"]:
        if not isinstance(tagged, dict) or tagged.get("evidence_id") not in evidence:
            raise PackWithheld("abstention lacks a cited JSON movement reference")
        if not isinstance(tagged.get("consistent_hypotheses"), list):
            raise PackWithheld("abstention lacks consistent hypotheses")


def _request(
    summary: Mapping[str, Any],
    evidence: Mapping[str, Evidence],
    catalogue: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "evidence": [item.request_record() for item in evidence.values()],
        "flags": summary["flags"],
        "abstentions": summary["abstentions"],
        "catalogue": list(catalogue.values()),
    }


def _allowed_number_spans(text: str) -> list[tuple[int, int]]:
    patterns = (CODE, DATE, ARTICLE, TIER)
    return [match.span() for pattern in patterns for match in pattern.finditer(text)]


def _scan_model_text(text: str) -> None:
    if "[" in text or "]" in text:
        raise PackWithheld("model supplied a citation instead of a reference id")
    without_refs = REF.sub("", text)
    allowed = _allowed_number_spans(without_refs)
    for match in NUMBER.finditer(without_refs):
        if not any(a <= match.start() and match.end() <= b for a, b in allowed):
            raise PackWithheld(
                f"model supplied an unreferenced figure: {match.group()}"
            )


def _validate_draft(
    draft: Draft,
    summary: Mapping[str, Any],
    evidence: Mapping[str, Evidence],
    catalogue: Mapping[str, dict[str, Any]],
) -> None:
    known_flags = _flag_ids(summary)
    abstentions = {
        str(item["id"])
        for item in summary["abstentions"]
        if isinstance(item, dict) and "id" in item
    }
    for item in draft.items:
        _scan_model_text(item.text)
        actual_refs = REF.findall(item.text)
        if set(actual_refs) != set(item.reference_ids):
            raise PackWithheld("draft reference list does not match its placeholders")
        if any(ref not in evidence for ref in actual_refs):
            raise PackWithheld("draft refers to an unknown JSON evidence id")
        if item.kind == "fact":
            if not actual_refs:
                raise PackWithheld("fact has no cited figure")
            if CAUSAL.search(item.text):
                raise PackWithheld("fact contains ungrounded causal wording")
            if item.catalogue_id is not None:
                raise PackWithheld("fact cannot claim a catalogue hypothesis")
            continue
        if item.kind == "abstention":
            if item.movement_id not in abstentions:
                raise PackWithheld("draft abstention is not tagged in JSON")
            if SPLIT.search(item.text):
                raise PackWithheld("draft allocated a share to an abstention")
            continue
        if item.catalogue_id not in catalogue:
            raise PackWithheld(
                "draft selected a missing or contradicted catalogue item"
            )
        assert item.catalogue_id is not None
        entry = catalogue[item.catalogue_id]
        matched = {
            flag
            for flag in known_flags
            if any(flag.startswith(p) for p in entry["flag_prefixes"])
        }
        if not item.flag_ids or not set(item.flag_ids) <= matched:
            raise PackWithheld("draft catalogue item has no matching reported flag")
        if not all(_condition_holds(c, summary, matched) for c in entry["conditions"]):
            raise PackWithheld("draft selected an item contradicted by reported facts")
        if item.kind == "verification_check" and (
            not entry.get("artifact") or not entry.get("comparison")
        ):
            raise PackWithheld("verification check has no artefact and comparison")


def _citation(cite: Mapping[str, Any]) -> str:
    period = cite.get("period", "?")
    template = cite.get("template", cite.get("sheet", "?"))
    row = cite.get("row", cite.get("metadata_field", "?"))
    column = cite.get("column", "value")
    context = cite.get("coordinate_context") or cite.get("context_id")
    base = f"[{period} | {template} | {row} | {column}]"
    return f"{base} ({context})" if context else base


def _display(evidence: Evidence) -> str:
    unit = evidence.unit
    value = evidence.value
    if unit.get("kind") == "money":
        return f"{value} {unit.get('currency', '')}".strip()
    if unit.get("kind") == "percentage_points":
        return f"{value} percentage points"
    return value


def _add_referenced(
    paragraph: Any, text: str, evidence: Mapping[str, Evidence]
) -> None:
    cursor = 0
    for match in REF.finditer(text):
        paragraph.add_run(text[cursor : match.start()])
        item = evidence[match.group(1)]
        citation = "; ".join(_citation(c) for c in item.citations)
        run = paragraph.add_run(f"{_display(item)} {citation}")
        run.style = "Evidence Reference"
        cursor = match.end()
    paragraph.add_run(text[cursor:])


def _check_rendered_numbers(document: WordDocument) -> None:
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.style and run.style.name == "Evidence Reference":
                continue
            _scan_model_text(run.text)


def _render(
    summary: Mapping[str, Any],
    draft: Draft,
    evidence: Mapping[str, Evidence],
    catalogue: Mapping[str, dict[str, Any]],
    path: Path,
) -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9)
    normal.paragraph_format.space_after = Pt(4)
    title_style = document.styles["Title"]
    title_style.font.color.rgb = RGBColor(0, 0, 0)
    title_properties = title_style._element.get_or_add_pPr()
    title_border = title_properties.find(qn("w:pBdr"))
    if title_border is not None:
        title_properties.remove(title_border)
    for name in ("Heading 1", "Heading 2"):
        document.styles[name].font.color.rgb = RGBColor(0, 0, 0)
    document.styles.add_style("Evidence Reference", 2)
    document.add_paragraph("Pre-Sign-Off Challenge Pack", style="Title")
    document.add_paragraph(
        "Reported movements and specific questions for actuarial sign off. "
        "The cited observations below do not establish the causes of a movement."
    )

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("What moved", []),
        ("Triage questions", []),
        ("Hypotheses", []),
        ("Follow up checks", []),
    ]
    by_kind = {name: items for name, items in sections}
    for item in draft.items:
        if item.kind == "fact":
            by_kind["What moved"].append((item.text, ""))
        elif item.kind == "triage_question":
            entry = catalogue[item.catalogue_id or ""]
            by_kind["Triage questions"].append(
                (entry["question"], ", ".join(item.flag_ids))
            )
        elif item.kind == "hypothesis":
            entry = catalogue[item.catalogue_id or ""]
            for hypothesis in entry["hypotheses"]:
                by_kind["Hypotheses"].append((hypothesis, ""))
    for entry in catalogue.values():
        by_kind["Follow up checks"].append(
            (f"{entry['artifact']}: {entry['comparison']}", "")
        )

    for tagged in summary["abstentions"]:
        movement = str(tagged.get("id", ""))
        evidence_id = str(tagged["evidence_id"])
        hypotheses = tagged.get("consistent_hypotheses", [])
        sentence = (
            f"{movement}: {{ref:{evidence_id}}}. "
            "Insufficient evidence in QRT snapshots to attribute "
            "this movement. "
            f"Consistent hypotheses: {'; '.join(str(h) for h in hypotheses)}."
        )
        by_kind["Hypotheses"].append((sentence, ""))

    budgets = {
        "What moved": 900,
        "Triage questions": 450,
        "Hypotheses": 550,
        "Follow up checks": 550,
    }
    appendix: list[tuple[str, str, str]] = []
    for heading, items in sections:
        if not items:
            continue
        body_items: list[str] = []
        section_chars = 0
        seen: set[tuple[str, str]] = set()
        for text, flags in items:
            if (text, flags) in seen:
                continue
            seen.add((text, flags))
            prefix = (
                "Hypothesis (not verifiable from QRT snapshots): "
                if heading == "Hypotheses" and "Insufficient evidence" not in text
                else "Abstention: "
                if heading == "Hypotheses"
                else ""
            )
            content = prefix + text + (f" Flags: {flags}." if flags else "")
            if section_chars + len(content) > budgets[heading]:
                appendix.append((heading, text, flags))
                continue
            body_items.append(content)
            section_chars += len(content)
        if not body_items:
            continue
        document.add_heading(heading, level=1)
        for content in body_items:
            paragraph = document.add_paragraph()
            _add_referenced(paragraph, content, evidence)
    if appendix:
        paragraph = document.add_paragraph()
        paragraph.add_run().add_break(WD_BREAK.PAGE)
        document.add_heading("Appendix", level=1)
        for heading, text, flags in appendix:
            paragraph = document.add_paragraph()
            label = (
                "Hypothesis (not verifiable from QRT snapshots)"
                if heading == "Hypotheses" and "Insufficient evidence" not in text
                else "Abstention"
                if heading == "Hypotheses"
                else heading
            )
            content = f"{label}: {text}" + (f" Flags: {flags}." if flags else "")
            _add_referenced(paragraph, content, evidence)
    _check_rendered_numbers(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".pending.docx")
    document.save(staged)
    staged.replace(path)


def create_pack(
    summary_path: Path, path: Path, provider: Provider | None = None
) -> None:
    """Produce a Word pack only after every source and drafting gate passes."""
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    _preflight(summary)
    evidence = _evidence(summary)
    catalogue = _filtered_catalogue(summary)
    request = _request(summary, evidence, catalogue)
    prompt = (_repo_root() / "prompts" / "challenge_pack_system.md").read_text()
    selected = provider or AnthropicProvider()
    draft = selected.draft(prompt, request)
    _validate_draft(draft, summary, evidence, catalogue)
    _render(summary, draft, evidence, catalogue, path)
