"""Independent integration checks for the R-009–R-011 first slice."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
OPENING = DATA / "opening.xlsx"
CLOSING = DATA / "closing.xlsx"
SOFFICE_VERSION = "LibreOffice 26.2.5.2"
FORBIDDEN_NETWORK_MODULES = {
    "socket",
    "urllib",
    "http",
    "ftplib",
    "requests",
    "httpx",
    "ctypes",
    "cffi",
}


def _run_cli(
    opening: Path,
    closing: Path,
    output_dir: Path,
    corrections: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), env.get("PYTHONPATH", "")))
    command = [
        str(ROOT / ".venv" / "bin" / "s2movement"),
        "compare",
        str(opening),
        str(closing),
        "--output-dir",
        str(output_dir),
    ]
    if corrections is not None:
        command.extend(("--corrections", str(corrections)))
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _outputs(directory: Path) -> tuple[Path, Path]:
    return directory / "reconciliation.xlsx", directory / "summary.json"


def _assert_missing_scr_failure(
    result: subprocess.CompletedProcess[str], directory: Path
) -> None:
    # These original slice inputs contain only excess-of-assets figures, with
    # no SCR. D5 now requires a validation failure while preserving that bridge.
    assert result.returncode == 1, f"{result.stdout}\n{result.stderr}"
    _, path = _outputs(directory)
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["gate"]["status"] == "pass"
    assert summary["bridges"][0]["status"] == "pass"
    assert {v["period"] for v in summary["ratio_validations"]} == {"opening", "closing"}
    for validation in summary["ratio_validations"]:
        assert validation["status"] == "fail"
        assert validation["input"]["status"] == "unavailable"
        assert validation["input"]["value"] is None
        assert validation["citations"]
        assert f"Validation failure ({validation['id']})" in result.stdout
    ratio = next(b for b in summary["bridges"] if b["id"] == "solvency_ratio")
    assert all(line["result"]["status"] == "withheld" for line in ratio["lines"])


def _find_raw_row(workbook: Any, row_code: str) -> int:
    sheet = workbook["Raw_closing"]
    for row_number in range(2, sheet.max_row + 1):
        if sheet.cell(row_number, 4).value == row_code:
            return row_number
    raise AssertionError(f"raw row {row_code} not found")


def _recalculate(source: Path, destination: Path) -> Path:
    soffice = shutil.which("soffice")
    assert soffice is not None, (
        "LibreOffice is required for R-010 formula recalculation tests"
    )
    version = subprocess.run(
        [soffice, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert SOFFICE_VERSION in version, f"expected {SOFFICE_VERSION}; found {version!r}"
    destination.mkdir(parents=True, exist_ok=True)
    profile = destination / "lo-profile"
    command = [
        soffice,
        "--headless",
        "--norestore",
        "--nodefault",
        "--nofirststartwizard",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to",
        "xlsx:Calc MS Excel 2007 XML",
        "--outdir",
        str(destination),
        str(source),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    recalculated = destination / source.name
    assert result.returncode == 0, (
        f"LibreOffice failed: {result.stdout}\n{result.stderr}"
    )
    assert recalculated.is_file(), f"LibreOffice did not produce {recalculated}"
    return recalculated


def _number(value: Any) -> Decimal | Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Decimal(str(value))
    return value


def _formula_results(path: Path) -> dict[tuple[str, str], Any]:
    formulas = load_workbook(path, data_only=False, read_only=False)
    values = load_workbook(path, data_only=True, read_only=False)
    results: dict[tuple[str, str], Any] = {}
    try:
        for sheet in formulas.sheetnames:
            for row in formulas[sheet].iter_rows():
                for cell in row:
                    if cell.data_type != "f":
                        continue
                    calculated = values[sheet][cell.coordinate]
                    assert calculated.value is not None, (
                        f"missing formula cache at {sheet}!{cell.coordinate}"
                    )
                    assert calculated.data_type != "e", (
                        f"formula error at {sheet}!{cell.coordinate}"
                    )
                    results[(sheet, cell.coordinate)] = _number(calculated.value)
    finally:
        formulas.close()
        values.close()
    return results


def _cell_snapshot(path: Path) -> tuple[tuple[Any, ...], ...]:
    formulas = load_workbook(path, data_only=False, read_only=False)
    values = load_workbook(path, data_only=True, read_only=False)
    snapshot: list[tuple[Any, ...]] = []
    try:
        for sheet_name in formulas.sheetnames:
            formula_sheet = formulas[sheet_name]
            value_sheet = values[sheet_name]
            snapshot.append(("sheet", sheet_name))
            for row in formula_sheet.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    cached = (
                        value_sheet[cell.coordinate].value
                        if cell.data_type == "f"
                        else cell.value
                    )
                    snapshot.append(
                        (
                            sheet_name,
                            cell.coordinate,
                            cell.data_type,
                            _number(cell.value),
                            _number(cached),
                            cell.number_format,
                            cell.style_id,
                        )
                    )
    finally:
        formulas.close()
        values.close()
    return tuple(snapshot)


def _edit_template_cell(path: Path, sheet_name: str, row_code: str, value: int) -> None:
    workbook = load_workbook(path)
    try:
        sheet = workbook[sheet_name]
        matching_rows = [
            row_number
            for row_number in range(1, sheet.max_row + 1)
            if sheet.cell(row_number, 1).value == row_code
        ]
        assert len(matching_rows) == 1
        sheet.cell(matching_rows[0], 2).value = value
        workbook.save(path)
    finally:
        workbook.close()


def _edit_metadata_field(path: Path, name: str, value: str) -> None:
    workbook = load_workbook(path)
    try:
        sheet = workbook["Metadata"]
        rows = [
            row_number
            for row_number in range(2, sheet.max_row + 1)
            if sheet.cell(row_number, 1).value == name
        ]
        assert len(rows) == 1
        sheet.cell(rows[0], 2).value = value
        workbook.save(path)
    finally:
        workbook.close()


def _bridge_values(path: Path) -> dict[str, tuple[Any, Any]]:
    workbook = load_workbook(path, data_only=True)
    try:
        sheet = workbook["Bridge"]
        result: dict[str, tuple[Any, Any]] = {}
        expected = {
            "opening_excess",
            "investments_movement",
            "linked_assets_movement",
            "other_assets_movement",
            "liabilities_contribution",
            "residual",
            "closing_excess",
        }
        for row in range(5, sheet.max_row + 1):
            line_id = sheet.cell(row, 1).value
            if isinstance(line_id, str) and line_id in expected:
                result[line_id] = (
                    sheet.cell(row, 3).value,
                    sheet.cell(row, 4).value,
                )
        return result
    finally:
        workbook.close()


def test_R010_recalculation_matches_every_python_formula_result(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    result = _run_cli(OPENING, CLOSING, output_dir)
    _assert_missing_scr_failure(result, output_dir)
    workbook_path, _ = _outputs(output_dir)
    python_results = _formula_results(workbook_path)
    assert python_results
    recalculated_path = _recalculate(workbook_path, tmp_path / "recalculated")
    formula_workbook = load_workbook(recalculated_path, data_only=False)
    try:
        formula_count = sum(
            cell.data_type == "f"
            for sheet in formula_workbook.worksheets
            for row in sheet.iter_rows()
            for cell in row
        )
    finally:
        formula_workbook.close()
    assert formula_count == len(python_results), (
        "LibreOffice replaced or dropped formula cells"
    )
    recalculated_results = _formula_results(recalculated_path)
    assert recalculated_results == python_results


def test_R010_live_formulas_update_liability_and_residual(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    result = _run_cli(OPENING, CLOSING, output_dir)
    _assert_missing_scr_failure(result, output_dir)
    workbook_path, _ = _outputs(output_dir)
    formulas = load_workbook(workbook_path, data_only=False)
    try:
        raw_row = _find_raw_row(formulas, "R0900")
        formulas["Raw_closing"].cell(raw_row, 13).value = 770
        changed = tmp_path / "changed.xlsx"
        formulas.save(changed)
    finally:
        formulas.close()
    recalculated = _recalculate(changed, tmp_path / "changed-recalculated")
    lines = _bridge_values(recalculated)
    assert lines["liabilities_contribution"] == (-70, "value")
    assert lines["residual"] == (20, "fail")
    assert lines["investments_movement"] == (20, "value")
    assert lines["linked_assets_movement"] == (10, "value")
    assert lines["other_assets_movement"] == (50, "value")
    assert lines["closing_excess"] == (330, "value")


def test_R011_visible_break_stays_on_residual_line(tmp_path: Path) -> None:
    closing = tmp_path / "closing-break.xlsx"
    shutil.copyfile(CLOSING, closing)
    _edit_template_cell(closing, "S.02.01", "R1000", 340)
    _edit_template_cell(closing, "S.23.01", "R0700", 340)
    output_dir = tmp_path / "output"
    result = _run_cli(OPENING, closing, output_dir)
    assert result.returncode == 1, result.stderr
    workbook_path, json_path = _outputs(output_dir)
    lines = _bridge_values(workbook_path)
    assert lines["residual"] == (10, "fail")
    assert lines["investments_movement"] == (20, "value")
    assert lines["linked_assets_movement"] == (10, "value")
    assert lines["other_assets_movement"] == (50, "value")
    assert lines["liabilities_contribution"] == (-50, "value")
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["bridges"][0]["residual_check"]["status"] == "fail"
    assert (
        summary["bridges"][0]["residual_check"]["signed_discrepancy"]["value"] == "10"
    )


def test_R011_failed_cross_template_check_withholds_dependent_movements(
    tmp_path: Path,
) -> None:
    closing = tmp_path / "closing-mismatch.xlsx"
    shutil.copyfile(CLOSING, closing)
    _edit_template_cell(closing, "S.23.01", "R0700", 328)
    output_dir = tmp_path / "output"
    result = _run_cli(OPENING, closing, output_dir)
    assert result.returncode == 1, result.stderr
    workbook_path, json_path = _outputs(output_dir)
    lines = _bridge_values(workbook_path)
    for line_id in (
        "investments_movement",
        "linked_assets_movement",
        "other_assets_movement",
        "liabilities_contribution",
        "residual",
    ):
        assert lines[line_id][1] == "withheld"
    assert lines["residual"][0].startswith("Withheld:")
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["comparisons"][1]["signed_discrepancy"]["value"] == "2"
    assert summary["comparisons"][1]["status"] == "fail"


def test_D2_source_evidenced_metadata_correction_reruns_the_gate(
    tmp_path: Path,
) -> None:
    closing = tmp_path / "closing-group.xlsx"
    shutil.copyfile(CLOSING, closing)
    _edit_metadata_field(closing, "perimeter", "group")
    blocked = _run_cli(OPENING, closing, tmp_path / "blocked")
    assert blocked.returncode == 1
    assert "Gate: blocked" in blocked.stdout

    corrections_path = tmp_path / "corrections.json"
    corrections_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corrections": [
                    {
                        "period": "closing",
                        "file_id": closing.name,
                        "field": "perimeter",
                        "original_value": "group",
                        "corrected_value": "solo",
                        "reason": "The source filing confirms solo scope.",
                        "reviewer": "test reviewer",
                        "evidence": "Synthetic source evidence item 1",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    corrected = _run_cli(OPENING, closing, tmp_path / "corrected", corrections_path)
    _assert_missing_scr_failure(corrected, tmp_path / "corrected")
    _, json_path = _outputs(tmp_path / "corrected")
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    perimeter = next(
        item
        for item in summary["metadata"]
        if item["period"] == "closing" and item["name"] == "perimeter"
    )
    assert perimeter["reported_value"] == "group"
    assert perimeter["value"] == "solo"
    assert perimeter["correction"]["reviewer"] == "test reviewer"
    assert summary["gate"]["corrections"][0]["evidence"] == (
        "Synthetic source evidence item 1"
    )
    assert all(
        line["result"]["status"] == "value"
        for line in summary["bridges"][0]["lines"]
        if line["role"] == "movement"
    )


def test_R009_repeatable_json_and_workbook_cells(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    result_one = _run_cli(OPENING, CLOSING, first)
    result_two = _run_cli(OPENING, CLOSING, second)
    _assert_missing_scr_failure(result_one, first)
    _assert_missing_scr_failure(result_two, second)
    workbook_one, json_one = _outputs(first)
    workbook_two, json_two = _outputs(second)
    assert json_one.read_bytes() == json_two.read_bytes()
    assert _cell_snapshot(workbook_one) == _cell_snapshot(workbook_two)


def test_R022_json_citations_preserve_source_locator_and_context(
    tmp_path: Path,
) -> None:
    result = _run_cli(OPENING, CLOSING, tmp_path / "output")
    _assert_missing_scr_failure(result, tmp_path / "output")
    _, json_path = _outputs(tmp_path / "output")
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    investments = next(
        line
        for line in summary["bridges"][0]["lines"]
        if line["id"] == "investments_movement"
    )
    citations = investments["result"]["citations"]
    assert len(citations) == 2
    assert {item["period"] for item in citations} == {"opening", "closing"}
    for citation in citations:
        assert citation["template"] == "S.02.01"
        assert citation["table"] == "S.02.01.01.01"
        assert citation["row"] == "R0070"
        assert citation["column"] == "C0010"
        assert citation["dimensions"] == {
            "s2c_BL": "s2c_x91",
            "s2c_VG": "s2c_x80",
        }
        assert citation["context_id"] == "investments"
        assert citation["file_id"] in {OPENING.name, CLOSING.name}
        assert len(citation["sha256"]) == 64
        assert citation["sheet"] == "S.02.01"
        assert citation["cell"].startswith("B")


def test_R009_core_does_not_import_network_or_raw_socket_modules() -> None:
    for path in sorted((ROOT / "src" / "s2movement").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            else:
                continue
            imported_roots = {module.split(".", maxsplit=1)[0] for module in modules}
            forbidden = imported_roots & FORBIDDEN_NETWORK_MODULES
            assert not forbidden, (
                f"{path} imports forbidden network/native modules: {forbidden}"
            )


def _network_audit_sitecustomize(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sitecustomize.py"
    path.write_text(
        "import os, sys\n"
        "def _audit(event, args):\n"
        "    network = {'socket.connect', 'socket.connect_ex',\n"
        "               'socket.getaddrinfo', 'socket.sendto'}\n"
        "    process = {'subprocess.Popen', 'os.system', 'os.posix_spawn',\n"
        "               'os.spawn', 'os.exec', 'os.fork'}\n"
        "    if event in network or event in process:\n"
        "        target = os.environ['S2_MOVEMENT_NETWORK_AUDIT']\n"
        "        with open(target, 'a', encoding='utf-8') as stream:\n"
        "            stream.write(event + '\\n')\n"
        "        forbid_process = os.environ.get(\n"
        "            'S2_MOVEMENT_FORBID_CHILD_PROCESSES'\n"
        "        ) == '1'\n"
        "        if event in network or forbid_process:\n"
        "            raise RuntimeError('network access or child process attempted')\n"
        "sys.addaudithook(_audit)\n",
        encoding="utf-8",
    )
    return path


def _sandbox_command(command: list[str]) -> list[str]:
    sandbox = shutil.which("sandbox-exec")
    assert sandbox is not None, (
        "macOS sandbox-exec is required for the R-009 network-isolation test"
    )
    return [sandbox, "-p", "(version 1) (allow default) (deny network*)", *command]


def test_R009_network_guard_observes_python_subprocess_and_blocks_native_calls(
    tmp_path: Path,
) -> None:
    assert sys.platform == "darwin", (
        "the R-009 network test requires the verified macOS sandbox backend"
    )
    site_dir = tmp_path / "site"
    _network_audit_sitecustomize(site_dir)
    audit_log = tmp_path / "network-attempts.log"
    env = os.environ.copy()
    env["S2_MOVEMENT_NETWORK_AUDIT"] = str(audit_log)
    env["PYTHONPATH"] = os.pathsep.join((str(site_dir), str(ROOT / "src")))

    standard_probe = subprocess.run(
        _sandbox_command(
            [
                sys.executable,
                "-c",
                "import socket; "
                "socket.create_connection(('127.0.0.1', 9), timeout=0.1)",
            ]
        ),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert standard_probe.returncode != 0
    assert "socket." in audit_log.read_text(encoding="utf-8")

    audit_log.unlink()
    caught_probe = subprocess.run(
        _sandbox_command(
            [
                sys.executable,
                "-c",
                "import socket\n"
                "try: socket.create_connection(('127.0.0.1', 9), timeout=0.1)\n"
                "except BaseException: pass",
            ]
        ),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert caught_probe.returncode == 0
    assert "socket." in audit_log.read_text(encoding="utf-8"), (
        "caught attempts must still fail the audit"
    )

    audit_log.unlink()
    child_probe = subprocess.run(
        _sandbox_command(
            [
                sys.executable,
                "-c",
                "import subprocess, sys; "
                "subprocess.run([sys.executable, '-c', "
                "\"import socket; socket.socket().connect(('127.0.0.1', 9))\"]) ",
            ]
        ),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert child_probe.returncode == 0
    assert "socket." in audit_log.read_text(encoding="utf-8"), (
        "subprocess attempts must be observed"
    )

    native_code = (
        "import ctypes, errno, struct\n"
        "libc = ctypes.CDLL(None, use_errno=True)\n"
        "fd = libc.socket(2, 1, 0)\n"
        "address_bytes = struct.pack('=H', 2) + struct.pack('!H', 9)\n"
        "address_bytes += bytes([127, 0, 0, 1]) + bytes(8)\n"
        "address = ctypes.create_string_buffer(address_bytes)\n"
        "result = libc.connect(fd, address, 16)\n"
        "error = ctypes.get_errno()\n"
        "libc.close(fd)\n"
        "assert result == -1 and error in (errno.EPERM, errno.EACCES), "
        "(result, error)\n"
    )
    native_probe = subprocess.run(
        _sandbox_command([sys.executable, "-c", native_code]),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert native_probe.returncode == 0, native_probe.stderr

    audit_log.unlink(missing_ok=True)
    output_dir = tmp_path / "offline-output"
    env["S2_MOVEMENT_FORBID_CHILD_PROCESSES"] = "1"
    app = subprocess.run(
        _sandbox_command(
            [
                str(ROOT / ".venv" / "bin" / "s2movement"),
                "compare",
                str(OPENING),
                str(CLOSING),
                "--output-dir",
                str(output_dir),
            ]
        ),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    _assert_missing_scr_failure(app, output_dir)
    assert not audit_log.exists(), (
        "the deterministic CLI attempted network access: "
        f"{audit_log.read_text(encoding='utf-8')}"
    )
    assert all(path.is_file() for path in _outputs(output_dir))
