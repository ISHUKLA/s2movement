# Benchmark sign-off

Current manifest SHA-256: `eb073b5d400ad380d518bcb40ede0cd6e5ae5aa160d0f419bf76d8987e78a044`

**Status: pending owner review.** The owner approved the design and thresholds on 25 November 2026. On 26 November 2026 two independent rebuilds produced byte-identical inputs, expected results and settings. The manifest fixes those bytes for diagnostic testing.

Before official release scoring, resolve the following dependencies or record their disposition against the specification. See [the 2.8.2 evidence](../../mappings/VERIFICATION.md).

- The complete life TP overlap and its treatment of transitionals and accepted reinsurance still require verification. The frozen answer key also records the former gap in the BV380_1-1 operand list.
- The frozen key records the former gap in the S.25 Article 112 selection. Subsequent verification of BV871-4 and BV380_1-1 supports the two supervisory equations in the Step 5 evidence supplement. Updating the frozen expectations for those checks requires owner approval.
- S.23 shows the restricted Tier 1 instrument and eligible amounts. The evidence does not identify a separate transfer amount to Tier 2. The key leaves that allocation unavailable. Review the remaining Article 82 MCR equality question before relying on an equality-boundary reading.

**Owner acceptance of the built packages, answer key, thresholds and manifest**

- Owner:
- Decision and date:
- Approved manifest SHA-256:
- Disposition of outstanding evidence:

Any later manifest change requires a new owner approval. Preserve the preceding entry and record the reason for the change, old and new checksums, approving owner and date here.

## Approved SCR citation correction · 26 November 2026

- Approving owner: ISHUKLA, in this conversation. The owner explicitly approved the correction and required it to be made in the new handoff folder only.
- Previous manifest SHA-256: `a04c5fd95b37c78142e19a9e417584a92ab5dc6a4168e97fa7d6cdcf2e63c6c4`.
- New manifest SHA-256: `eb073b5d400ad380d518bcb40ede0cd6e5ae5aa160d0f419bf76d8987e78a044`.
- Reason: EIOPA 2.8.2 validation BV254_1-2-7 sums gross S.25.01.01.01 module cells in C0040 and BV134-1-6 adds the separately reported signed LAC-TP adjustment. The previous SCR bridge answer key cited net C0030 module cells. Using net modules and then adding LAC-TP would double-count the adjustment. For a gross increase of 30 and LAC-TP of −11, the correct combined increase is 19; net 19 plus −11 would give 8.
- Scope: The independent builder's SCR component citations now use C0040. The six `expected.yaml` files and `SHA256SUMS` were regenerated. A field-by-field comparison found only module citation `column` and physical `cell` changes. The 12 filing workbooks, values, thresholds and conversion sidecar remained byte-identical.
- This correction does not constitute owner acceptance of the entire benchmark or resolve the other evidence items listed above.
