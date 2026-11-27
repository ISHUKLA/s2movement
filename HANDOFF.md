# s2movement handoff

This folder is a copy of the complete working repository, including uncommitted work, Git history, official reference files and the frozen benchmark. It was copied on 26 November 2026 at the owner's request.

## Start here

Read `AGENTS.md`, `docs/progress.md`, `docs/spec.md` Revision 2, `docs/decisions.md`, `docs/architecture.md` and `mappings/VERIFICATION.md`. The reviewed spec governs the original user story. The recent acceptance work is recorded at the end of progress and decisions.

The latest session implements and verifies R-019–R-021 and D5. It covers the gross S.25.01 SCR bridge, independent S.26 drill-down schedules, the S.23.01 headline fallback, exact rational own-funds/SCR/interaction effects, cited positive-SCR validations, formula notes and live Excel guards. New acceptance tests are `tests/test_scr_ratio_requirements.py` and `tests/test_scr_ratio_workbook.py`.

## Set up and verify

Run `make setup` and then `make check` in this folder. The Python version is pinned to 3.12; uv and the lockfile manage the environment. Formula tests require LibreOffice 26.2.5.2. The network-isolation tests require macOS `sandbox-exec`. The copied folder intentionally has no `.venv`; create its own environment instead of using an environment from the original path.

Final `make check` passed in the original working folder. All 20 frozen files and the locked environment matched, Ruff lint and formatting passed (42 files), strict mypy passed (40 source files), and pytest reported:

```text
350 passed in 521.34s (0:08:41)
```

This includes real LibreOffice recalculation, live raw-value edits, all four D5 scenarios, 504 exact-rational property cases, missing/zero/negative SCR validation, repeatability and network isolation. The copied source files were checked byte for byte against the original after completion. `COPY_SHA256SUMS` records the handoff snapshot. The copied folder now has its own locked environment. Its full `make check` passed with `350 passed in 510.99s (0:08:30)` after the approved SCR citation correction.

## Open work and evidence

- The broader release is unfinished. Flags, commentary and remaining release/sign-off work are recorded in `docs/progress.md`. Follow the owner's next request.
- The frozen benchmark and thresholds must not be changed without owner approval. Its manifest SHA-256 is `a04c5fd95b37c78142e19a9e417584a92ab5dc6a4168e97fa7d6cdcf2e63c6c4`.
- Frozen SCR citation expectations use net modules; the officially verified additive equation uses gross modules plus signed LAC-TP. Numeric frozen SCR and ratio bridge expectations agree. See `mappings/VERIFICATION.md` and progress for the citation discrepancy and arithmetic.
- Previously documented consistency-status and restricted-Tier-1 expectation differences remain open. Full release scoring is not a green release claim.
- Original first-slice sample inputs lack SCR. Their smoke tests now require CLI status 1 with explicit missing-SCR validation results, while preserving the independently usable excess bridge.

## Git and copy details

Remote: https://github.com/ISHUKLA/s2movement.git

The latest local commit is `e8b438e` (`Step 0.0: repository scaffold`). Later work remains uncommitted and unpushed. All those working-tree files are included here. Do not reset or clean this tree: that would discard the work. No new commit or push was requested in this handoff.

Original folder: `/Users/coralieroland/Documents/Codex/2026-11-24/this-is-the-first-session-in`.

This copy: `/Users/coralieroland/Documents/s2movement-handoff-2026-11-26`.

The copy includes `reference/` source downloads and their manifest. It excludes the machine-specific environment, caches, `.env` and prior output artifacts. The `private/` and `output/` folders contain only their README files.

## 26 November owner-approved SCR citation correction

The owner approved correcting frozen SCR citations only in this handoff copy. The independent oracle and six answer keys now cite gross S.25.01.01.01 C0040 modules. The source workbooks, values, signs and thresholds remain unchanged. The new benchmark manifest is `eb073b5d400ad380d518bcb40ede0cd6e5ae5aa160d0f419bf76d8987e78a044`; `tests/fixtures/SIGNOFF.md` records the old and new checksums, approval and arithmetic. Integrity and 34 focused tests passed. This correction does not complete the R-022–R-024 flags, citation validator or release scoring. `mappings/VERIFICATION.md` §7 still says the exact pre-tax SCR expression for the LAC-DT flag is unverified; resolve this before assigning a numerical result. The original repository folder was not edited.

The owner also explicitly approved the R-024 pre-tax SCR arithmetic measure: S.25.01 final SCR R0220/C0100 minus signed LAC-DT R0150/C0100. `docs/decisions.md` records this choice. Implement it as a derived, cited measure; do not present it as a separately reported cell.

This folder was moved to the top level of Documents at the owner’s request. Run `uv sync --locked --group dev` here before `make check` so the copied environment points to this location.

## XBRL adapter preparation and mapping gap

The approved XBRL plan was investigated in this Documents repository. The official EIOPA 2.8.2 taxonomy ZIP with external files is stored in ignored `reference/` and recorded in `reference/manifest.csv` with SHA-256 `a5090b571a8fc2b4297fa39d6bdb5498baa61a78add2b2ee95944dbfbbc39980`. Arelle 2.47.5 is pinned in `pyproject.toml`/`uv.lock`. `make fetch-taxonomy` is an explicit download-and-check command outside the deterministic core. Arelle loaded EIOPA's random annual solo example offline with zero load errors.

The XBRL adapter remains open because 1,375 supervisory cells in `mappings/2.8.2/cells.csv` lack complete data-point signatures. In frozen case 1, 484 of 1,176 mapped workbook facts lack one. S.12.01 and S.25.01 are affected. The prototype was removed after it failed to establish equivalent ledger coverage; XBRL and mixed inputs now fail clearly. Extend the official mapping before enabling them. See `docs/progress.md` and `docs/decisions.md` for the exact evidence and test status. Do not infer a signature from a metric alone.

The final `make check` for this preparation passed: frozen files verified, offline lockfile check clean, Ruff and strict mypy clean, and `353 passed in 454.52s (0:07:34)`. The full suite was run with LibreOffice process permission; within the file sandbox, LibreOffice aborted its recalc subprocesses. `make fetch-taxonomy` checksum-verified the downloaded ZIP. The setup test is independent of the ignored ZIP, so a clean checkout can run `make check` without fetching it.

## Optional commentary preparation · 27 November 2026

The owner requested R-025–R-030 and R-037, then selected Anthropic Sonnet. The handoff copy now has an opt-in `--challenge-pack` path, the system prompt in `prompts/challenge_pack_system.md`, a condition-filtered check catalogue, offline recorded-response safety tests and a Word renderer. It uses `claude-sonnet-4-6` through Anthropic structured outputs. `docs/commentary.md` documents the request projection, numeric gate and body-page measurement. The deterministic workbook and JSON remain unchanged when the option is off, on, or withheld by a failed gate.

The current deterministic JSON lacks R-022 citation validation, R-023/R-024 flags and deterministic abstention tags. The optional path therefore withholds before an API request on the six current benchmark packages. The owner has no Anthropic API key yet. No live model run or R-034 release score was claimed. Complete those JSON prerequisites and configure `ANTHROPIC_API_KEY` before live scoring. The full offline `make check` passed **367 tests in 453.01s (0:07:33)** after the commentary work; the Word sample was rendered and visually inspected. The original repository folder remains untouched.
