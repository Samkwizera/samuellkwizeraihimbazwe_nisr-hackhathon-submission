"""Build the household-level analysis table from the EICV7 cross-section files.

Steps
  1. Poverty file (label, weights, district)   -> one row per household
  2. Household file (housing, utilities, land) -> merged on hhid
  3. Program files S9D1-S9D5                   -> VUP participation flags

Usage:
    python src/build_table.py --raw data/raw/Cross_Section
"""
import argparse
from pathlib import Path

import pandas as pd

from common import is_yes, read_dta

# component flag -> (file, column that says "this household has a beneficiary")
PROGRAMS = {
    "ds": ("CS_S9D1_Direct_Support.dta", "s9d1q2"),
    "cpw": ("CS_S9D2_Classic_Public_Work.dta", "s9d2q1"),
    "epw": ("CS_S9D3_Expanded_Public_Work.dta", "s9d3q1"),
    "nsds": ("CS_S9D4_NSDS.dta", "s9d4q1"),
    # s9d5q1 is "ever applied for a loan"; a beneficiary is one whose loan was approved.
    "fin": ("CS_S9D5_Financial_Services.dta", "s9d5q2"),
}
# Every program file carries a column named s9d1q1, but it is NOT the household's
# answer to Q1 ("any VUP component?"): in each file it is Yes only for that file's own
# component (in S9D5 it means "applied"). So vup_any = union of the 5 component flags;
# households whose only benefit is Asset Transfer or Skills Development (no program
# file, 0.8% of the admin frame) are not captured.


def main(raw: Path, out: Path) -> None:
    pov = read_dta(raw / "CS_EICV7_poverty_file.dta")
    assert pov["hhid"].is_unique, "hhid is not unique in the poverty file"
    pov["poor"] = pov["pov_jan"].astype(str).eq("Poor")
    pov["extreme_poor"] = pov["epov_jan"].astype(str).eq("Extreme Poor")

    # Household file: drop columns already present in the poverty file.
    hh = read_dta(raw / "CS_S01_S5_S7_Household.dta")
    hh = hh.drop(columns=[c for c in hh.columns if c in pov.columns and c != "hhid"])
    df = pov.merge(hh, on="hhid", how="left", validate="1:1", indicator="_hh")
    assert (df["_hh"] == "both").all(), "some households missing from the household file"
    df = df.drop(columns="_hh")

    # Program flags: collapse to one row per household (some files have extra rows).
    for name, (fname, col) in PROGRAMS.items():
        d = read_dta(raw / fname)
        flag = d.assign(y=is_yes(d[col])).groupby("hhid")["y"].max().rename(name)
        df = df.merge(flag, left_on="hhid", right_index=True, how="left")
        df[name] = df[name].fillna(False).astype(bool)
    df["vup_any"] = df[list(PROGRAMS)].any(axis=1)

    # Parquet needs one type per column; a few survey columns mix numbers and text
    # labels (e.g. "Don't know"), so store all categorical/text columns as strings.
    for c in df.columns:
        if isinstance(df[c].dtype, pd.CategoricalDtype) or df[c].dtype == object:
            df[c] = df[c].astype("string")

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    w, pw = df["weight"], df["pop_wt"]
    print(f"Wrote {out}  shape={df.shape}")
    print(f"Weighted households: {w.sum():,.0f}")
    print(f"Poverty rate (pop_wt, person level): {100 * (df.poor * pw).sum() / pw.sum():.1f}%")
    print(f"VUP any (household-weighted): {100 * (df.vup_any * w).sum() / w.sum():.1f}%")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, default=Path("data/raw/Cross_Section"))
    p.add_argument("--out", type=Path, default=Path("data/processed/hh_table.parquet"))
    a = p.parse_args()
    main(a.raw, a.out)
