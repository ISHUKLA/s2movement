# Step 0.0 tooling decisions

| Choice | Reason |
| --- | --- |
| Git on local `main` | Gives every later session a common starting commit. |
| CPython 3.12.14 | An exact patch pin in `.python-version` makes setup repeatable within the project's Python 3.12 requirement. |
| uv and a committed `uv.lock` | Reviewers install the same Python dependencies for their platform. `uv sync --locked` fails when the project and lockfile disagree. |
| `src/s2movement/` and the pinned `uv_build` backend | uv installs the package directly from the standard source layout. Pinning the build backend also fixes the version used for isolated builds. |
| A separate dev dependency group | pytest, Ruff and mypy are needed to develop the package. The runtime dependency list can stay empty. |
| pytest | A single import test exercises the package installed in the environment. |
| Ruff lint and format | One tool checks style, undefined names, import order, common bugs and Python 3.12 idioms. The separate formatting target applies its formatter. |
| Strict mypy | New package and test code must pass type checks from the first commit. |
| Make | Three targets give reviewers stable commands. The check target verifies the environment and lockfile offline, runs tools from the project environment and disables persistent caches and bytecode writes. |
| Git ignore rules | Restrict tracked private inputs, outputs and public downloads to the designated documentation and provenance files. Ignore local credentials, environments and caches. |
| CSV reference manifest | A header-only manifest reserves fields for filenames, source URLs, versions and SHA-256 digests. Step 2 supplies the entries. |
| Git attributes | Normalise text to LF and preserve Excel and ZIP files as binary. |

## Step 1 review decisions

The [specification](spec.md#decisions-after-owner-review) records the owner's scope, arithmetic and evidence decisions. Two design choices complete the handoff:

- Use the Excel summary as the dashboard. Deliver the optional narrative in Word, with an appendix if full coverage exceeds two pages. This keeps the main report readable and each material item traceable.
- For the delegated release trial, use eight reviewers, two matched cases and four balanced assignments. Each reviewer tries both methods on different cases. Measure elapsed time to the first submitted list of issues and score detection separately for each defect class. This tests the time target without rewarding a faster review that misses seeded defects.

## Step 2 evidence decision

- **R-008, R-021, D3:** For an XBRL solvency-ratio fact, the owner selected the fact's declared `decimals` precision to define the comparison tolerance, rather than the number of lexical digits in the value. See [the verification notes](../mappings/VERIFICATION.md#6--reported-solvency-ratio-and-precision) for the source and remaining edge case.

## Approved architecture and first-slice tooling decisions

| Choice | Reason |
| --- | --- |
| openpyxl for normalized workbook input and test inspection | It reads literal cell values, formulas, sheet names and physical locators without making the downstream calculation depend on workbook objects. |
| Pydantic for ledger boundary models | It rejects malformed or incomplete evidence records before calculations use them. |
| XlsxWriter for output | Its formula writer accepts the Python-computed cached result; the generated formulas remain live and can be recalculated by Excel or LibreOffice. |
| pytest plus `types-openpyxl` in the dev group | pytest exercises the deterministic slice; the stubs keep strict mypy checking useful at the workbook boundary. |
| LibreOffice 26.2.5.2 in `make check` | It is the installed formula engine used to recalculate every generated formula in the integration suite. The test fails if this supported version is absent. |
| macOS `sandbox-exec` plus CPython audit hooks for the offline test | The OS sandbox denies network syscalls. Audit hooks record Python socket, DNS and process-launch attempts, including attempts the application catches; the harness self-tests its observer and native-socket block. |
| UTF-8 JSON with canonical Decimal strings | It avoids float serialization and supports byte-for-byte repeatability. |
| Static first-slice inputs under `tests/data/` | They exercise the CLI without adding files to `tests/fixtures/`, which is reserved for Step 4 benchmark packages and their independent builder. |
| Console command `s2movement compare` | It exposes the local deterministic operation with no network or commentary mode in this slice. |
| Exclude XLSX ZIP container timestamps from repeatability comparison | They are generated metadata; test results compare every workbook cell, formula, cache, type and style while JSON remains byte-for-byte identical. |

## Step 4 benchmark tooling

| Choice | Reason |
| --- | --- |
| Independent reported statements and answer-key arithmetic in tests/fixtures | The builder uses the spec, mappings and approved seeds. It can rebuild the benchmark without loading the product. |
| Fixed workbook timestamps and stable table, row and dimension ordering | A rebuild can verify the exact workbook bytes in the manifest. |
| YAML 1.2 using JSON syntax for expected values and settings | The locked Python environment can parse both with the standard library. Monetary values and exact ratios retain their precision. |
| Separate integrity and diagnostic commands | `make check` detects changes to the frozen inputs and answer key. The CLI score can expose missing product features while the independent benchmark is under review. |

## Step 5 gate and reconciliation

| Choice | Reason |
| --- | --- |
| Order by the effective reference date and record the original input order | Chronological periods define movement signs. Check succession before interpreting the financial tables. A PDF has a file locator but supplies no reference date. |
| Retain header facts and corroborating S.01.02/context evidence | A metadata correction can repair a declaration. Contradictory source evidence keeps the gate blocked. |
| Version the R-008 check catalogue alongside the cell mappings | Each equation exposes its source, operands, tolerance, unsupported variants and dependent movements to a reviewer. Both Python and Excel use the selected operands. |
| Use an exact rational quotient for the reported-ratio comparison | The recomputed ratio can be recurring. Its inclusive boundary must be decided before presentation rounding. |
| Key SR coverage by portfolio type and identifier | A matching-adjustment portfolio does not evidence a ring-fenced fund, and the remaining part cannot clear either warning. |

## Bridge implementation

| Choice | Reason |
| --- | --- |
| Gross S.25.01 modules with the separately reported signed LAC-TP adjustment | EIOPA validations BV254_1-2-7 and BV134-1-6 establish the additive basis. The frozen answer keys cite net cells, so their citation discrepancy remains open for owner review. |
| Exact rational arithmetic for the solvency-ratio decomposition | The three effects must sum exactly before display rounding under D5. |

## Technical-provision presentation · R-012–R-015

| Choice | Reason |
| --- | --- |
| Show net BEL as a derived subtotal beside each TP bridge | It makes gross BEL less its recoverables auditable while each total counts the amount once. |
| Show S.22.01 as undertaking-wide scenarios beside both TP bridges | The source supplies undertaking TP impacts. A separate schedule preserves their scope. |
| Pair the linked-asset movement with each of the four reported comparator movements | Each signed difference has two explicit operand IDs and all source citations for Step 9. |
| Display available observations when materiality is indeterminate | Missing denominator evidence or a currency outside the frozen EUR settings is visible to the reviewer alongside the available figures. |

## Own funds and tier limits · R-016–R-018

| Choice | Reason |
| --- | --- |
| Load balance-sheet buckets from the versioned coverage catalogue | The formula roots and the full row membership have one reviewable source. The test expands subtotals and proves each Solvency II component is counted once. |
| Retain statutory-only row assignments with their valuation scope | Coverage includes all S.02.01 row codes while the bridge uses its C0010 valuation basis. |
| Show combined dividends/distributions/charges and RFF/MAP restrictions with unavailable individual splits | Those are the aggregates reported at the mapped S.23.01 addresses. |
| Use the same ordered decision conditions in Python and Excel | Live changes to reported amounts recalculate both legal comparisons and conclusions. |
| Record exact reported compliance and a separate attribution conclusion | A strict equality fails the mapped comparison. Reporting precision can still leave attribution indeterminate. |
| Require the eligible amount to match the largest source-precision multiple within the bound before concluding binding | This respects strict and inclusive bounds and requires excess supply beyond one source unit and evidence that a competing limit has headroom. Ambiguous observations remain indeterminate. |
| Show observed eligibility adjustments separately from attributed effects | Overlapping limits can affect the same amounts. A combined-limit assessment with headroom has zero attributed effect even when Tier 3 causes a reported deduction. |

## SCR and ratio acceptance · R-019–R-021

| Choice | Reason |
| --- | --- |
| Give S.26 schedules an explicit `scr_drilldown` category and `scr_modules` association | It identifies their purpose while their values remain outside every top-level bridge expression. Single-template removal and single-cell mutation tests verify isolation at both dates. |
| Validate each S.23.01 SCR denominator separately and withhold the whole D5 decomposition on failure | Missing, zero and negative SCR must produce a cited validation failure. The CLI returns 1 and writes both review outputs. The summary's live validation formulas prevent an edited denominator from producing a division error. |
| Preserve the D5 own-funds, SCR and interaction terms as exact rational numbers | Repeating quotients cannot acquire a spurious Python residual. JSON uses exact decimal or fraction strings and carries every contributing citation. The interaction stays on its own line. |
| Display six decimal places for percentage-point cells without rounding formulas | The workbook remains readable while the calculation and JSON retain their precision. Formula notes record the definition of E and S, all three equations, units and interaction treatment. |
| Accept nonzero ratio formula results within `max(1e-10 percentage points, 1e-14 × abs(expected))` in LibreOffice tests | Excel-compatible engines use floating-point arithmetic. This is a numerical test allowance, separate from D3's reported-precision tolerance. Exact-zero effects and the identity residual must equal zero. Monetary comparisons retain their existing exact checks. |
| Group identical signed raw-cell quotients in the Excel identity residual before combining unlike terms | This evaluates the same declarative residual without cancellation noise. The coefficients come from all opening, movement and closing expressions, so an incorrect coefficient remains observable. |
| Use 500 seeded random positive input quadruples and four edge cases for the D5 property test | The independent `Fraction` equations test exact equality across increasing and decreasing amounts, recurring quotients, adjacent large integers and widely different denominators. A fixed seed makes any failure reproducible without another dependency. |

## Owner decisions for R-022–R-024 · 26 November 2026

| Decision | Reason |
| --- | --- |
| Correct the frozen SCR module answer-key citations from net C0030 to gross C0040 in the handoff copy | The owner approved this specific manifest change. EIOPA 2.8.2 validations BV254_1-2-7 and BV134-1-6 add gross modules and the separately reported signed LAC-TP adjustment. See `tests/fixtures/SIGNOFF.md` for both checksums and the exact changed fields. |
| For the R-024 LAC-DT direction rule, use pre-tax SCR = S.25.01 final SCR R0220/C0100 minus signed LAC-DT R0150/C0100 | The owner explicitly approved the frozen proposal's measure in this conversation. It is an arithmetic measure before this one signed adjustment, not a claim that the template reports a separate pre-tax SCR cell. Preserve both citations, the reported sign and the distinction in the rule message. |

## XBRL adapter preparation · R-001–R-004

| Choice | Reason |
| --- | --- |
| Pin `arelle-release==2.47.5` and use EIOPA's 2.8.2 package with external files | Arelle can resolve the official annual solo sample locally with `workOffline=True`; the package includes its own `META-INF/catalog.xml`, `taxonomyPackage.xml` and external schema dependencies. |
| Make taxonomy acquisition an explicit `make fetch-taxonomy` setup command outside `src/` | The default comparison path stays offline, and R-009 prohibits network imports in the deterministic core. The command checks downloaded bytes against the SHA-256 in `reference/manifest.csv`. |
| Refuse XBRL and mixed pairs until the cell signature catalogue covers all needed facts | The current annotated-template mapping omits 1,375 supervisory data-point signatures. In the frozen clean package, 484 of 1,176 ledger facts lack such a signature, including S.12.01 and S.25.01 cells. Assigning them from a metric alone would silently merge different dimensions or cells. The partial prototype was removed before release. |

## Optional challenge pack preparation · R-025–R-030 and R-037

| Choice | Reason |
| --- | --- |
| Use Anthropic `claude-sonnet-4-6` behind `--challenge-pack` | The owner changed the provider to Anthropic Sonnet. The exact active model id and structured-output support were checked against Anthropic's published model and API documentation. No credential was available for a live call. |
| Require passing citation-validation, flags and abstention fields in the JSON before provider access | The current deterministic producer lacks these R-022–R-024 outputs. Fail-closed behavior prevents unvalidated pre-submission figures from being sent. |
| Use Pydantic typed items and a static, condition-filtered catalogue | The model selects evidence and review entries by id. Python supplies the cited values, labels, artefacts and comparisons, and repeats contradiction checks after drafting. |
| Use `python-docx` for Word and `pypdf` only in render tests | Word is the required delivery format. The test converts to PDF with LibreOffice and counts actual pages before the appendix, rather than estimating from characters alone. |
| Give each narrative section its own body budget and move overflow to an appendix | This preserves observations, questions, hypotheses and checks in the one-to-two-page body even when many material items compete for space. |
| Generate a catalogue check for every material flag regardless of model selection | R-030 coverage must not depend on the model remembering to ask for a check. An unmatched flag withholds the pack instead of disappearing. |

## Revision 3 — Excel acceptance and actuarial AoC · 27 November 2026

The governing requirements are [Revision 3](spec.md). On 27 November 2026 the owner explicitly approved the recommended D11–D22 basis and separately required the AoC practising-actuary trial before v1 release. The answers below supersede the earlier pending labels in the specification; this session leaves the specification text unchanged. Earlier LibreOffice and first-slice decisions describe historical implementation, not Microsoft Excel or AoC acceptance. Approval of the plan is not approval of a benchmark answer key, release result, provider transmission or an unspecified numerical allowance.

| ID / status | Decision or recommendation and reason |
| --- | --- |
| **D10 — confirmed owner instruction** | Target Microsoft 365 desktop Excel and bring insurer-evidenced actuarial AoC into fundamental scope. Reported reconciliations and standalone SCR deltas alone do not meet that purpose. No source-code or prompting-algorithm change is authorized in this first specification session. |
| **D11 — approved policy; exact targets pending** | Certify Microsoft 365 desktop Excel on Mac and Windows, with each minimum set to the earliest exact build that passes the full harness. Actual machines/builds/channels and the responsible operator must be nominated and evidenced before platform acceptance. No numeric build was supplied or assumed. |
| **D12 — approved** | Retain LibreOffice only as a secondary diagnostic on copies, never a substitute for Excel acceptance or a production cache-filling step. Microsoft Word remains the narrative layout target; LibreOffice PDF pagination is secondary. Existing mandatory test dependencies change only in a checked implementation session. |
| **D13 — approved** | Preserve the insurer's actual supplied run order, with no mandated re-sequencing. C01–C12 classify reported steps; their numbering does not order runs. A different planning order for future insurer runs needs separate approval. |
| **D14 — approved feature split** | v1 permits conditional Euler/date allocations and exact S.22/S.23 observed deltas as separate schedules; causal steps need insurer runs/records. S.13/RFR approximate unwind belongs to v1.1 after the v1 release gate. The future proxy's detailed curve/currency, LTG, timing, tail, coverage and error-budget convention still needs approval before implementation. |
| **D15 — approved method; source/edge-case gates remain** | Use Euler only for a verified reconstructible basic-SCR aggregation, and full SCR reruns for exact diversified step impacts. Standalone, allocated and proxy amounts remain distinct; missing exact SCR stays unavailable. Source basis, exceptional/zero-aggregation handling and any new engineering allowance must be resolved before the dependent numerical branch is implemented or frozen. |
| **D16 — approved** | Where full intermediate SCR is missing, show available-own-funds AoC by tier plus the change in the observed eligible-minus-available adjustment as a final reconciliation. Do not infer intermediate eligible tiers or splice available opening into eligible closing. Complete same-step SCR/classification evidence permits stepwise eligibility subject to D6; unresolved restricted Tier 1 attribution stays indeterminate. |
| **D17 — approved existing rules; new bounds pending** | Preserve D3 on monetary endpoint/continuity/residual controls, including confirmed-conversion precision, and exact D5 identities. Any new Euler engineering bound, altered source-precision rule or approximate-step error budget remains a blocking owner approval before dependent implementation/freeze. State units, equality and near-zero behavior. No new allowance can widen D3 or absorb a residual. |
| **D18 — approved per-run consent policy** | Require separate explicit per-run AoC provider permission in addition to QRT commentary permission. Authorize only the reviewed minimized validated-JSON projection, including AoC-derived figures and internal attribution/run metadata; record scope/provider/model/input hashes and consenting reviewer separately from deterministic outputs. This policy approval grants no consent for an actual transmission and no standing permission or invented retention terms. |
| **D19 — approved conditional cross-checks** | Use verified comparable S.29.03/S.29.04 only as separate cross-checks, never causal sources or fillers for missing AoC steps. S.29.01/S.29.02 remain unused. Source verification is still required; no mappings or original frozen expectations change in this session. |
| **D20 — approved release split** | v1 includes Excel-certified reconciliation, insurer-input deterministic AoC and the optional safe, separately consented Word pack. v1.1 follows the v1 release gate and adds separately approved approximate unwind/broader automation. An unfinished mandatory v1 feature cannot be deferred to make the gate pass. |
| **D21 — approved; additional v1 release gate** | Retain R-035's original triage gate. Also require the separate AoC practising-actuary trial before v1 release: eight reviewers, balanced crossover, at least 35% median time reduction and tool detection at least the manual Excel AoC baseline separately by each seeded AoC defect class. Both methods receive identical underlying run inputs. Use fresh matched cases, a separately signed independent key, blinded findings, no feedback between runs, and owner sign-off on observed times/counts/outcome. Neither trial substitutes for the other. |
| **D22 — approved** | Keep normalized QRT/AoC inputs literal-only; reject all financial numeric text and all formula inputs, including those with caches. Accept native Excel numbers/dates and text in schema-defined identifier fields. No locale inference or cached-formula freshness assumption is authorized. |

Approval evidence, 27 November 2026: in response to the question asking to adopt the recommended D11–D22 basis while keeping exact Excel builds/new numerical tolerances as approval gates, the owner answered **“Approve this basis (Recommended)”**. In response to whether the separate AoC trial should precede v1 release or only an AoC utility claim, the owner answered **“Required before v1 release (Recommended)”**. This records the two actual answers, not inferred approval. The original alternatives remain in [the specification](spec.md#decisions-needed-from-the-owner); only its earlier pending decision status is superseded here. No benchmark manifest or sign-off is approved by these answers.

The cache audit corrects a possible diagnosis: `output.py` supplies Python-evaluated numeric/text results to XlsxWriter's `write_formula` cache argument. Production does not recalculate/save through LibreOffice. LibreOffice rewrites disposable test/scorer copies only. The confirmed conflict is missing Excel acceptance evidence, not an established LibreOffice-caused repair prompt. The specification lists every detected engine dependency and the components that can be reused for AoC.
