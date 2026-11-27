# Session prompts for specification Revision 3

Prepared 27 November 2026 for the current build in `/Users/coralieroland/Documents/s2movement-handoff-2026-11-26`. This document is a sequence to execute later, not a claim that its sessions have run. The original repository folder is not the implementation target.

On 27 November 2026 the owner explicitly approved the recommended D11–D22 basis, retaining exact Excel builds and new numerical tolerances as approval gates before dependent work. The owner separately chose **“Required before v1 release”** for the AoC practising-actuary trial. These answers are recorded with their actual wording in `docs/decisions.md` and supersede the earlier pending decision labels in the unchanged Revision 3 specification. This is the approved basis for this sequence, not approval of a release, benchmark answer key or actual provider transmission. R-055 continues to block an unresolved numerical method. Independent work can proceed while a dependent approval or external acceptance remains open.

## Approved decisions and remaining execution conditions

| Decision | Approved basis | Condition before dependent execution/acceptance |
| --- | --- | --- |
| D11 | Microsoft 365 desktop Mac and Windows; minimum is the earliest exact build certified by the harness. | Owner/release operator identifies the actual machines, builds/channels and operator; record the supported minimums and approval. An untested platform is not supported by assertion. |
| D12 | LibreOffice remains a secondary diagnostic on copies. | Migrate the existing command/pin only in a checked implementation session. It cannot satisfy any Excel gate. |
| D13 | Preserve actual insurer run order; no mandated re-sequencing. | Implement and test the recorded convention. A different proposed order for future insurer runs is a separate decision. |
| D14 | v1 uses insurer-run attribution, conditional Euler allocation and separate observed S.22/S.23 deltas. S.13/curve unwind is v1.1. | Apply the approved feature boundary. Later unwind still needs explicit curve, currency, timing, tail, LTG, coverage and error-budget approval in Session 21. |
| D15 | Euler for reconstructible basic SCR; full reruns for exact step SCR; proxies remain separate. | Verify the actual allocation source/basis and resolve exceptional/zero-aggregation treatment and new engineering bounds before dependent numerical implementation/freeze. |
| D16 | Available own funds by tier with the observed change in eligibility adjustment as a final reconciliation when intermediate full SCR is missing. | Complete stepwise eligibility still needs same-step SCR/classification evidence and D6. Do not reuse an endpoint SCR by default. |
| D17 | Preserve D3 and exact D5 identities; no newly invented allowance. | Approve any new source-precision/irrational-allocation engineering bound or approximation error budget before freezing/using it. Show proposed units, operator and zero/boundary cases. |
| D18 | Separate per-run AoC provider permission in addition to QRT commentary permission; minimized evidence projection. | Record the permitted scope and actual consent for each live run. Credential availability does not grant AoC transmission permission. |
| D19 | S.29.03/S.29.04 cross-check only, subject to verified comparable mapping. | Complete source verification; otherwise keep them present/not used and the dependent cross-check unavailable. Preserve the original signed benchmark's behavior. |
| D20 | v1 includes Excel-certified insurer-input AoC and the optional safe pack; v1.1 adds approximate unwind/broader automation. | Apply the recorded release scope. Do not move an unfinished mandatory v1 feature to v1.1 merely to pass. |
| D21 | Both the original triage trial and a separate eight-reviewer AoC balanced crossover must pass before v1 release; AoC median reduction at least 35%, with tool detection at least Excel by defect class. | Independently author and separately sign the fresh task/cases/key, run real reviewers, and obtain owner sign-off on actual times/counts/outcome. These results cannot be supplied by an agent. |
| D22 | Literal-only normalized inputs; reject all financial numeric text and all input formulas. | Implement the approved policy; native Excel numbers/dates and schema-defined identifiers remain distinct. |

Session 1 turns these recorded answers into a short execution register. Do not ask the owner to approve D11–D22 again. Collect the exact targets/evidence still needed and present only unresolved parameters or changed scope at the session that depends on them. Exact Excel machines/builds/channels/operator, new numerical bounds/exceptional cases and the detailed future approximation basis remain explicit gates, as approved; no number or human result is invented here.

## How to use the sequence

Start a fresh session and paste one complete prompt block. Each block names the goal, requirements, allowed files, tests first, stop conditions and exit gate. Read its result, use the repair prompt if needed, and use the close-out prompt only after its exit gate passes. After three unsuccessful repairs of the same gate, stop, show the evidence and split the session or resolve the specification; do not weaken a test or threshold.

The following common constraints are also repeated in each prompt where essential:

- Work on the existing build. Preserve existing usable paths; do not replace failures with placeholders or rebuild the project from scratch. A new incomplete capability must fail explicitly or remain unavailable, not silently appear complete.
- Read the 27 November owner approval in `docs/decisions.md` as the answers to Revision 3's earlier pending D11–D22 table. Verify that record instead of requesting the same choices again. A newly required numerical parameter still needs a concrete proposal and approval before dependent implementation/freeze.
- The original frozen population is `tests/fixtures/packages/`, `thresholds.yaml`, `SHA256SUMS` and `SIGNOFF.md`. Verify its current manifest `eb073b5d400ad380d518bcb40ede0cd6e5ae5aa160d0f419bf76d8987e78a044` against the current recorded approval, rather than assuming it forever. Also preserve the existing frozen trial materials. Only the benchmark-correction prompt can authorize a change to a signed population.
- The deterministic core is offline. Acquisition of taxonomy, curves and regulatory files is an explicit setup operation. No provider call, telemetry or download is introduced into comparison, validation or workbook recalculation logic.
- Every financial number is ledger-backed; Decimal money and exact-rational D5 identities retain units/signs/precision. Live formulas, explicit residuals, unavailable/withheld/indeterminate results and D2's two stop-clearing routes remain mandatory.
- New regression tests outside a frozen population may be written before product changes. Freeze changes need owner approval; a repaired product never generates its own oracle. All secrets, real figures and confidential evidence stay out of Git and terminal output. Stage only the authorized files at close-out.

### Gates used in every prompt

**L — local build:** run `make check` and record the exact command, exit status, actual summary/counts, and anything not run in `docs/progress.md`. Do not copy a previous session's green result. A green local build is distinct from the diagnostic release score. The present baseline has 367 tests but later counts may change legitimately.

**E — Microsoft Excel:** run the implemented `make check-excel` for the exact changed candidate and its affected dependencies. The named owner/release operator runs this on each approved Excel platform/build. If the agent machine has the required Excel, the agent can run the harness locally under that operator's responsibility; otherwise supply a hashed **synthetic/public** candidate bundle, command and expected-value manifest for the operator to run. The operator returns the full manifest, cell comparisons, observations, saved copies and checksums. The maintainer verifies candidate/build/decision hashes and commits the permitted evidence under `docs/release-evidence/excel/<candidate>/<platform-build>/`, recording its path/result in progress. Confidential evidence remains in `private/` with a nonconfidential reference/hash. No Excel installation or returned evidence means **E OPEN**, never passed or skipped-as-pass. A failed Excel result stays failed even when LibreOffice passes. Baseline/harness-only sessions explicitly limit what E certifies.

**I — independent oracle:** an authoring session must not read/import `src/`, call the product or derive expected values from its output. It seals and hashes its candidate before any product score. A **separate source-aware maintainer session** runs L against that sealed candidate and returns the actual log/commit/fingerprint to the authoring handoff; the independent author does not run `make check`, which imports product code. The exit gate still requires that external L record plus the author's independent integrity/arithmetic checks. Missing external verification stays open. This separation resolves the otherwise conflicting requirements of source-independent authoring and a checked repository. No scored run is permitted until the owner signs the applicable answer key/thresholds/manifest. An integrity check is not sign-off.

**R — release:** all applicable automated, Excel and independent-review gates pass, and both the original triage trial and the separate AoC trial pass with owner-signed actual results before v1 release. No tag, push, demo or publishing follows automatically from a green test command.

### Why there are more sessions than the suggested thirteen

The release report shows unfinished R-022/R-023/R-024 and XBRL work, so sessions 5–8 repair these prerequisites explicitly. Contract design is separated from adapter implementation so the source-independent oracle can be built between them. Expected values are frozen before feature scoring rather than authored after seeing the feature's outputs. Independent review precedes the human trial/release decision. The v1.1 approximation has its own decisions, oracle and release checks after the v1 gate.

## v1 sessions

### Session 1 — Baseline and execution register

```text
Goal: establish the current working baseline and the decisions actually recorded. Do not implement features.
R-IDs: R-001–R-055 as an inventory; verification focus R-009, R-031–R-036, R-053, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, docs/spec.md Revision 3 in full, docs/decisions.md, docs/progress.md, docs/architecture.md and docs/release-report.md. Work in the handoff copy. Read the explicit 27 November owner approval in decisions.md as the answers to the spec's older pending D11–D22 table.
Allowed files: docs/progress.md and docs/decisions.md for an execution register; this prompt sequence only to reconcile approved sequencing changes. Do not change product, tests, mappings, dependencies or frozen populations.
Tests first: verify the frozen manifests and record git status/content fingerprint; run the existing make check. Compare its actual result with the historical report, without running a new scored benchmark before required sign-off. List existing failures, including validator/flags/XBRL/commentary gaps and unresolved source evidence.
Create the execution register from the approved D11–D22 answers, naming remaining exact parameters, dependent sessions and evidence/operator needed. Include both triage and AoC trials as mandatory v1 gates. Collect installed Excel build information if available; it is a candidate, not a certified minimum. Keep API credentials unread and unused in this session.
Stop and ask only for consequential unresolved parameters needed immediately or a baseline failure that prevents useful progress. Do not ask for these approved policy choices again, or invent a build, new allowance, human result or benchmark sign-off.
Exit gate: L passes and the actual result, fingerprint, blockers and first runnable next session are recorded in progress. If L fails, use the repair prompt before feature work. E is not required for this read-only baseline and remains unmeasured.
```

### Session 2 — Excel acceptance harness and evidence exchange

```text
Goal: add a trustworthy Microsoft 365 Excel acceptance harness before changing the writer.
R-IDs: R-009, R-010, R-022, R-038, R-039, R-041, R-053, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, the complete Revision 3 spec, decisions, progress, architecture and release report. Check D11/D12 and the execution register. Use the current build; preserve frozen data.
Allowed files: new scripts/excel_acceptance/ and its tests; Makefile; AGENTS.md Commands section only; docs/architecture.md, docs/decisions.md, docs/progress.md and synthetic evidence under docs/release-evidence/excel/. No production calculation changes.
Tests first: positive numeric/text/status toy workbooks and negative missing-cache, changed-formula, wrong-cache, external-link, macro-part, inserted-@, circular-reference and precision-as-displayed cases. Test missing Excel, wrong build, incomplete/tampered evidence and a repaired/suppressed-warning open as failures or open gates. Expected toy results are independent arithmetic.
Implement normal open with observable alerts, CalculateFull and completion detection, cache/expected comparisons, formula representations, settings/error scans, Excel save/close/reopen and tool re-read. Record the full R-041 manifest, cell-comparison CSV, observations and hashes. Provide the operator command and verified evidence-import route for remote Mac/Windows machines. Do not use LibreOffice to fill production caches. Keep any harness automation macros outside deliverables.
Stop for absent platform/build/operator approval, an unsupported Excel automation operation or an unexplained formula difference. Build portable evidence-validation parts while an external run is pending.
Exit gate: L plus E on harness positive/negative toys, with operator/build and evidence path in progress. Record current production-workbook failures separately for Session 3; toy certification must not claim product acceptance.
```

### Session 3 — Writer compatibility, caches and live calculations

```text
Goal: make the current production workbooks pass Microsoft Excel and preserve auditable live formulas.
R-IDs: R-009–R-011, R-022, R-038, R-039, R-041, R-049.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec, decisions, progress, architecture, release report and Session 2 evidence. Use approved Excel settings and unchanged D3/D5 tolerances.
Allowed files: src/s2movement/output.py and narrowly necessary expression/compiler helpers; writer/recalculation regression tests outside frozen populations; harness compatibility fixes; relevant docs, Makefile and AGENTS.md Commands only if commands change; Excel evidence. No financial redefinition or frozen answer edits.
Tests first: original XlsxWriter output opens without repair/link/macro warnings; every numeric/text/status cache exists and agrees after full Excel recalculation and save/re-read; no errors, @ insertion, circularity, lost formula or precision setting change. Cover formulas under unavailable/withheld states, exact zero ratio identities, source-scale conversions and repeatability. Edit a copied raw amount and independently predict its dependent line/residual change. Test that calculated coarser-precision tolerances remain formula-traceable, rather than pasted results.
Retain direct explicit Python-computed XlsxWriter caches unless evidence justifies a supported change. The current CLI does not save through LibreOffice: do not invent that diagnosis or add such a production pass. Repair XML/formula compatibility from evidence, retaining the same numerical meaning.
Stop on any change that alters a financial method, required tolerance or source interpretation. Do not waive a repair prompt or overwrite an original specimen.
Exit gate: L and E for all current output families and affected formula dependencies. The owner/release operator runs E on the approved matrix; import its hashed bundle and record actual results/paths in progress. Other unfinished release requirements remain explicit.
```

### Session 4 — Excel-authored normalized input

```text
Goal: read actual Excel-authored/saved normalized QRT inputs safely, with explicit rejection diagnostics.
R-IDs: R-001, R-004–R-009, R-022, R-040, R-041, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec including the input-rejection table, decisions, progress, architecture/input-format and the release report. Apply approved D22: native numeric cells and schema-defined text, literal-only financial inputs; reject all financial numeric text and all input formulas, never infer locale.
Allowed files: normalized adapter/models and related CLI validation; new Excel compatibility specimens/tests under tests/data/excel_compat/; input-format/architecture/decisions/progress docs and E evidence. Do not alter frozen benchmark inputs or relax scope gates.
Tests first: real Excel-saved shared/inline strings, 1900/1904 epochs, ISO/native dates, hidden/very-hidden sheets, local/external defined names and comma/dot UI locales. Exercise every specified rejection: ambiguous numeric text, other financial text per D22, formulas with/without caches, #N/A/errors, active/external content, invalid/time/leap-day dates, Boolean/nonfinite/range/precision failures, duplicate/overlapping/ambiguous coordinates and unreadable/encrypted/wrong-format containers. Assert exact locator/reason/remedy and no silent zero. Test reversed/equal/non-successive dates and D2 conversions/corrections still behave correctly.
Keep original source types/values and source locations. Input-literal policy must not prevent the separate output verifier from reading generated formulas.
Stop if a proposed parse changes a number by locale, a numeric/text policy is unapproved or date evidence is ambiguous.
Exit gate: L and E for Excel-origin specimens and resulting outputs. The approved operator authors/saves specimens and runs E; import hashes and cell comparisons into release-evidence and record actual results in progress.
```

### Session 5 — Source evidence and missing mapping dependencies

```text
Goal: complete the verified evidence needed by the existing product and approved AoC analyses. This session writes data/documentation, not financial tool code.
R-IDs: R-002, R-004, R-008, R-013, R-018, R-022, R-045–R-047, R-051, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report and mappings/VERIFICATION.md. Preserve original frozen expected values. Official sources, never remembered codes, govern the evidence inventory.
Allowed files: versioned mapping/reference catalogues, mappings/VERIFICATION.md, reference/manifest.csv, source-acquisition scripts if necessary, independent data-integrity tests outside frozen populations, and relevant docs. Large official downloads remain ignored. No src/ feature changes.
Tests first: catalogue keys/variants/context uniqueness, source locators/hashes, signs/bases/subtotal membership and legal operator integrity. Create explicit evidence-gap records for unverified cells or equations.
Verify current reconciliation and tier questions; complete required metric/dimension signatures for XBRL; source the applicable Standard Formula aggregation/matrix, module gross/net/portfolio basis and basic-SCR reconstruction operands. Under approved D19 verify S.29.03/.04 comparison scope. Do not populate S.13/curve data for v1 under the approved release split. Record exact version/date/location/checksum in the committed reference manifest. New acquisitions are explicit setup work, never a deterministic-run fetch.
Stop when an ambiguity changes a reported number. Show the conflicting source passages and the arithmetic. Restricted Tier 1 stays indeterminate while its reporting treatment is unresolved. A disagreement with the frozen key requires the benchmark-correction process, not an edit here.
Exit gate: L plus independent source/catalogue integrity checks, actual results and unresolved scope in progress. E is not required for data-only work; no generated workbook or unverified mapping is certified by this session.
```

### Session 6 — Complete citation validation and repair core output leaks

```text
Goal: make R-022 a real final gate for every deterministic output path and retain explicit supported detail.
R-IDs: R-007–R-011, R-016, R-022, R-033, R-039.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report and verified mappings. The current writer emits outputs without a final source validator; do not replace this gap with a dummy pass marker.
Allowed files: a new citation-validation module; models/engine/output/CLI and expression helpers as necessary; focused mutation/regression tests outside frozen populations; architecture/progress and Excel evidence. Keep all frozen inputs, thresholds and expected values unchanged.
Tests first: mutate a parsed source value/hash, citation coordinate, period, context, formula, unit, sign and computed result in turn. Include post-parse source replacement and a bogus result retaining plausible citations. Test standalone JSON/workbook and combined output paths, raw facts, metadata, conversions, thresholds and legal bounds. Validation failures must withhold affected outputs and identify the failed figure. Reproduce the legacy five-row balance-sheet fallback: unsupported seven-bucket splits must be explicitly unavailable, not silently omitted under a full R-016 claim.
Validate source facts and every contributing input/expression, then check generated formula references/caches before publication. Keep D2 audit evidence and live tolerance formulas intact. Do not invent a missing subtotal or absorb a reconciliation break.
Stop for an unresolved source equation or a proposed change in accepted financial meaning. Keep unrelated valid results usable.
Exit gate: L and E for all affected output paths, with actual operator/build/cell evidence imported and progress updated. Mutation tests must demonstrate rejection, not just the presence of citation strings.
```

### Session 7 — Deterministic flags, abstentions and complete JSON

```text
Goal: complete the missing deterministic rule and abstention layer before commentary or AoC consumes JSON.
R-IDs: R-006, R-009, R-015, R-018, R-022–R-024, R-029, R-033, R-034, R-037.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report, verified mappings and the frozen rule settings/expected files. Use Session 6's validator on every output path. Do not alter the frozen settings to make a rule fire.
Allowed files: new declarative rule catalogue/engine, models/engine/CLI/output integration; rule tests using the existing mutation helper in new temporary variants; commentary JSON-contract docs, architecture/progress and affected Excel evidence. No frozen key/manifest edits.
Tests first: for every rule, isolated positive/control patterns and both sides/equality of the threshold; repeat a boundary with a changed user setting. Include zero bases, signed LAC-DT/pre-tax comparison, all three tier limits, LTG shifts, linked movement differences and accounting premiums written/claims incurred. Use the specifically recorded owner-approved pre-tax measure, not a guessed substitute. Test every seeded ambiguous movement and false abstentions on accounted movements.
Record rule ID, inputs/citations, units/sign/denominator/equality/zero policy, settings used and factual messages. Never describe S.05 accounting figures as cash receipts/payments. Complete flags, abstention tags and real citation-validation results in JSON. No provider call is permitted.
Stop for an unverified rule basis, unapproved numerical threshold or a substantive expected-value disagreement. Show evidence and arithmetic without changing the key.
Exit gate: L; independent rule/abstention expectations pass for supported scope. E for workbook flags/settings/results the approved operator tests, imported with hashes and actual outcomes in progress. Diagnostic release gaps stay reported rather than stubbed.
```

### Session 8 — Finish the offline XBRL adapter

```text
Goal: implement the still-missing R-001 XBRL input path after its mappings are verified, without changing downstream calculations.
R-IDs: R-001–R-009, R-022, R-033.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report and the completed source catalogue. Arelle/taxonomy setup already exists; examine it before selecting replacements. No guessed metric/dimension mapping is permitted.
Allowed files: XBRL adapter and ledger boundary integration, CLI, explicit setup scripts, adapter tests and independent synthetic instances outside the original frozen population; provenance/architecture/input/progress docs and E evidence. Only verified source-backed mapping supplements may be added; do not edit frozen workbooks/keys.
Tests first: published sample loading where applicable, equivalent workbook/XBRL pairs cell-for-cell including context/currency/precision/metadata, both input orders, unsupported release/group/quarterly/Internal Model stops, missing local taxonomy, unplaced/duplicate facts and source-citation validation. Monitor attempted connections with the network blocked; schemas must resolve locally without even a fallback attempt. XBRL decimals is precision, not a lexical scale multiplier. Test a mixed pair against equivalent single-format pairs.
Fill only the same ledger; count and list unplaced facts. Missing local taxonomy produces a clear error directing explicit setup. Refuse mixed pairs unless equivalence is demonstrated and the supported behavior recorded. Existing gate/bridge/flag outputs must remain equal for equivalent inputs.
Stop for missing signatures, ambiguous dimensions or unverified metadata. Do not restore a partial adapter that drops required facts.
Exit gate: L with no-network/equivalence tests plus E on equivalent resulting workbooks by the approved operator. Record actual results and imported evidence paths; no XBRL acceptance claim while required equivalence is open.
```

### Session 9 — AoC input contract and acceptance design

```text
Goal: define a stable AoC input/ledger contract before the independent benchmark is authored. Write documentation, not an adapter.
R-IDs: R-042–R-044, R-047–R-050, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md and the full Revision 3 spec, decisions, progress, architecture and release report. Apply approved D13–D18/D22. Identify any remaining new numerical parameter/exceptional-case treatment needed for the contract; do not silently select it.
Allowed files: docs/aoc-input-format.md, the AoC extension in docs/architecture.md, docs/decisions.md and docs/progress.md. No src/, tests, mappings, prompt or frozen-data changes in this design session.
Tests first: specify the acceptance matrix for literal/native Excel types, field/segment/run identities, independently supplied starts/ends or a resolvable start run, actual order/repeated categories, branches/cycles/duplicates, scope/currency/sign/precision, missing steps and full/proxy/missing SCR. Define exact expected statuses and diagnostics so a source-independent builder can implement them.
Cover gross BEL/recoverables/RM/whole TP, excess, available/eligible tiers, standalone/basic/diversified SCR and ratio at supported segment granularity. C01/C12 are anchors; C11 is tool-calculated and cannot plug a chain; C10 needs real adjustment evidence. Specify extended run/reference citations and missing-evidence propagation. No delta-only oracle or guessed RM guarantee split.
Stop and present a concrete proposal with independent examples and numerical consequences for any new D17 bound or exceptional allocation treatment that remains unresolved. Do not re-open approved D16. Continue unrelated schema detail; keep the dependent part visibly pending.
Exit gate: L plus a documented complete contract/acceptance matrix and decision register in progress. E is not required for this documentation-only session. Session 10 may not freeze expected values for an unresolved numerical convention.
```

### Session 10 — Independent Excel/AoC benchmark, freeze and owner sign-off

```text
Goal: build the new Excel/AoC inputs and expected values independently before product implementation or scoring.
R-IDs: R-031–R-034, R-038–R-052, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

This is a source-independent authoring session: do not read/import src/, product tests, product outputs or the tool's calculation code. Do not run the CLI or make check. Read only AGENTS.md, the full Revision 3 spec, approved decisions, the AoC input contract, official mappings/reference evidence, and the independent benchmark conventions. Read progress/release report only for scope and open decisions, not as a numerical oracle.
Allowed files: a new tests/benchmarks/rev3_excel_aoc/ builder, mutation helper, inputs, expected.yaml/settings, independent arithmetic/integrity tests, SHA256SUMS and SIGNOFF.md; docs/progress.md. The original tests/fixtures/ and existing trial freeze are unchanged. No src/ or product implementation changes.
Tests first: independent rebuild/integrity checks and arithmetic for complete chains, independently stated broken starts, cancelling continuity defects, bad endpoints, each unavailable/withheld path, actual order effects, illegal segment splits, full/proxy/missing SCR, all tier statuses, exact ratio telescoping and Euler reconstruction/mismatch. Include accepted/rejected Excel XML/date/string/hidden/name/error/formula cases and causal/consent adversaries. Use invented names/LEIs. Expected results cite actual independent input cells and reference sources.
Derive expected amounts with plain independent arithmetic. Keep irrational allocation precision/tolerances explicit and approved before freezing; a tool-computed cache is never an answer key. Author new mutation variants outside signed packages. Under approved D21 independently author fresh matched AoC trial inputs and their separated answer key here, with their own manifest/provenance and independent rebuild command. Both methods get identical inputs; retain the approved eight-reviewer crossover, 35% median target and detection-by-defect-class criteria. Do not expose these trial cases as worked examples. Seal/hash candidates and verify two rebuilds. Freeze separate manifests; leave owner answer-key approval blank and stop for the owner to sign the keys, thresholds and checksums. Policy approval is not fixture sign-off; do not backdate or fabricate it.
Stop for an unresolved numerical basis, missing official evidence or absent owner approval of the sealed answer key/settings/checksum. Present the proposed arithmetic and exact approval needed; do not run the product to choose an answer.
Exit gate: I. Run independent checks only; a separate maintainer runs L after sealing and records its actual result/fingerprint in progress. The approved Excel operator authors/saves any required Excel-origin specimens before their final hashes are signed and supplies provenance. No scored run or product-based acceptance test against this key until owner sign-off is recorded. Missing approvals/external L keep the gate open.
```

### Session 11 — AoC adapter, ledger and continuity controls

```text
Goal: ingest the approved AoC workbook into the same ledger and expose validated chain controls in a thin working path.
R-IDs: R-001, R-004–R-010, R-022, R-040, R-042–R-044, R-049, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report, aoc-input-format and the separately signed Session 10 key/manifest. Verify sign-off before any scoring. No oracle edits are permitted.
Allowed files: new aoc_models.py, aoc_input.py and aoc_controls.py; ledger/CLI/engine/output/validator integration; acceptance tests outside signed data; architecture/input/progress docs and E evidence.
Tests first: every schema/identity/context rejection and independently stated continuity break from the signed key, both valid start forms, duplicates/dangling/cyclic pointers, nonsequential branches, repeated categories, unit conversions, metadata mismatches, missing end/run evidence, unsupported segment granularity and delta-only input. Confirm each step's start is checked against an independently supplied preceding end, not manufactured from deltas. Test complete residual versus partial unallocated gap, including a zero partial gap with a missing step.
Keep existing QRT-only behavior usable. Route AoC/reference facts through ledger citation validation. Add an optional AoC input path with actual-order controls, statuses and minimal live control output; missing AoC does not synthesize a causal chain. No provider calls or estimates.
Stop for an unapproved contract/numerical decision or inconsistent signed expected arithmetic. Preserve D2; AoC corrections cannot clear a real entity/currency/perimeter difference.
Exit gate: L, signed contract/control expectations and E on the thin output plus Excel-origin input cases. The approved operator runs E and returns the verified bundle; record exact results/path in progress.
```

### Session 12 — Reported-data schedules and Euler allocation

```text
Goal: add only approved analyses reproducible from reported data; do not estimate insurer causal runs.
R-IDs: R-008, R-014, R-017–R-019, R-022, R-045, R-046, R-049, R-051, R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, full Revision 3 spec/decisions/progress/architecture/release report, verified aggregation/reference data and the separately signed benchmark. Apply approved D14/D15/D19 and verify any new D17 allowance/exceptional-case approval; use only verified basis/allowances. Approximate S.13 unwind belongs after the v1 gate under approved D14/D20.
Allowed files: new reported_analysis.py/reference-ledger support, narrowly necessary expression/output/validator integration and explicit setup scripts; new tests outside signed data; source/progress/architecture docs and E evidence. Mapping additions require official evidence and manifest provenance; no frozen expected edits.
Tests first: independently calculated Euler allocations and their algebraic sum, reconstruction of reported basic SCR, gross/net/portfolio mismatch, missing module/matrix, zero/exceptional aggregation, separately evidenced additive terms, missing/mismatched local reference files and blocked network. Test observed S.22 impacts and S.23 capital/deduction deltas without causal labels. For approved S.29 cross-checks test scope/sign/coverage and isolation from every bridge result.
Keep standalone modules, date allocations and rerun SCR effects distinct. A reconstruction gap stays visible and withholds allocation to the reported total; do not scale contributions to force a tie. Exact reported deltas are not capital transactions or isolated LTG causes. Missing/new unapproved numerical evidence gives unavailable/indeterminate detail.
Stop for a legal/source conflict or an unanswered engineering tolerance/exceptional-case rule. Continue only unaffected observed schedules.
Exit gate: L and signed independent numerical/status tests plus E for all added formulas and live reference-parameter edits. The approved operator returns cell evidence; import it and record actual results in progress. An unrun or failed numerical branch is not complete.
```

### Session 13 — Technical-provision AoC by step and segment

```text
Goal: implement insurer-attributed TP AoC while preserving the reported reconciliation as an independent anchor.
R-IDs: R-007–R-015, R-022, R-042–R-045, R-049.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report, AoC contract, verified mappings and signed independent expected values. Preserve actual run order and all missing-evidence semantics.
Allowed files: new aoc_tp.py; AoC/ledger/expression/engine/output/validator integration; TP acceptance and live-formula tests outside signed data; architecture/progress docs and E evidence. No benchmark/threshold edits.
Tests first: gross BEL, whole TP, recoverables, RM and net subtotals separately for life/health SLT; LoB/guarantee granularity; independently stated starts/ends; opening/closing/QRT/bridge tie-outs; omitted steps; cancelling discontinuities; a deliberate residual; and failed cross-template checks withholding only dependent attribution. Independently prove totals do not double-count net BEL and its components. RM at LoB total must not acquire a guarantee split.
Use insurer-evidenced category steps only. Keep S.22 observed impacts beside the AoC rather than double-count them as C08. Preserve linked asset/liability/RM differences as observed comparisons, never a measured non-unit BEL or attributed cause. An unreported step names the missing run/input; its impact is not zero.
Stop if a source only supports an aggregate, a proposed allocation changes a figure or a signed key conflicts with reproducible arithmetic. Retain the aggregate and unavailable split.
Exit gate: L, matching signed TP expectations and E on generated TP controls/steps, including raw-edit response and a visible break. The approved operator runs/imports E; record actual results and evidence path in progress.
```

### Session 14 — Own-funds AoC and tier eligibility

```text
Goal: explain available-own-funds steps and only the eligible-tier effects justified by same-step evidence.
R-IDs: R-008–R-011, R-016–R-018, R-022, R-042–R-044, R-047, R-049.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report, AoC contract, mapped Article 82 entries and signed expected values. Apply approved D16 and check any new D17 parameter's recorded approval; keep unresolved restricted Tier 1 treatment indeterminate.
Allowed files: new aoc_own_funds.py; tier/ledger/engine/expression/output/validator integration; focused independent acceptance/live-edit tests; relevant docs and E evidence. No signed data changes.
Tests first: dividends/approved capital movements, tax, subordinated/ancillary funds, available tiers, classification changes and supported restrictions; strict/inclusive legal boundaries, source precision and competing limits; full/proxy/missing step SCR. Prove that when full intermediate SCR is absent, the annual eligible change equals available change plus the change in eligible-minus-available adjustment, not the entire closing deduction. Test no accidental splice between available opening and eligible closing levels.
With full evidence, use mapped limits at the same step and cite its SCR. Otherwise show available-tier AoC, separate reported endpoint eligibility and a final observed adjustment-change reconciliation; intermediate eligible-tier conclusions/ratio effects stay unavailable. Do not fill intermediate SCR with an endpoint by default or attribute the final net adjustment to a single unproved limit.
Stop for missing legal/reporting treatment or a new attribution convention. An instrument-to-eligible difference is not evidence of a reclassification amount.
Exit gate: L, matching signed own-funds/limit outcomes and E for both complete and incomplete chains with live threshold-boundary edits. The approved operator supplies verified evidence, recorded with actual results in progress.
```

### Session 15 — Sequential SCR and exact ratio effects

```text
Goal: implement diversified-SCR step impacts and the exact per-step ratio decomposition without confusing them with module allocations.
R-IDs: R-008–R-011, R-019–R-022, R-042–R-044, R-046–R-049.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, full Revision 3 spec/decisions/progress/architecture/release report and the signed AoC key. Apply approved D15/D16 and verify any required new D17 parameter. Reuse the existing D5 method; no Shapley or linear alternative.
Allowed files: new aoc_scr.py/aoc_ratio.py or cohesive equivalent; capital/engine/expression/output/validator integration; acceptance/property/recalculation tests; relevant docs and E evidence. Preserve signed fixtures/settings.
Tests first: full diversified rerun deltas, standalone module changes kept separate, changing diversification/adjustments, proxy/missing SCR, missing/zero/negative SCR at each endpoint, failed reported-ratio checks and incomplete eligible tiers. Use independent rational equations for both inputs moving, E only, S only, neither, and randomized positive complete chains. Assert each three-term identity and telescoping total, including actual order changes.
For adjacent endpoints show 100×deltaE/S_before, 100×E_before×(1/S_after−1/S_before) and 100×deltaE×(1/S_after−1/S_before). Retain exact rational evidence before display rounding. The sum of per-step categories need not equal the single endpoint D5 split; label both definitions. An incomplete/proxy chain never claims complete ratio attribution; retain valid endpoint decomposition and a cited partial gap without allocating missing causes. Invalid SCR is a validation failure, never division error/number.
Stop for an unapproved proxy/tolerance policy or missing step basis.
Exit gate: L, all signed identities/statuses and E on complete/incomplete chains and live SCR/eligible edits. The approved operator runs/imports the cell-level bundle; record actual results/path in progress.
```

### Session 16 — Complete AoC workbook and JSON presentation

```text
Goal: integrate readable live AoC schedules and all tie-outs into the existing review outputs.
R-IDs: R-004, R-007–R-011, R-022, R-038–R-044, R-049.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report and all approved contracts. Use current calculations; do not change their meaning to make a layout tie.
Allowed files: output.py/new aoc_output.py, JSON schema/serializer, narrowly necessary formula/compiler metadata; output/schema/integration tests; architecture/output/progress docs and E evidence. No source-mapping or signed-key changes.
Tests first: every displayed financial cell is a live formula with explicit correct cache and citations; every JSON number retains units/signs/all leaf inputs; actual run order/repeated categories visible; raw AoC/reference provenance/conversions retained; dashboard distinguishes reported reconciliation, insurer attribution, allocation, approximation, unavailable and withheld. Test all four tie-outs, visible residuals and incomplete-zero-gap cases. Compare repeat runs byte-for-byte JSON and workbook cells; test all provider-consent combinations leave deterministic outputs unchanged.
Use separate raw period/AoC/reference tabs and measure/segment AoC schedules with starts, ends, deltas, methods and control discrepancies/tolerances, while retaining the original bridges as independent anchors. Provider/consent timestamps belong in separate audit sidecars. Run the citation validator on every output path before delivery. Test raw edits recalculate dependent lines and control statuses without inserted @, errors or precision drift.
Stop for any missing calculation contract, unexplained formula/cache difference or pressure to paste a result.
Exit gate: L and E for all workbook families, hidden dependencies, native input round-trips and Excel save/re-read. The approved operator returns evidence tied to the exact candidate; record actual results/path in progress.
```

### Session 17 — Safe AoC commentary and separate consent

```text
Goal: repair the current commentary bypasses and add constrained insurer-attributed AoC statements with separate provider permission.
R-IDs: R-009, R-022, R-025–R-030, R-034, R-037, R-050.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report, validated JSON contract and signed adverse cases. Confirm D18. Keep Anthropic behind the existing provider interface unless an approved decision says otherwise. A locally available API key is a credential, not consent to transmit AoC evidence.
Allowed files: commentary module/provider interface, prompts/catalogue and system prompt, optional CLI flags/sidecars; recorded-response/request/Word-rendering tests; commentary/progress docs and evidence. No deterministic financial-method or frozen-key changes.
Tests first: invented digit and word-based figures, a correct number with the wrong measure/sign/citation, causal paraphrases inside facts, contradicted hypotheses inserted through abstention strings, unsupported finer-granularity causes, unlabelled hypotheses, invented percentage splits, scale loss, artefact-free checks and stale/tampered JSON validation. Include positive accepted AoC attribution, all permission combinations and exact deterministic-output invariance. Write body-length/overflow cases: one/two narrative pages accepted, excess moved into the same document's appendix without losing material items, and an overlong body rejected by the Word acceptance measurement.
Make safe claims structural: typed evidence/step IDs, renderer-supplied amounts/units/scale/citations and canonical validated claim templates; arbitrary fact prose cannot acquire a cause merely by containing a valid reference. Recheck every rendered field against catalogue/JSON conditions. A causal sentence attributes only the insurer AoC step at its demonstrated granularity; snapshots/Euler/proxies remain observations or hypotheses. Deterministically render every required abstention. Keep ordinary and AoC permissions separate and audited outside core outputs; denied AoC evidence must not leak through flags, labels or derived values in the request.
Stop for missing real source validation, unmatched catalogue coverage, unapproved provider/consent or unavailable credential. Keep the offline suite working. Request per-run live consent only after the exact minimized request is reviewable; do not print/copy/commit keys.
Exit gate: L, all signed adverse/positive cases, and real Microsoft Word body-length acceptance: the Word-equipped release operator opens/renders the exact DOCX, records Word build, body/appendix page boundaries and candidate/render hashes, and supplies the evidence under docs/release-evidence/word/ for maintainer verification. LibreOffice PDF pagination is secondary. Also require E output-invariance evidence by the approved Excel operator. Run live benchmark commentary only after applicable manifest sign-off and explicit transmission permission; record actual R-034/false-abstention results and withhold misses honestly.
```

### Session 18 — Scorers, trial preparation and candidate release report

```text
Goal: measure the candidate against signed independent keys and prepare fair human-trial materials without altering the judge.
R-IDs: R-009, R-022, R-031–R-041, R-044–R-054.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report and every applicable SIGNOFF.md. Verify owner approval/checksums before any scored run. Check D20/D21 release and trial scope.
Allowed files: new black-box scoring/evidence runners outside the signed oracle, integration tests for scorers using independent toy values, docs/release-report.md/progress.md, permitted synthetic release-evidence and new separately frozen reviewer-trial materials. Do not edit existing or new signed inputs, expected values or thresholds, or the independent builder to follow product output.
Tests first: scorer catches missing bridges/steps, wrong values/signs/citations/units, false pass or missing status, unsupported extra numbers, missing packs, false abstentions and absent/tampered Excel evidence. Test it refuses unsigned/moved manifests. Run identical full inputs twice with network attempts monitored and blocked; compare deterministic JSON and workbook cells.
Score all seven original runs and new signed Excel/AoC runs. Report counts/denominators/thresholds/commands/files, failing as failing. Interpret a source-backed disagreement with the original key as a documented issue requiring the correction prompt, never a waiver. Prepare candidate-versioned delivery copies of the original triage kit from its unchanged input/key; leave the frozen prototype bytes intact and record/obtain approval for the new delivery manifest before use. Obtain new unexposed matched AoC trial cases/key from Session 10 or a separate source-independent authoring handoff; do not author or revise their numerical oracle in this source-aware scorer session. Prepare identical inputs/task under both methods, manual Excel AoC baseline, separated key, blinded scoring and formula-driven timing. Preserve original triage scope; never reuse exposed A/B as new blinded AoC evidence.
Stop for an unsigned key, unapproved trial target or an expected-value disagreement. Human results stay open, not invented.
Exit gate: L and complete measured diagnostic report; E for every scored workbook and trial/diff/scoring book, run by approved operators with imported evidence. Candidate status remains failed/open until all release conditions pass. Record actual results/path in progress; proceed to independent review before declaring release.
```

### Session 19 — Independent recalculation, code review and full Excel run

```text
Goal: obtain an independent check from a reviewer who did not write the implementation, then a full target-Excel acceptance run.
R-IDs: R-001–R-055 for declared v1 scope; focus R-022, R-032–R-034, R-038–R-050, R-052–R-053.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md and the full Revision 3 spec/approved decisions first. During Phase A read only source/input contracts, the benchmark inputs/reference evidence and integrity manifests; defer expected values, progress/results, architecture implementation details and the release report until your arithmetic is sealed. In Phase B read those remaining documents and inspect implementation/tests. Do not change product code, mappings, tests or signed data. Do not trust a preceding green report as your calculation oracle.
Allowed files: an independent review report under docs/reviews/, independent calculation artifacts under permitted release-evidence, and docs/progress.md. Phase A must not read src/ or product outputs: recalculate the signed AoC benchmark directly from its inputs/reference data using separate arithmetic, record controls, signs, allocation basis, tier outcomes and exact ratio identities, then seal/hash those results. Phase B may inspect code/tests and compare outputs with that sealed work; disclose every area not reviewed.
Checks first: validate manifests/signatures and confirm your expected arithmetic is independent. Examine every output path for validator bypass, pasted calculation, silent zero, absorbed residual, widened tolerance, date/scope bypass, unrecorded conversion, unsupported tier/cause/segment conclusion, proxy masquerading as full SCR, consent leak and network attempt. Review tests and builder independence. Report findings by severity with file/line, R-ID and reproduction.
After any repairs are completed in separate sessions, the approved Mac/Windows Excel operators run full E on all original/new scored cases and trial workbook families at the final candidate fingerprint. Inspect opening warnings, every cache/text/status/formula, live edits, precision and save/re-read. Import the complete verified evidence; do not substitute LibreOffice.
Stop for absent reviewer independence, missing source/sign-off, high-severity findings or unreturned Excel evidence. Use repair sessions, then rerun affected and full gates.
Exit gate: L, sealed independent recalculation matches within approved policies, no open high-severity finding, and full E passes. Record actual results/operator/build/evidence in progress. Human sign-off and release authorization remain for Session 20.
```

### Session 20 — Human evidence and v1 release gate

```text
Goal: close only genuinely measured release gates for the approved v1 scope.
R-IDs: R-031–R-036, R-038–R-041, R-052–R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/approved decisions, progress, architecture, release report, all benchmark/trial sign-offs and Session 19 evidence. Check that no code/input change has invalidated the accepted candidate. Do not invent human data or change acceptance targets.
Allowed files: release/progress docs, actual anonymized trial results and owner sign-offs in the approved trial locations, and permitted release-evidence. No product/test/mapping/expected-value changes in this measurement session.
Checks first: verify complete original/new benchmark population, signed thresholds and candidate fingerprints; recompute the timing/scoring workbook on independent toy controls, then validate actual records. Practising actuaries and the trial coordinator perform both mandatory trials. Preserve D9's eight-reviewer triage crossover, first-written-list timing, no feedback and blinded defect classification. Also run the separate D21 eight-reviewer AoC crossover with identical AoC inputs and the manual Excel AoC baseline: require at least 35% median time reduction and tool detection at least Excel separately by each seeded AoC defect class. Report its results separately as AoC utility; neither trial substitutes for the other.
Recompute medians/detection rates from real anonymized observations. Obtain owner sign-off on times/counts/outcome. Update every R-031–R-036 gate and all new applicable gates with actual measures, thresholds and commands/evidence. Missing trials, platforms, decisions or live-model measurements stay open/failing.
Stop if any prerequisite is open or a count cannot be reproduced. A green build is not permission to tag or demonstrate.
Exit gate: L plus final E/evidence import by approved operators, independent-review clearance, and passes with owner-signed actual results for BOTH the original triage trial and the separate AoC trial. Missing either blocks v1 release. Record the actual release decision in progress/report. Request explicit final authorization before a v1 tag, push or public demo. Do not start the v1.1 implementation below before this v1 gate passes.
```

## v1.1 sessions — only after the v1 release gate

Approved D14/D20 place these sessions after the v1 release gate. They cannot bypass an unfinished mandatory v1 requirement. The detailed future proxy basis and any new D17 error/engineering allowance still need concrete approval in Session 21 before oracle freeze or implementation.

### Session 21 — Unwind source verification and numerical proposal

```text
Goal: specify the optional S.13/opening-curve proxy after v1 is accepted, without implementing its numerical algorithm yet.
R-IDs: R-009, R-022, R-040, R-043–R-045, R-049, R-052–R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report and confirm the v1 gate passed. Follow the approved v1.1 scope; do not read a proxy amount back into a v1 exact causal step.
Allowed files: source-backed S.13/reference mapping supplements, reference/manifest.csv, explicit acquisition scripts, docs/unwind-proposal.md, decisions/progress and independent data-integrity tests. No src/ financial implementation or signed-data change.
Tests first: specify independent cases for original-currency coverage, opening as-of/version/checksum, compounding/interpolation/extrapolation, annual timing/grouped tail, VA/MA basis, projection-to-BEL gap, missing inputs and no-network execution. Identify which cases must be unavailable rather than approximated.
Verify official S.13 instructions and exact cells/variants, then propose the curve/timing/tail/LTG convention and approximation error budget in units with equality/zero behavior. The planning candidate is opening original-currency EIOPA basic RFR forward roll and end-year annual timing, with no assumed VA/MA or grouped-tail timing. Present alternatives and numeric examples independently; obtain explicit owner approval before use. Preserve visible gaps and distinguish expected cash flows, discount roll, recoverables and missing RM/SCR projections.
Stop for missing authoritative mapping, mixed-currency/tail information or an unapproved numerical basis. Offline acquisition is explicit; runs never fetch the latest curve.
Exit gate: L plus source-integrity checks and the recorded approved numerical proposal. E is not required for documentation/data-only changes; record its unmeasured status. No proxy acceptance or implementation is claimed.
```

### Session 22 — Independent v1.1 oracle and separate freeze

```text
Goal: build expected unwind/projection values independently after the numerical basis is approved.
R-IDs: R-022, R-032–R-034, R-045, R-049, R-052–R-055.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Do not read/import src/, product tests or product outputs, and do not run the CLI/make check. Read AGENTS.md, full Revision 3 spec, approved decisions/unwind proposal and official source/input contracts. Confirm v1 release and the v1.1 numerical approval.
Allowed files: a new tests/benchmarks/rev3_unwind/ independent builder, source inputs, plain-arithmetic expected values, mutation helper, integrity tests, thresholds, separate manifest/SIGNOFF.md and progress. Do not alter any original or v1 Excel/AoC signed population.
Tests first: positive/negative rates, first-year flow versus roll, gross/recoverable scope, original-currency checks, timing/tail effects, explicit opening PV-to-BEL gap, missing/mismatched curve, absent/unknown projection and rejected substitutions for RM/full SCR. Expectations include approximate labels, exact source citations, mathematical results and approved adequacy thresholds without widening D3.
Derive values from independently read cash flows/discount factors; do not call product interpolation/bridge/curve helpers. Verify rebuilds, seal/hash the candidate and stop for owner sign-off of key, thresholds and checksum. No scored run precedes that signed entry.
Stop for a missing source, unresolved proxy convention or absent owner approval of the new key/settings/checksum. Show the independent arithmetic and keep the dependent score blocked.
Exit gate: I, with independent arithmetic/integrity results and external maintainer L evidence after sealing. Record exact commands/results in progress. Any required Excel-authored source specimen is supplied by the approved operator before final source hashes are signed. Missing sign-off or external gate stays open.
```

### Session 23 — Explicitly approximate unwind implementation

```text
Goal: implement only the approved and independently frozen v1.1 proxy, with visible limits.
R-IDs: R-009–R-011, R-022, R-040, R-043–R-045, R-049–R-050, R-052.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, Revision 3 spec/decisions/progress/architecture/release report, approved unwind proposal and signed v1.1 key. Confirm the v1 release gate and all numerical approvals. Do not reinterpret recommendations as answers.
Allowed files: new projection/curve adapter/calculation modules and ledger/expression/CLI/output/validator integration; tests outside signed data; explicit acquisition helpers and docs; Excel evidence. No signed expected/threshold changes.
Tests first: every signed ordinary/boundary/missing-input case, local reference hash/date/currency enforcement, separate first-year flows/discount roll, opening basis gap, grouped-tail unavailability, and no-network attempted-call monitoring. Assert source/curve/assumption citations and full formula reproducibility. Verify the existing exact v1 AoC is unchanged when the proxy is disabled.
Label every projection result approximate with its approved basis/error budget and gap; retain D3 on actual reconciliation controls. Missing currency/timing/curve evidence remains unavailable, never estimated silently. Do not infer risk-margin release or full SCR from BEL cash flows. Proxy statements cannot acquire the causal authority of insurer model reruns, even with AoC provider consent.
Stop for an unapproved parameter, unexpectedly material approximation gap or signed expected-value disagreement; show independent arithmetic and use the correction process if needed.
Exit gate: L, signed v1.1 expectations and E on all new/live curve-dependent formulas plus v1 regression outputs. Approved Excel operators return full evidence; import hashes and actual results into progress.
```

### Session 24 — Independent v1.1 review and release measurement

```text
Goal: verify the approximate extension independently and measure the full release without borrowing the v1 acceptance result.
R-IDs: R-009, R-022, R-031–R-041, R-045, R-049–R-055 for the declared v1.1 scope.

Read docs/prompting-algorithm-rev3.md for the target folder, protected-population rules and definitions of L/E/I/R. These rules are part of this prompt. L records actual make-check results in progress; where E is required, the approved Excel operator returns the hashed evidence bundle and a maintainer verifies/imports it under docs/release-evidence/excel/ before claiming a pass.

Read AGENTS.md, full Revision 3 spec/approved decisions, source contracts, all sign-offs and the v1.1 proposal. Use a reviewer who did not implement the proxy. Recalculate first without expected values, product outputs, progress/results, implementation architecture or release-report measurements; read those and the code only after sealing your arithmetic. Do not change code, mappings or signed expected values during review.
Allowed files: independent review/calculation and Excel evidence, release/progress docs and actual owner sign-offs. First recalculate the v1.1 key directly from source cash flows/curves without src/ or product outputs, seal those results, then review the code and compare results. Check approximation labels/error budgets, source dates/units/timing, no silent tail/FX/LTG substitution, residual visibility, absence of causal overstatement and separate provider permissions.
Checks first: manifests/signatures/fingerprints, independent values/statuses, then all original/v1/v1.1 scored runs and repeatability/network-isolation checks. Run full E on the exact candidate, including Excel save/re-read and live reference edits. The approved operators return the R-041 bundles; the maintainer verifies/imports them under release-evidence and records actual builds/results. Re-evaluate whether any changed task requires new human evidence under the approved scope.
Stop for high-severity findings, missing approvals/evidence or a failed release gate. Use separate repair/correction sessions and rerun required gates.
Exit gate: L, independent agreement, full E and all applicable owner-signed release/human requirements pass. Report any unmet gate as open/failing and ask for explicit tag/demo authorization only after the result is concrete. No automatic tag, push or publication.
```

## Requirement coverage index

| R-IDs | Primary sessions |
| --- | --- |
| R-001–R-008 | 4–8 and 11; regression coverage in 18–20 |
| R-009–R-011 | 1–4, 6–8, 11–20 and 23–24 |
| R-012–R-015 | 5, 7, 13, 16, 18–19 |
| R-016–R-018 | 5–7, 14, 16, 18–19 |
| R-019–R-021 | 5, 8, 12, 15–16, 18–19 |
| R-022 | 6 and every later financial output path |
| R-023–R-024 | 7; integration in 16–19 |
| R-025–R-030 and R-037 | 7, 17–20; approximation safety in 23–24 |
| R-031–R-036 | 1, 10, 18–20, 22, 24 |
| R-038–R-041 | 2–4 and E on every later generated workbook family |
| R-042–R-044 | 9–11, 13–16, 18–19 |
| R-045 | 5, 9–13 and the deferred 21–24 branch |
| R-046 | 5, 10, 12, 15, 18–19 |
| R-047–R-048 | 9–11, 14–16, 18–19 |
| R-049–R-050 | 9–17, 18–19, 23–24 |
| R-051 | 5, 10, 12, 18–19; approved D19 still requires verified comparability |
| R-052–R-055 | 1, 9–10, 18–24 and the decision checks in every dependent session |

## Reusable prompts

### Repair — when an exit gate fails

```text
The exit gate for Session [number] is failing. Actual output/evidence:
[paste output or repository evidence path]

Read AGENTS.md, Revision 3 spec, approved decisions and progress. Identify the root cause and explain it before changing anything. Fix the authorized implementation/harness code and keep existing working paths. Leave tests, fixtures, expected values, signed manifests and thresholds unchanged during this repair; if a test/oracle is wrong, stop with the independent arithmetic/source evidence and use the separate correction process. Do not weaken a gate, widen tolerance or suppress an Excel warning. Keep facts/statuses/citations and the two D2 routes intact.

Rerun make check and every failed/affected Excel or benchmark gate, recording the actual result, operator/build and returned evidence path in progress. Full release gates must be repeated when the repaired candidate fingerprint changes. If Excel cannot run locally, send the hashed synthetic candidate/instructions to the approved operator through the agreed handoff and await verified evidence; do not claim a pass. After three failed repairs of the same condition, stop and propose a smaller session or a specific owner decision.
```

### Close-out — only after the stated gate passes

```text
Update docs/progress.md with the completed session, R-IDs and tests, exact commands and actual results, Excel operator/build/evidence paths where required, candidate/manifest checksums, anything unverified, open decisions and the first next runnable session. Distinguish local success from Excel/release/human gates; never mark an open external gate complete.

Verify the original and new signed populations stayed unchanged. Check the diff against this session's allowlist, explicitly stage only authorized files, and exclude credentials, confidential packages and ignored downloads/output. Then commit with the session and R-IDs in the message. Do not push, tag, publish or start another feature session automatically. An independent-oracle session uses external maintainer make-check evidence and must retain its no-src authoring record.
```

### Benchmark correction — only after a concrete owner approval

```text
The owner has approved this specific benchmark correction:
[quote the approval, owner identity/date and exact affected manifest/files]
Independent reason and arithmetic/source evidence:
[insert evidence]

Read AGENTS.md, Revision 3 spec, the applicable SIGNOFF.md and existing checksum manifest. If the quoted approval does not identify the change, stop; this template is not itself an approval. Work in a dedicated correction session. The corrected oracle/builder author must not read/import src/ or use product outputs to obtain expected numbers. Do not change product code to accompany the oracle correction.

Preserve the old manifest and sign-off history. Rebuild independently, compare fields/bytes and confirm every change lies within the approval. In the applicable SIGNOFF.md record approving owner, exact approval reference/date, reason, independent arithmetic/source locations, old/new manifest SHA-256 and changed-file scope. Do not substitute the original benchmark's sign-off for the new Excel/AoC or v1.1 sign-off. Verify all unaffected inputs/settings are byte-identical.

Freeze the new approved manifest and run the independent integrity/arithmetic checks. A separate source-aware maintainer runs make check and then the required black-box/Excel scoring against the sealed corrected key; record its actual result and evidence. The oracle author never imports product code. A correction does not turn an observed product failure into a pass or authorize unrelated threshold changes. Update progress/release evidence, then obtain the normal close-out review.
```

**First prompt to run:** Session 1. The document-authoring session that created this file has not executed Sessions 1–24 or certified any new feature.
