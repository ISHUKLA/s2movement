"""Independently score the approved flag thresholds and D9 movement register."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from bench_workbooks import HERE, Cells, Key, metadata

BS, TP, OF, RR, MOD, SCR, FLOW, LTG = (
    "S.02.01.01.01",
    "S.12.01.01.01",
    "S.23.01.01.01",
    "S.23.01.01.02",
    "S.25.01.01.01",
    "S.25.01.01.02",
    "S.05.01.01.02",
    "S.22.01.01.01",
)
SEEDS: tuple[Key, ...] = (
    (BS, "R0070", "C0010"),
    (TP, "R0030", "C0210"),
    (TP, "R0100", "C0210"),
    (SCR, "R0130", "C0100"),
    (BS, "R0660", "C0010"),
    (MOD, "R0030", "C0030"),
    (MOD, "R0020", "C0030"),
    (BS, "R0330", "C0010"),
    (OF, "R0580", "C0010"),
    (FLOW, "R1410", "C0230"),
    (FLOW, "R1610", "C0210"),
    (TP, "R0030", "C0020"),
    (BS, "R0220", "C0010"),
    (TP, "R0030", "C0040"),
    (TP, "R0030", "C0050"),
    (TP, "R0100", "C0030"),
    (BS, "R0040", "C0010"),
    (SCR, "R0150", "C0100"),
    (MOD, "R0010", "C0030"),
    (MOD, "R0040", "C0030"),
)


def both(*keys: Key) -> list[list[str]]:
    return [[period, *k] for period in ("opening", "closing") for k in keys]


def movement_register(
    case: str, left: Cells, right: Cells, rules: dict[str, Any]
) -> dict[str, Any]:
    rows = [
        line.split("|")[1:-1]
        for line in (HERE / "README.md").read_text().splitlines()
        if line.startswith("| A") and line[3:5].isdigit()
    ]
    ambiguous = []
    threshold = rules["movement_money"]["threshold"]
    for fields, k in zip(rows, SEEDS, strict=True):
        ident, pkg, label, followup = (f.strip() for f in fields)
        if pkg.split()[0] != case:
            continue
        sign = -1 if ident == "A18" else 1
        a, b = sign * int(left[k]), sign * int(right[k])
        cutoff = max(
            threshold["absolute_eur"],
            abs(a) * Fraction(threshold["fraction_of_abs_opening_component"]),
        )
        if abs(b - a) <= cutoff or (b < a) != ("decreases" in label):
            raise ValueError(
                f"D9 opportunity {ident} fails its direction/materiality check"
            )
        hypotheses, check = followup.split(". ", 1)
        alternatives = hypotheses.split(" or ", 1)
        if len(alternatives) != 2:
            raise ValueError(
                f"{ident} must have two independently plausible hypotheses"
            )
        ambiguous.append(
            {
                "id": ident,
                "movement": label,
                "signed_change": str(b - a),
                "unit": "EUR",
                "opening": str(a),
                "closing": str(b),
                "threshold": str(cutoff),
                "threshold_rule": "max(absolute_eur, abs(opening) * fraction)",
                "settings": "thresholds.yaml#rules/movement_money",
                "hypotheses": alternatives,
                "follow_up": check,
                "required_statement": "Insufficient evidence in QRT snapshots "
                "to attribute this movement",
                "citations": both(k),
                "requirements": ["R-029", "R-034"],
            }
        )
    of = (OF, "R0540", "C0010")
    scr = (OF, "R0580", "C0010")
    dividend = (RR, "R0720", "C0060")
    av = (OF, "R0500", "C0010")
    accounted = []
    labels = {
        "1": ("F01", "Coverage increase from eligible own funds"),
        "2a": ("F02", "Direct profit-participating net BEL decrease from recoverables"),
        "3": ("F03", "Eligible own funds decrease from the reported deduction"),
        "5": ("F04", "Eligible own funds decrease from excluded Tier 3"),
    }
    if case in labels:
        unit = "EUR"
        if case == "1":
            keys = [of, scr]
            assert left[scr] == right[scr]
            delta = 100 * Fraction(int(right[of]) - int(left[of]), int(left[scr]))
            assert delta > Fraction(
                rules["movement_ratio"]["threshold"]["percentage_points"]
            )
            unit = "pp"
        elif case == "2a":
            keys = [(TP, r, "C0020") for r in ("R0030", "R0080", "R0090")]
            gross, rec, net = keys
            assert left[gross] == right[gross]
            delta = Fraction(int(right[net]) - int(left[net]))
            assert delta == int(left[rec]) - int(right[rec]) < 0
        elif case == "3":
            keys = [of, dividend, (RR, "R0700", "C0060"), av]
            delta = Fraction(int(right[of]) - int(left[of]))
            assert delta == int(left[dividend]) - int(right[dividend]) < 0
        else:
            keys = [
                of,
                av,
                *[
                    (OF, r, c)
                    for r in ("R0500", "R0540")
                    for c in ("C0020", "C0030", "C0040", "C0050")
                ],
            ]
            assert left[av] == right[av]
            delta = Fraction(int(right[of]) - int(left[of]))
            a3, e3 = (OF, "R0500", "C0050"), (OF, "R0540", "C0050")
            assert (
                delta
                == (int(left[a3]) - int(left[e3])) - (int(right[a3]) - int(right[e3]))
                < 0
            )
        ident, label = labels[case]
        accounted.append(
            {
                "id": ident,
                "movement": label,
                "signed_change": str(delta),
                "unit": unit,
                "citations": both(*keys),
                "requirements": ["R-029", "R-034"],
            }
        )
    exclusions = []

    def exclude(condition: str, explanation: str, *keys: Key) -> None:
        exclusions.append(
            {
                "condition": condition,
                "excluded_explanation": explanation,
                "citations": both(*keys),
                "requirements": ["R-037"],
            }
        )

    if case in ("4", "5"):
        assert left[dividend] == right[dividend] == 0
        exclude(
            "The dividend/distribution/charge deduction is zero at both dates.",
            "A change in that deduction reduced eligible funds.",
            dividend,
        )
    if case == "1":
        exclude(
            "Both dates have the same positive SCR.",
            "A falling SCR raised coverage.",
            scr,
            (SCR, "R0220", "C0100"),
        )
    if case == "4":
        shares = (RR, "R0710", "C0060")
        assert left[shares] == right[shares]
        exclude(
            "The own-shares deduction is unchanged.",
            "Its change explains the eligible funds movement.",
            shares,
        )
    if case == "2b":
        ma = (LTG, "R0010", "C0090")
        assert left[ma] == right[ma] == 0
        exclude(
            "MA is off and its reported TP impact is zero at both dates.",
            "Introduction of MA explains the TP impact.",
            ("Metadata", "ma_applied", "value"),
            ma,
        )
    if case == "5":
        t2, t3 = (OF, "R0540", "C0040"), (OF, "R0540", "C0050")
        assert all(2 * (int(p[t2]) + int(p[t3])) < int(p[scr]) for p in (left, right))
        exclude(
            "Eligible Tier 2 plus Tier 3 is below half of SCR at both dates.",
            "The combined limit explains increased Tier 3 exclusion.",
            t2,
            t3,
            scr,
        )
    return {"abstentions": ambiguous, "accounted": accounted, "exclusions": exclusions}


def observations(
    case: str,
    left: Cells,
    right: Cells,
    rules: dict[str, Any],
    bridges: list[dict[str, Any]],
    heads: tuple[dict[str, str], dict[str, str]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    evaluations: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []

    def flag(
        rule: str,
        key: str,
        change: Fraction | int,
        threshold: Fraction | int | str,
        refs: list[list[str]],
        unit: str = "EUR",
    ) -> None:
        flags.append(
            {
                "id": f"{rule}/{key}",
                "rule": rule,
                "measure": key,
                "signed_statistic": str(change),
                "unit": unit,
                "threshold": str(threshold),
                "settings": f"thresholds.yaml#rules/{rule}",
                "citations": refs,
            }
        )

    def cutoff(rule: str, field: str, base: int) -> Fraction:
        t = rules[rule]["threshold"]
        return max(Fraction(t["absolute_eur"]), Fraction(t[field]) * abs(base))

    components = {
        TP: {
            "R0010",
            "R0020",
            "R0030",
            "R0080",
            "R0090",
            "R0100",
            "R0110",
            "R0120",
            "R0130",
            "R0200",
            "R0210",
        },
        FLOW: {"R1410", "R1610"},
        LTG: {"R0010"},
        BS: {
            "R0040",
            "R0070",
            "R0220",
            "R0320",
            "R0330",
            "R0340",
            "R0500",
            "R0600",
            "R0690",
            "R0700",
            "R0710",
            "R0720",
            "R0780",
            "R0900",
            "R1000",
        },
        OF: {"R0140", "R0160", "R0500", "R0540", "R0580"},
        RR: {"R0700", "R0710", "R0720", "R0730", "R0740", "R0750", "R0760"},
        MOD: {"R0010", "R0020", "R0030", "R0040", "R0050", "R0060", "R0070", "R0100"},
        SCR: {"R0120", "R0130", "R0140", "R0150", "R0160", "R0210", "R0220"},
    }
    for k in sorted(left.keys() & right.keys()):
        table, r, c = k
        if r not in components.get(table, set()) or (
            table == LTG and c not in ("C0030", "C0050", "C0070", "C0090")
        ):
            continue
        if (table == FLOW and c == "C0300") or (table == MOD and c != "C0030"):
            continue
        a, b = int(left[k]), int(right[k])
        limit = cutoff("movement_money", "fraction_of_abs_opening_component", a)
        if abs(b - a) > limit:
            flag("movement_money", "/".join(k), b - a, limit, both(k))
    # A derived movement uses its own signed opening component as the denominator.
    # Raw level changes and bridge contributions are distinct review observations.
    for bridge in bridges:
        for line in bridge["lines"]:
            if "closing_level" not in line:
                continue
            start = int(line["opening_level"]["value"])
            move = int(line["value"])
            limit = cutoff("movement_money", "fraction_of_abs_opening_component", start)
            if abs(move) > limit:
                flag(
                    "movement_money",
                    f"{bridge['id']}/{line['id']}",
                    move,
                    limit,
                    line["citations"],
                )
    of, scr = (OF, "R0540", "C0010"), (OF, "R0580", "C0010")
    a, b, s, t = int(left[of]), int(right[of]), int(left[scr]), int(right[scr])
    if min(s, t) <= 0:
        evaluations.append(
            {
                "rule": "movement_ratio",
                "status": "indeterminate",
                "reason": "SCR must be positive at both dates",
                "citations": both(scr),
            }
        )
    else:
        reciprocal = Fraction(1, t) - Fraction(1, s)
        for name, pp in {
            "ratio_change": 100 * (Fraction(b, t) - Fraction(a, s)),
            "own_funds": 100 * Fraction(b - a, s),
            "scr": 100 * a * reciprocal,
            "interaction": 100 * (b - a) * reciprocal,
        }.items():
            rlimit = Fraction(rules["movement_ratio"]["threshold"]["percentage_points"])
            if abs(pp) > rlimit:
                refs = (
                    both(of, scr)
                    if name in ("ratio_change", "interaction")
                    else (
                        both(of) + [["opening", *scr]]
                        if name == "own_funds"
                        else [["opening", *of], *both(scr)]
                    )
                )
                flag("movement_ratio", name, pp, rlimit, refs, "pp")
    left_head, right_head = heads or (
        metadata(case, "opening"),
        metadata(case, "closing"),
    )
    for field in rules["measure_status"]["measures"]:
        before, after = left_head[field], right_head[field]
        refs = both(("Metadata", field, "value"))
        if before not in ("yes", "no") or after not in ("yes", "no"):
            evaluations.append(
                {
                    "rule": "measure_status",
                    "measure": field,
                    "status": "indeterminate",
                    "citations": refs,
                }
            )
        elif before != after:
            flag(
                "measure_status",
                field,
                1 if after == "yes" else -1,
                "any known change",
                refs,
                f"{before} to {after}",
            )
    base = (LTG, "R0010", "C0010")
    for col in ("C0030", "C0050", "C0070", "C0090"):
        k = (LTG, "R0010", col)
        absent = [
            period
            for period, facts in (("opening", left), ("closing", right))
            if k not in facts or (period == "opening" and base not in facts)
        ]
        if absent:
            evaluations.extend(
                {
                    "rule": "measure_impact",
                    "measure": col,
                    "status": "unavailable",
                    "period": period,
                    "missing_template": "S.22.01",
                }
                for period in absent
            )
            continue
        impact = int(right[k]) - int(left[k])
        limit = cutoff(
            "measure_impact",
            "fraction_of_abs_opening_with_measures_tp",
            int(left[base]),
        )
        if abs(impact) > limit:
            flag("measure_impact", col, impact, limit, both(k) + [["opening", *base]])
    linked, total = (BS, "R0220", "C0010"), (BS, "R0500", "C0010")
    decisions = [
        abs(int(p[linked]))
        > cutoff("linked_materiality", "fraction_of_total_assets", int(p[total]))
        if int(p[total]) > 0
        else None
        for p in (left, right)
    ]
    for period, outcome in zip(("opening", "closing"), decisions, strict=True):
        if outcome is None:
            evaluations.append(
                {
                    "rule": "linked_materiality",
                    "period": period,
                    "status": "indeterminate",
                    "reason": "Nonpositive total assets",
                    "citations": [[period, *linked], [period, *total]],
                }
            )
    material: bool | str = (
        True if True in decisions else ("indeterminate" if None in decisions else False)
    )
    lk = [(BS, r, "C0010") for r in ("R0220", "R0340", "R0700", "R0710", "R0720")]
    gap = sum(
        sign * (int(right[k]) - int(left[k]))
        for k, sign in zip(lk, (1, 1, -1, -1, -1), strict=True)
    )
    limit = cutoff(
        "linked_divergence", "fraction_of_abs_opening_linked_assets", int(left[linked])
    )
    if material is True and abs(gap) > limit:
        flag("linked_divergence", "linked_portfolio", gap, limit, both(*lk, total))
    final, lac = (SCR, "R0220", "C0100"), (SCR, "R0150", "C0100")
    top = [
        (MOD, row, "C0030")
        for row in ("R0010", "R0020", "R0030", "R0040", "R0050", "R0060", "R0070")
    ]
    adjustments = [
        (SCR, row, "C0100")
        for row in ("R0120", "R0130", "R0140", "R0150", "R0160", "R0210")
    ]
    required = [final, *top, *adjustments]
    missing_scr = [
        period
        for period, cells in (("opening", left), ("closing", right))
        if any(k not in cells for k in required)
    ]
    if missing_scr:
        evaluations.extend(
            {
                "rule": "lac_dt_direction",
                "status": "unavailable",
                "period": period,
                "missing_template": "S.25.01",
            }
            for period in missing_scr
        )
    elif any(
        abs(int(cells[final]) - sum(int(cells[k]) for k in top + adjustments))
        > int(h["money_precision"]) * int(h["money_unit_scale"])
        for cells, h in ((left, left_head), (right, right_head))
    ):
        evaluations.append(
            {
                "rule": "lac_dt_direction",
                "status": "indeterminate",
                "reason": "SCR component reconstruction failed",
                "citations": both(*required),
            }
        )
    else:
        benefit = int(left[lac]) - int(right[lac])
        pretax = int(right[final]) - int(left[final]) + benefit
        floor = int(rules["lac_dt_direction"]["threshold_each_abs_change"]["eur"])
        if pretax * benefit < 0 and min(abs(pretax), abs(benefit)) > floor:
            flag(
                "lac_dt_direction", "relief_magnitude", benefit, floor, both(final, lac)
            )
            flags[-1]["pre_tax_scr_change"] = str(pretax)
    # Matched direct LoBs. S.05 flows are accrual measures, and are never called cash.
    lob_pairs = {
        "C0210": ["C0170", "C0180"],
        "C0220": ["C0020"],
        "C0230": ["C0040", "C0050"],
        "C0240": ["C0070", "C0080"],
        "C0250": ["C0190"],
        "C0260": ["C0090"],
    }
    for col, tp_cols in lob_pairs.items():
        for row in ("R1410", "R1610"):
            flow = (FLOW, row, col)
            missing_flow = [
                period
                for period, cells in (("opening", left), ("closing", right))
                if flow not in cells
            ]
            for period in missing_flow:
                evaluations.append(
                    {
                        "rule": "premium_claim_scale",
                        "measure": row + "/" + col,
                        "period": period,
                        "missing_template": "S.05.01",
                        "status": "unavailable",
                    }
                )
            if flow not in right:
                evaluations.append(
                    {
                        "rule": "premium_claim_vs_bel",
                        "measure": row + "/" + col,
                        "period": "closing",
                        "missing_template": "S.05.01",
                        "status": "unavailable",
                    }
                )
                continue
            b = int(right[flow])
            a = int(left[flow]) if flow in left else 0
            sm, lg = sorted((abs(a), abs(b)))
            ts = rules["premium_claim_scale"]["threshold"]
            if not missing_flow and not sm and lg:
                evaluations.append(
                    {
                        "rule": "premium_claim_scale",
                        "measure": row + "/" + col,
                        "status": "indeterminate",
                        "reason": "Zero denominator",
                        "citations": both(flow),
                    }
                )
            if (
                sm
                and lg > sm * Fraction(ts["factor"])
                and abs(b - a) > ts["also_abs_signed_change_eur_gt"]
            ):
                flag(
                    "premium_claim_scale",
                    row + "/" + col,
                    b - a,
                    ts["factor"],
                    both(flow),
                )
                flags[-1].update(
                    size_factor=str(Fraction(lg, sm)),
                    sign_changed=(a * b < 0),
                    signed_opening=str(a),
                    signed_closing=str(b),
                    change_floor=str(ts["also_abs_signed_change_eur_gt"]),
                )
            operands = [(TP, "R0030", c) for c in tp_cols]
            missing_bel = [
                period
                for period, cells in (("opening", left), ("closing", right))
                if not all(k in cells for k in operands)
            ]
            if missing_bel:
                evaluations.extend(
                    {
                        "rule": "premium_claim_vs_bel",
                        "measure": row + "/" + col,
                        "period": period,
                        "missing_template": "S.12.01",
                        "status": "unavailable",
                    }
                    for period in missing_bel
                )
            else:
                change = sum(int(right[k]) - int(left[k]) for k in operands)
                limit = cutoff(
                    "premium_claim_vs_bel", "multiple_of_abs_delta_gross_bel", change
                )
                if not change and b:
                    evaluations.append(
                        {
                            "rule": "premium_claim_vs_bel",
                            "measure": row + "/" + col,
                            "multiple": "undefined",
                            "reason": "Zero comparable gross BEL movement",
                            "signed_bel_change": "0",
                            "threshold": str(limit),
                            "status": "triggered" if abs(b) > limit else "no_flag",
                            "citations": [["closing", *flow], *both(*operands)],
                        }
                    )
                if abs(b) > limit:
                    flag(
                        "premium_claim_vs_bel",
                        row + "/" + col,
                        b,
                        limit,
                        [["closing", *flow], *both(*operands)],
                    )
                    flags[-1].update(
                        signed_bel_change=str(change),
                        multiple=str(abs(Fraction(b, change)))
                        if change
                        else "undefined",
                    )
    result.update(
        flags=flags,
        linked_material=material,
        flag_evaluations=evaluations,
        joint_questions=(
            {
                "4": [
                    "Compare unit prices and units outstanding with fund statements. "
                    "Check subscriptions and withdrawals against S.05 flows."
                ],
                "5": [
                    "Compare the DTA recoverability forecast and the stressed-tax "
                    "projection for LAC-DT when reviewing Tier 3 eligibility."
                ],
            }.get(case, [])
        ),
    )
    return result
