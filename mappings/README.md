# Cell mappings

`2.8.2/` holds the v1 source inventory for the 2.8.2 taxonomy. A later taxonomy gets its own sibling directory. The source locations and SHA-256 digests are in [the reference manifest](../reference/manifest.csv). The source files themselves are ignored by Git and can be downloaded from the URLs in that manifest.

- `cells.csv` records the unshaded, row-and-column-addressed cells in the annual solo supervisory and public-disclosure sheets for the template families in scope. It includes the full annotated-table identifier, physical workbook cell, source label locations, metric evidence, reporting variant, known sign and subtotal information, and any EIOPA-identified data-point context signature. A blank signature means the validation workbook does not list the cell as an identical datapoint; it does not prove the context is unnecessary or the cell is unique. `supervisory_ars` and `public_aps` describe **that physical table**, not the absence of an equivalent cell in another table.
- `variant_equivalences.csv` records supervisory/public pairs explicitly identified as the same data point in EIOPA's validation workbook. Retain the source dimensions and coordinate context. Absence from this file does not prove that no equivalent exists.
- `metadata_enumerations.csv` records selected S.01.02 display codes alongside their XBRL members. The numeric labels and XBRL member suffixes are different code systems.
- `relationships.csv` records the sourced S.05.01 gross-to-net relationships separately from additive subtotal relationships.
- `legal_limits.csv` records the Article 82 comparisons and whether each bound is strict or inclusive. Check its date-status field and [VERIFICATION.md](VERIFICATION.md) before using it.

This is a source inventory, not a completed bridge definition. In `cells.csv`, an **unverified** sign or subtotal is an evidence gap; an empty subtotal list does not mean that a row has no children. The per-cell sign instructions, subtotal relationships and some like-for-like comparisons remain open as described in [VERIFICATION.md](VERIFICATION.md). A grey cell in the source is not emitted as reportable. A source cell can require a Z axis or other dimensions in addition to row and column; retain the applicable XBRL context.

The data includes supplementary cells from the in-scope template sheets to preserve context. Inclusion does not make every cell mandatory for a bridge or allow a mapping consumer to use an unverified entry. Fixtures, formulas and application code are later work.

For R-016, `2.8.2/balance_sheet_buckets.json` records every S.02.01 row, its bucket or signed subtotal, its source location, and the seven sets of reported roots used in the excess bridge. Its children describe coverage. The calculation adds each reported root once. Goodwill R0010, deferred acquisition costs R0020 and other technical provisions R0730 are assigned to their respective buckets with their statutory-accounting-only scope recorded.
