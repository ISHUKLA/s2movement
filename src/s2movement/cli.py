"""Offline command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from s2movement.engine import analyze
from s2movement.normalized import InputError, load_ledger
from s2movement.output import write_outputs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s2movement",
        description="Reconcile two normalized Solvency II reporting periods.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser(
        "compare", help="write a cited Excel bridge and JSON summary"
    )
    compare.add_argument("first", type=Path, help="first supplied filing")
    compare.add_argument("second", type=Path, help="second supplied filing")
    compare.add_argument("--output-dir", type=Path, default=Path("output"))
    compare.add_argument(
        "--confirmations",
        type=Path,
        help="reviewer-confirmed scale conversions in JSON",
    )
    compare.add_argument(
        "--corrections",
        type=Path,
        help="source-evidenced metadata corrections in JSON",
    )
    compare.add_argument(
        "--challenge-pack",
        action="store_true",
        help="opt in to sending cited summary figures to Anthropic for a Word draft",
    )
    compare.add_argument(
        "--commentary-model",
        default="claude-sonnet-4-6",
        help="Anthropic model ID used only with --challenge-pack",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command != "compare":
        return 2
    try:
        kinds = {path.suffix.lower() for path in (arguments.first, arguments.second)}
        if kinds == {".xbrl"}:
            raise InputError(
                "XBRL input is blocked until the EIOPA metric/dimension mapping "
                "covers every required ledger cell; see docs/progress.md"
            )
        elif kinds == {".xlsx"}:
            ledger = load_ledger(
                arguments.first,
                arguments.second,
                confirmation_path=arguments.confirmations,
                correction_path=arguments.corrections,
            )
        elif kinds == {".xbrl", ".xlsx"}:
            raise InputError(
                "mixed XBRL/workbook pairs have not passed the R-001 equivalence "
                "test; supply both periods in one format"
            )
        else:
            ledger = load_ledger(
                arguments.first,
                arguments.second,
                confirmation_path=arguments.confirmations,
                correction_path=arguments.corrections,
            )
        analysis = analyze(ledger)
        workbook_path = arguments.output_dir / "reconciliation.xlsx"
        json_path = arguments.output_dir / "summary.json"
        write_outputs(analysis, workbook_path, json_path)
    except (InputError, OSError, ValueError) as exc:
        print(f"s2movement: {exc}", file=sys.stderr)
        return 2
    print(f"Workbook: {workbook_path}")
    print(f"JSON: {json_path}")
    commentary_failed = False
    if arguments.challenge_pack:
        from s2movement.commentary import (
            AnthropicProvider,
            PackWithheld,
            create_pack,
        )

        pack_path = arguments.output_dir / "pre-sign-off-challenge-pack.docx"
        status_path = arguments.output_dir / "challenge-pack-status.json"
        try:
            create_pack(
                json_path,
                pack_path,
                AnthropicProvider(arguments.commentary_model),
            )
            status = {"status": "delivered", "model": arguments.commentary_model}
            print(f"Challenge pack: {pack_path}")
        except PackWithheld as exc:
            pack_path.unlink(missing_ok=True)
            status = {"status": "withheld", "reason": str(exc)}
            commentary_failed = True
            print(f"Challenge pack withheld: {exc}")
        except Exception as exc:
            pack_path.unlink(missing_ok=True)
            status = {
                "status": "withheld",
                "reason": f"provider or document error: {type(exc).__name__}",
            }
            commentary_failed = True
            print(f"Challenge pack withheld: {status['reason']}")
        status_path.write_text(json.dumps(status, sort_keys=True) + "\n")
    print(f"Gate: {analysis.gate.status}; bridge: {analysis.bridge.status}")
    for finding in analysis.gate.findings:
        if finding.status in ("blocked", "warning"):
            print(f"{finding.status}: {finding.message}")
    for check in analysis.comparisons:
        if check.status == "fail":
            print(f"Reconciliation failure ({check.id}): {check.message}")
    for validation in analysis.ratio_validations:
        if validation.status == "fail":
            print(f"Validation failure ({validation.id}): {validation.message}")
    for bridge in analysis.bridges:
        if bridge.residual_status == "fail":
            value = bridge.residual_discrepancy.value
            assert value is not None
            print(
                f"Reconciliation failure ({bridge.definition.id}): "
                f"signed residual {value:+f}, tolerance {bridge.tolerance.value} "
                f"{bridge.tolerance.currency}."
            )
    if analysis.gate.status == "blocked" or any(
        b.status == "fail" for b in analysis.bridges
    ):
        return 1
    if any(item.status == "fail" for item in analysis.comparisons):
        return 1
    if any(item.status == "fail" for item in analysis.ratio_validations):
        return 1
    return 3 if commentary_failed else 0
