"""Reconcile survey VUP participation against MINALOC administrative counts.

Admin counts: EICV7 Methodological Note, Table 3.4 (final VUP sampling frame,
545,278 beneficiaries from the MINALOC database). Survey: EICV7 cross-section,
household weights, "benefited in the last 12 months".

Usage:
    python src/reconcile_vup.py
Writes reports/vup_reconciliation.csv (aggregates only).
"""
import argparse
from pathlib import Path

import pandas as pd

from common import is_yes, read_dta, svy_ratio, svy_total

ADMIN = {"ds": 117_484, "nsds": 161_807, "cpw": 113_757, "epw": 91_188, "fin": 56_448}
ADMIN_NO_FILE = {"asset_transfer": 3_961, "skills_dev": 633}
ADMIN_TOTAL = 545_278
CENSUS_HH = 3_293_143
NAMES = {"ds": "Direct Support", "nsds": "Nutrition-Sensitive DS", "cpw": "Classic Public Works",
         "epw": "Expanded Public Works", "fin": "Financial Services (loan approved)"}
# Beneficiary column per program file, used to count beneficiary persons (rows with a pid).
PERSON_COL = {"ds": ("CS_S9D1_Direct_Support.dta", "s9d1q2"),
              "cpw": ("CS_S9D2_Classic_Public_Work.dta", "s9d2q1"),
              "epw": ("CS_S9D3_Expanded_Public_Work.dta", "s9d3q1"),
              "nsds": ("CS_S9D4_NSDS.dta", "s9d4q1"),
              "fin": ("CS_S9D5_Financial_Services.dta", "s9d5q2")}


def main(table: Path, raw: Path) -> None:
    df = pd.read_parquet(table)
    w, h, c = df["weight"], df["district"], df["clust"]
    assert set(ADMIN) <= set(df.columns), "rebuild hh_table first"

    rows = []
    for k, admin in ADMIN.items():
        tot, se = svy_total(df[k], w, h, c)
        f, col = PERSON_COL[k]
        d = read_dta(raw / f, columns=["hhid", col]).merge(df[["hhid", "weight", "district", "clust"]], on="hhid")
        persons, _ = svy_total(is_yes(d[col]), d["weight"], d["district"], d["clust"])
        rows.append({"component": NAMES[k], "sample_hh": int(df[k].sum()),
                     "survey_hh": tot, "ci_low": tot - 1.96 * se, "ci_high": tot + 1.96 * se,
                     "survey_persons": persons, "admin": admin, "survey_over_admin": tot / admin,
                     "ratio_ci_low": (tot - 1.96 * se) / admin, "ratio_ci_high": (tot + 1.96 * se) / admin})

    comp_sum = sum(r["survey_hh"] for r in rows)
    admin_sum = sum(ADMIN.values())
    any_tot, any_se = svy_total(df["vup_any"], w, h, c)
    share, share_se = svy_ratio(df["vup_any"], pd.Series(1, index=df.index), w, h, c)
    rows.append({"component": "Sum of 5 components (household-component pairs)",
                 "survey_hh": comp_sum, "admin": admin_sum, "survey_over_admin": comp_sum / admin_sum})
    rows.append({"component": "Any of the 5 components (unique households)", "sample_hh": int(df["vup_any"].sum()),
                 "survey_hh": any_tot, "ci_low": any_tot - 1.96 * any_se, "ci_high": any_tot + 1.96 * any_se})

    out = pd.DataFrame(rows)
    rep = Path("reports/vup_reconciliation.csv")
    rep.parent.mkdir(exist_ok=True)
    out.round(3).to_csv(rep, index=False)

    pd.set_option("display.width", 200)
    show = out[["component", "sample_hh", "survey_hh", "ci_low", "ci_high", "survey_persons", "admin", "survey_over_admin"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:,.2f}" if abs(v) < 10 else f"{v:,.0f}"))
    n_comp = df[list(ADMIN)].sum(axis=1)
    print(f"\nComponents per VUP household (sample): {n_comp[df.vup_any].value_counts().sort_index().to_dict()}")
    print(f"Any-VUP share of households: {100 * share:.1f}% (95% CI {100 * (share - 1.96 * share_se):.1f}"
          f"-{100 * (share + 1.96 * share_se):.1f}); weighted households {w.sum():,.0f} vs census {CENSUS_HH:,}")
    print(f"Admin beneficiaries without a program file (not measurable): {ADMIN_NO_FILE}, "
          f"{100 * sum(ADMIN_NO_FILE.values()) / ADMIN_TOTAL:.1f}% of the frame")

    # Sensitivity: how much of the exclusion error could the survey undercount explain?
    # Missing beneficiaries M = survey unique households scaled by the component-pair gap.
    poor_hh, _ = svy_total(df["poor"], w, h, c)
    covered, _ = svy_total(df["poor"] & df["vup_any"], w, h, c)
    missing = any_tot * (admin_sum / comp_sum - 1)
    scen = {"as reported": 0.0,
            "missing like reported (proportional)": missing * covered / any_tot,
            "all missing are poor (upper bound)": min(missing, poor_hh - covered)}
    print(f"\nExclusion error = poor households with no VUP / all poor households "
          f"(missing beneficiaries ~{missing:,.0f})")
    for name, extra in scen.items():
        print(f"  {name:40s} {100 * (1 - (covered + extra) / poor_hh):.1f}%")
    print(f"Wrote {rep}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", type=Path, default=Path("data/processed/hh_table.parquet"))
    ap.add_argument("--raw", type=Path, default=Path("data/raw/Cross_Section"))
    a = ap.parse_args()
    main(a.table, a.raw)
