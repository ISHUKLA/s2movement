"""Offline acceptance gates for R-025–R-030 and R-037 commentary."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from s2movement.cli import main
from s2movement.commentary import (
    AnthropicProvider,
    Draft,
    PackWithheld,
    _scan_model_text,
    create_pack,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tests" / "fixtures" / "packages" / "1"


class RecordedProvider:
    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer
        self.requests: list[dict[str, Any]] = []

    def draft(self, system_prompt: str, request: dict[str, Any]) -> Draft:
        assert "Head of Actuarial Function" in system_prompt
        self.requests.append(request)
        return Draft.model_validate(self.answer)


def summary() -> dict[str, Any]:
    cite = {
        "period": "closing",
        "template": "S.02.01",
        "row": "R0220",
        "column": "C0010",
        "context_id": "linked",
        "sheet": "S.02.01",
        "cell": "B19",
    }
    return {
        "schema_version": "0.1",
        "gate": {"status": "pass"},
        "citation_validation": {"status": "pass"},
        "flags": [
            {
                "id": "movement_money/S.02.01.01.01/R0220/C0010",
                "status": "fired",
                "citations": [cite],
            }
        ],
        "abstentions": [
            {
                "id": "linked_assets_movement",
                "evidence_id": "bridge:excess:linked_assets",
                "consistent_hypotheses": ["fund returns", "net subscriptions"],
            }
        ],
        "reported_conditions": {
            "reported_foreseeable_dividends": {"opening": "0", "closing": "0"}
        },
        "bridges": [
            {
                "id": "excess",
                "lines": [
                    {
                        "id": "linked_assets",
                        "label": "Linked assets movement",
                        "result": {
                            "status": "value",
                            "value": "120000000",
                            "unit": {"kind": "money", "currency": "EUR", "scale": "1"},
                            "sign": "increase",
                            "citations": [cite],
                        },
                    }
                ],
            }
        ],
        "affected_detail": [],
    }


def good_answer() -> dict[str, Any]:
    flag = "movement_money/S.02.01.01.01/R0220/C0010"
    return {
        "items": [
            {
                "kind": "fact",
                "text": "Linked assets moved by {ref:bridge:excess:linked_assets}.",
                "reference_ids": ["bridge:excess:linked_assets"],
                "catalogue_id": None,
                "flag_ids": [flag],
            },
            {
                "kind": "triage_question",
                "text": "Review the linked movement together.",
                "reference_ids": [],
                "catalogue_id": "linked_fund_movement",
                "flag_ids": [flag],
            },
            {
                "kind": "hypothesis",
                "text": "Possible fund returns and flows.",
                "reference_ids": [],
                "catalogue_id": "linked_fund_movement",
                "flag_ids": [flag],
            },
            {
                "kind": "verification_check",
                "text": "Compare the unit-fund report.",
                "reference_ids": [],
                "catalogue_id": "linked_fund_movement",
                "flag_ids": [flag],
            },
        ]
    }


def write_summary(tmp_path: Path, content: dict[str, Any]) -> Path:
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_R027_scan_distinguishes_codes_dates_and_articles_from_figures() -> None:
    _scan_model_text(
        "S.23.01.01.01 R0540/C0010 at 2025-12-31 under Article 82(3), Tier 3"
    )
    with pytest.raises(PackWithheld, match="unreferenced figure"):
        _scan_model_text("The amount rose by 12%.")


def test_R025_request_is_only_cited_json_evidence_and_filtered_catalogue(
    tmp_path: Path,
) -> None:
    source = summary()
    provider = RecordedProvider(good_answer())
    path = tmp_path / "pack.docx"
    create_pack(write_summary(tmp_path, source), path, provider)
    assert path.is_file()
    request = provider.requests[0]
    assert request["flags"] == source["flags"]
    assert request["abstentions"] == source["abstentions"]
    assert request["evidence"] == [
        {
            "id": "bridge:excess:linked_assets",
            "label": source["bridges"][0]["lines"][0]["label"],
            "value": source["bridges"][0]["lines"][0]["result"]["value"],
            "unit": source["bridges"][0]["lines"][0]["result"]["unit"],
            "sign": source["bridges"][0]["lines"][0]["result"]["sign"],
            "citations": source["bridges"][0]["lines"][0]["result"]["citations"],
        }
    ]
    assert {entry["id"] for entry in request["catalogue"]} == {
        "balance_sheet_movement",
        "linked_fund_movement",
    }
    book = Document(path)
    text = "\n".join(p.text for p in book.paragraphs)
    assert "Pre-Sign-Off Challenge Pack" in text
    assert "120000000 EUR [closing | S.02.01 | R0220 | C0010]" in text
    assert "Hypothesis (not verifiable from QRT snapshots)" in text
    assert "Insufficient evidence in QRT snapshots to attribute this movement" in text
    assert "unit-fund attribution report" in text


def test_R025_anthropic_sdk_receives_only_the_json_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = summary()
    expected = RecordedProvider(good_answer())
    create_pack(write_summary(tmp_path, source), tmp_path / "expected.docx", expected)
    captured: dict[str, Any] = {}

    class FakeMessages:
        def parse(self, **kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(parsed_output=Draft.model_validate(good_answer()))

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-test-only")
    monkeypatch.setattr("anthropic.Anthropic", FakeClient)
    create_pack(
        write_summary(tmp_path, source),
        tmp_path / "actual.docx",
        AnthropicProvider(),
    )
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["output_format"] is Draft
    assert json.loads(captured["messages"][0]["content"]) == expected.requests[0]
    assert "Head of Actuarial Function" in captured["system"]


def test_R030_every_material_flag_gets_a_catalogue_check_without_model_selection(
    tmp_path: Path,
) -> None:
    answer = good_answer()
    answer["items"] = [item for item in answer["items"] if item["kind"] == "fact"]
    path = tmp_path / "pack.docx"
    create_pack(write_summary(tmp_path, summary()), path, RecordedProvider(answer))
    text = "\n".join(p.text for p in Document(path).paragraphs)
    assert "unit-fund attribution report" in text

    unknown = summary()
    unknown["flags"].append({"id": "unmapped_material_flag", "status": "fired"})
    provider = RecordedProvider(answer)
    with pytest.raises(PackWithheld, match="lack a specific catalogue check"):
        create_pack(write_summary(tmp_path, unknown), path, provider)
    assert not provider.requests


@pytest.mark.parametrize(
    "change,reason",
    [
        ("invented_number", "unreferenced figure"),
        ("mismatched_citation", "model supplied a citation"),
        ("causal_fact", "causal wording"),
        ("contradicted_hypothesis", "contradicted catalogue"),
        ("percentage_split", "unreferenced figure"),
        ("artefact_free_check", "contradicted catalogue"),
    ],
)
def test_R027_R028_R029_R030_R037_adversarial_recordings_are_withheld(
    tmp_path: Path, change: str, reason: str
) -> None:
    answer = good_answer()
    item = answer["items"][0]
    if change == "invented_number":
        item["text"] = "Linked assets increased by 999 EUR."
        item["reference_ids"] = []
    elif change == "mismatched_citation":
        item["text"] += " [opening | S.02.01 | R0220 | C0010]"
    elif change == "causal_fact":
        item["text"] += " This was driven by fund returns."
    elif change == "contradicted_hypothesis":
        item = answer["items"][2]
        item["catalogue_id"] = "foreseeable_dividend_change"
    elif change == "percentage_split":
        answer["items"].append(
            {
                "kind": "abstention",
                "text": "40% came from fund returns.",
                "reference_ids": [],
                "movement_id": "linked_assets_movement",
            }
        )
    else:
        item = answer["items"][3]
        item["catalogue_id"] = None
    provider = RecordedProvider(answer)
    path = tmp_path / "pack.docx"
    with pytest.raises(PackWithheld, match=reason):
        create_pack(write_summary(tmp_path, summary()), path, provider)
    assert not path.exists()


def test_R025_default_and_withheld_option_leave_deterministic_outputs_equal(
    tmp_path: Path,
) -> None:
    off = tmp_path / "off"
    on = tmp_path / "on"
    args = [
        "compare",
        str(PACKAGE / "opening.xlsx"),
        str(PACKAGE / "closing.xlsx"),
    ]
    assert main([*args, "--output-dir", str(off)]) == 0
    assert main([*args, "--output-dir", str(on), "--challenge-pack"]) == 3
    assert (off / "summary.json").read_bytes() == (on / "summary.json").read_bytes()
    left = load_workbook(off / "reconciliation.xlsx", data_only=False)
    right = load_workbook(on / "reconciliation.xlsx", data_only=False)
    assert left.sheetnames == right.sheetnames
    for name in left.sheetnames:
        assert list(left[name].values) == list(right[name].values)
    assert not (on / "pre-sign-off-challenge-pack.docx").exists()
    assert (
        "source citation validation" in (on / "challenge-pack-status.json").read_text()
    )


def test_R025_failed_scope_gate_withholds_pack_without_changing_outputs(
    tmp_path: Path,
) -> None:
    package = ROOT / "tests" / "fixtures" / "packages" / "2a"
    off = tmp_path / "off"
    on = tmp_path / "on"
    args = [
        "compare",
        str(package / "opening.xlsx"),
        str(package / "closing.xlsx"),
    ]
    assert main([*args, "--output-dir", str(off)]) == 1
    assert main([*args, "--output-dir", str(on), "--challenge-pack"]) == 1
    assert (off / "summary.json").read_bytes() == (on / "summary.json").read_bytes()
    left = load_workbook(off / "reconciliation.xlsx", data_only=False)
    right = load_workbook(on / "reconciliation.xlsx", data_only=False)
    for name in left.sheetnames:
        assert list(left[name].values) == list(right[name].values)
    assert not (on / "pre-sign-off-challenge-pack.docx").exists()
    assert (
        "comparability gate did not pass"
        in (on / "challenge-pack-status.json").read_text()
    )


def test_R026_joint_question_names_the_related_reported_measures(
    tmp_path: Path,
) -> None:
    source = summary()
    source["flags"] = [
        {"id": "lac_dt_direction/opposite", "status": "fired"},
        {"id": "tier_constraints/closing_tier3", "status": "fired"},
    ]
    answer = {
        "items": [
            {
                "kind": "triage_question",
                "text": "Review these flags together.",
                "reference_ids": [],
                "catalogue_id": "tax_capacity",
                "flag_ids": [
                    "lac_dt_direction/opposite",
                    "tier_constraints/closing_tier3",
                ],
            }
        ]
    }
    path = tmp_path / "pack.docx"
    create_pack(write_summary(tmp_path, source), path, RecordedProvider(answer))
    text = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    joint = "deferred-tax balance, LAC-DT adjustment and binding tier limit"
    assert text.count(joint) == 1
    assert "lac_dt_direction/opposite" in text
    assert "tier_constraints/closing_tier3" in text


def test_R026_word_body_is_at_most_two_rendered_pages(tmp_path: Path) -> None:
    soffice = shutil.which("soffice")
    assert soffice, "LibreOffice is required"
    answer = good_answer()
    for index in range(55):
        label = chr(65 + index // 26) + chr(65 + index % 26)
        answer["items"].append(
            {
                "kind": "fact",
                "text": (
                    f"Linked assets observation {label} moved by "
                    "{ref:bridge:excess:linked_assets}."
                ),
                "reference_ids": ["bridge:excess:linked_assets"],
                "catalogue_id": None,
                "flag_ids": ["movement_money/S.02.01.01.01/R0220/C0010"],
            }
        )
    path = tmp_path / "pack.docx"
    create_pack(write_summary(tmp_path, summary()), path, RecordedProvider(answer))
    converted = tmp_path / "pdf"
    converted.mkdir()
    profile = tmp_path / "lo-profile"
    run = subprocess.run(
        [
            soffice,
            "--headless",
            "--norestore",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(converted),
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    pages = PdfReader(converted / "pack.pdf").pages
    page_text = [page.extract_text() for page in pages]
    appendix_page = next(
        (n for n, page in enumerate(page_text, 1) if "Appendix" in page), 0
    )
    body_pages = appendix_page - 1
    assert 1 <= body_pages <= 2
    assert any("Appendix" in page for page in page_text)
