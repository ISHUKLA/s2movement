# User Story

As a solo Head of Actuarial Function (HoAF), Solvency II Reporting Manager, or independent actuarial reviewer performing pre-submission sign-off on an annual solo European life insurer (Standard Formula), I want to run a local tool against two consecutive Solvency II XBRL reporting packages (or normalized SFCR/QRT workbooks) and receive a formula-driven Excel reconciliation workbook plus an evidence-constrained Pre-Sign-Off Challenge Pack. I want the tool to verify period-on-period comparability, reconcile movements in Technical Provisions (BEL and Risk Margin), Eligible Own Funds, SCR, and the Solvency Ratio to zero residual, flag structural anomalies across templates, and generate cited review questions that state clearly where QRT data cannot prove a root cause.

Draft commentary the actuary can verify. Link each numerical claim to its source row. Label plausible explanations as hypotheses and give a specific follow-up check.

## Example of the commentary I'd expect from the app

> Gross BEL increased by €20m, of which €18m came from unit-linked business. Unit-linked assets rose by €19m and the associated risk margin rose by €1m, so these three lines offset at the balance-sheet level. Fund performance and net inflows are both plausible explanations for the unit-linked movement. Comparing fund returns with net subscriptions and withdrawals would help establish how much each contributed.

That example captures the AI's job in v1. The figures show where the movement occurred. The AI proposes a plausible explanation and the next check an actuary can actually perform.

## v1 Scope & Non-Goals

**In scope (v1):** Annual, solo, European life undertakings reporting under Standard Formula per Commission Implementing Regulation (EU) 2023/894 and (EU) 2023/895 (EIOPA Taxonomy 2.8.x, architected for Taxonomy 2.10.0).

- Required templates: S.02.01 and S.23.01. A period that omits either is a hard stop.
- Expected templates: S.12.01 and S.25.01. If either is absent, the affected bridge degrades with a warning.
- Metadata templates: S.01.01 and S.01.02 (or XBRL context headers).
- Optional enrichers when present: S.05.01, S.22.01, and S.26.01–S.26.03.

**Explicitly out of scope (v1):** Group consolidation (Method 1/Method 2, S.32.01), Internal Model SCR (S.25.05), quarterly QRTs (where S.25.01 and S.22.01 are absent), annual variation templates (S.29.01–S.29.04, proposed for deletion under EIOPA-BoS-26/081), PDF SFCR scraping. If a package contains S.29 templates, the tool reports them as "present, not used".

**Implementation and data handling (v1):** The tool is written in Python. The LLM layer is off by default and runs only behind an explicit flag, because enabling it sends pre-submission figures to a model provider.

## Revised Acceptance Criteria

### 1. Input Ingestion & Comparability Gate (Hard Stops vs. Warnings)

The tool parses both reporting periods and executes a mandatory comparability gate before generating movement bridges.

**Metadata extraction:** Extract and display from S.01.01 and S.01.02 (or XBRL context headers): Legal Entity Identifier (LEI), undertaking name, reporting reference dates, solo vs. group scope, reporting currency, reporting unit scale (exact units vs. thousands), taxonomy version, Standard Formula vs. Internal Model flag, Ring-Fenced Fund (RFF) / Matching Adjustment Portfolio (MAP) indicators, and LTG/transitional flags.

**Hard-stop blockers:** Halt bridge generation (requiring explicit user normalization or override) if:

- LEIs or solo/group reporting perimeters do not match;
- Currencies differ between periods;
- Unit scales differ without confirmed normalization (e.g., exact euros vs. thousands);
- Either period uses an Internal Model (S.25.05) or omits a required template (S.02.01 or S.23.01).

**Non-blocking structural warnings:** Prominently flag on the executive dashboard and Excel summary tab if:

- EIOPA taxonomy versions differ across periods;
- LTG or transitional measures (VA, MA, TMTP, TMIR) changed status or materially shifted in S.22.01;
- RFF/MAP flags are active in S.01.02 while SR.\* templates are absent;
- Expected templates (S.12.01, S.25.01) or optional enrichers (S.05.01, S.22.01) are missing, triggering graceful degradation of the affected sub-bridge rather than silent omission.

**Cross-template internal consistency checks:** Verify that overlapping figures agree within declared rounding tolerance (at most 1 reporting unit) within each period before computing deltas—including S.02.01 vs. S.12.01 life technical provisions and reinsurance recoverables, S.02.01 R1000 vs. S.23.01 Excess of Assets over Liabilities, and S.23.01 R0580 vs. S.25.01 Total SCR. Any break must surface as an explicit reconciliation failure.

### 2. Reconciled Deterministic Bridges & Exact Ratio Decomposition

All calculations must be 100% deterministic, reproducible, and exported as live Excel formulas (never hard-coded output values) linking back to raw ingested period tabs. Every bridge must tie opening value + sum of movements + explicit residual = closing value, with an unexplained residual of 0 (within 1 reporting unit for rounding).

**Technical Provisions & BEL Bridge (S.02.01, S.12.01, optional S.22.01 & S.05.01):**

- Decompose life and health SLT technical provisions separately into Technical Provisions calculated as a whole, Gross BEL, Reinsurance Recoverables, Net BEL, and Risk Margin.
- Provide Line of Business breakdown from S.12.01, preserving regulatory boundaries (labeling LoB 31 accurately as Index-linked and unit-linked, splitting BEL with vs. without options/guarantees while reporting Risk Margin only at its reported LoB total granularity).
- Where S.22.01 is present, display opening/closing impacts of VA, MA, and transitionals on Technical Provisions alongside the bridge.
- Where index-linked/unit-linked business is material, include a dedicated Unit-Linked Balance-Sheet Pairing Check comparing linked assets (S.02.01 R0220), linked reinsurance recoverables (R0340), TP as a whole (R0700), Gross BEL (R0710), and Risk Margin (R0720), flagging any divergence between asset growth, implied non-unit BEL, and Risk Margin.

**Eligible Own Funds Bridge (S.02.01, S.23.01):**

- Bridge opening to closing Excess of Assets over Liabilities (S.02.01 R1000) via major balance-sheet asset and liability buckets (clearly isolating investments, linked assets, technical provisions, deferred tax assets/liabilities, and other assets/liabilities).
- Bridge from Excess of Assets over Liabilities to Own Funds Eligible to Meet the SCR (S.23.01 R0540), isolating foreseeable dividends, own shares, RFF/MAP restrictions, subordinated liabilities, ancillary own funds, and Tier 2 / Tier 3 eligibility cap movements (highlighting when the 50% SCR Tier 2+3 cap or 15% SCR Tier 3 cap binds or releases).

**SCR & Solvency Ratio Bridge (S.25.01, S.23.01, optional S.26.01–S.26.03):**

- Decompose Standard Formula SCR movements across reported risk modules, diversification, operational risk, LAC-TP, LAC-DT, and capital add-ons/RFF adjustments. If S.26.\* sub-modules are supplied, attach a drill-down schedule without altering the top-level S.25.01 reconciliation.
- If S.25.01 is missing, display the headline SCR movement from S.23.01 R0580 and explicitly mark the module breakdown as Unavailable.
- Decompose the change in the Solvency Ratio (Δ(E/S)) using an exact, zero-residual algebraic split into Own Funds contribution, SCR contribution, and the explicit non-linear interaction term (or exact Shapley allocation, documented in the formula notes)—never an unadjusted linear approximation.

### 3. Deterministic Anomaly Flags, Auditable Traceability & Evidence-Constrained Pre-Sign-Off Challenge Pack

Separate factual movement reporting from interpretive review questions so a reviewer can rely on the deterministic numbers even with the LLM turned off. The deterministic engine ships first (v0.1). The LLM layer is a later, optional release (v0.2).

**100% programmatic traceability:** Every figure in both the Excel workbook and the Markdown/Word Challenge Pack carries a verified coordinate citation ([Period | Template | Row | Col]) validated programmatically against the parsed source files before output is rendered.

**Deterministic mode (mandatory baseline, v0.1):** Run end-to-end with zero LLM calls, producing the Excel workbook plus a structured JSON summary of reconciled bridges and rule-based anomaly flags. The anomaly engine flags, without an LLM, material movements exceeding user-configurable thresholds and structural patterns, including:

- Tier 2 / Tier 3 caps binding;
- LACDT moving opposite to pre-tax SCR;
- VA/transitional shifts;
- non-unit BEL vs. Risk Margin divergence in index-linked and unit-linked business;
- S.05.01 premium/claim scale mismatches;
- large statutory cash flows (S.05.01) relative to BEL changes.

**Optional evidence-constrained LLM layer (v0.2):** Consume only the verified deterministic JSON (never raw unparsed tables) to draft a 1–2 page Pre-Sign-Off Challenge Pack, never framed as "final close commentary", containing:

- **Factual Movement Summary:** Every numerical value must carry a machine-verified source tag ([Period | Template | Row | Col]) checked programmatically against the deterministic JSON before display; any unverified number fails the output gate.
- **Cross-Template Triage Questions:** Synthesize co-occurring deterministic flags into specific sign-off challenges for the HoAF or actuarial production team.
- **Labeled Hypotheses:** Every causal explanation not directly observable in the QRTs must be explicitly labeled Hypothesis (not verifiable from QRT snapshots) and present multiple mathematically consistent drivers where applicable.

The layer is bound by these rules:

- **No causal creep:** Prohibited from attributing unobservable economic or actuarial causes as facts (bans ungrounded causal verbs such as "driven by" or "caused by" when referencing external drivers).
- **Mandatory abstention:** When a material movement has multiple unobservable drivers, or multiple actuarial mechanisms can produce the same QRT footprint (such as non-linked BEL changes mixing risk-free rate shifts, assumption updates, model changes, business volumes, and net inflows), the tool must explicitly state "Insufficient evidence in QRT snapshots to attribute this movement", list the mathematically consistent hypotheses, and never invent percentage driver or attribution splits.
- **Contradiction filtering:** Must not propose a hypothesis contradicted by another reported cell in the package (e.g., citing foreseeable dividends when reported foreseeable dividends are zero).
- **Actionable verification checks:** Every material flag or hypothesis is paired with a specific internal artifact to check (e.g., internal actuarial AoC waterfall step, unit-fund attribution or return vs. net-flow report, LACDT recoverability study, or DTA tax-schedule memo).

### 4. Measurable Release & Benchmark Gates

Before tagging v1.0 or publishing a public demo, the tool must pass a 5-case benchmark suite:

1. Clean Annual Solo Close
2. Unit/LTG Basis Mismatch, run as two sub-cases with separate expected outcomes:
   - 2a. Unit-scale mismatch (expected outcome: hard stop)
   - 2b. LTG or transitional change (expected outcome: warning)
3. Annual Package with S.25.01 Absent (tests graceful degradation; quarterly reporting stays out of scope)
4. Ambiguous Unit-Linked/BEL Move
5. Binding Tier 3 DTA/LACDT Cliff

The gates:

- **Reconciliation accuracy:** 100% of supported bridges tie to zero residual (within 1 reporting unit) with 0 sign inversions.
- **Citation accuracy:** 100% of numeric values and cell references match source files programmatically.
- **Hallucination & abstention:** 0% fabricated numbers or unlabelled causal claims; at least 95% recall on seeded unobservable-driver abstention cases.
- **Reviewer utility:** In blind trials against a plain Excel diff baseline, practicing life actuaries achieve at least 35% faster initial review triage with equal or higher detection of seeded cross-template and comparability defects. This gate is measured in a human trial that the product owner runs and signs off. The build delivers the trial kit: seeded-defect packages, the Excel diff baseline, an answer key, and a timing and scoring sheet.
