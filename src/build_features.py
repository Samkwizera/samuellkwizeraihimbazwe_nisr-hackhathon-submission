"""Build leakage-free household features for the proxy-targeting model.

The poverty label is built from consumption, so nothing here may come from
expenditure, rent, utility bills, dwelling or durable values, or school spending
(see CLAUDE.md, Modeling rules). Durables enter as counts only.

Sources
  Household file : dwelling materials, utilities, shocks, livestock
  Person file    : head characteristics, household composition, education, ICT
  Durables file  : number of items owned (no values)

Usage:
    python src/build_features.py
Writes data/processed/features.parquet (one row per hhid) and
reports/feature_list.csv (feature -> source, kept in git as documentation).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import is_yes, read_dta

# Household-file columns used as categorical features (no amounts or values).
HH_CATEGORICAL = {
    "ur": "urban/rural",
    "s5aq1": "type of habitat",
    "s5aq2": "type of dwelling",
    "s5aq7": "owner of dwelling",
    "s5cq1": "main water source",
    "s5cq14": "electricity connection (grid / solar / both / no)",
    "s5cq16": "main lighting source",
    "s5cq21": "primary cook stove",
    "s5cq22a": "primary cooking fuel",
    "s5cq25": "toilet type",
    "s5dq1": "wall material",
    "s5dq2": "roof material",
    "s5dq3": "floor material",
}
HH_YESNO = {
    "s5cq20a": "internet connection",
    "s5cq26": "toilet shared",
    "s5eq1": "hit by a shock (12m)",
    "s7aq4": "owns livestock",
    "s7a2q1": "ever received Girinka cow",
}
HH_NUMERIC = {
    "s5aq3": "sleeping rooms",
    "s5cq2b": "minutes to fetch water",
    "s7aq4a": "cattle",
    "s7aq4b": "goats",
    "s7aq4c": "sheep",
    "s7aq4d": "pigs",
    "s7aq4e": "poultry",
}
PERSON_COLS = ["hhid", "s1q1", "s1q2", "s1q3y", "s1q4", "s3q2", "s3q3",
               "s3q7", "s3q8", "s3q9", "s3q10", "s3q11", "s3q12",
               "s4aq1", "s4aq2", "s4bq4", "s4bq8", "s4bq10", "s4bq15", "s4bq23c",
               "s6aq5", "s6aq6"]
EDU_ORDER = {"ECD": 0, "Nursery": 0, "Primary": 1, "INGOBOKA /Vocational training": 2,
             "Lower secondary": 2, "Upper secondary": 3, "Tertiary": 4}
DIFFICULTY = ["s3q7", "s3q8", "s3q9", "s3q10", "s3q11", "s3q12"]


def person_features(raw: Path) -> tuple[pd.DataFrame, dict]:
    p = read_dta(raw / "CS_S0_S1_S2_S3_S4_S6A_S6B_S6C_Person.dta", columns=PERSON_COLS)
    age = pd.to_numeric(p["s1q3y"], errors="coerce")
    edu = p["s4aq2"].astype(str).map(EDU_ORDER).fillna(0)
    # Washington Group style: any answer other than "No difficulty" counts.
    disabled = np.zeros(len(p), dtype=bool)
    for c in DIFFICULTY:
        s = p[c].astype(str).str.lower()
        disabled |= p[c].notna().to_numpy() & ~s.str.startswith("no").to_numpy()
    p = p.assign(
        age=age, edu=edu, disabled=disabled,
        child=age < 15, elderly=age >= 65, working_age=(age >= 15) & (age < 65),
        female=p["s1q1"].astype(str).str.lower().eq("female"),
        insured=is_yes(p["s3q2"]),
        cbhi=p["s3q3"].astype(str).str.startswith("CBHI"),
        literate=is_yes(p["s4bq4"]),
        phone=is_yes(p["s4bq8"]),
        smartphone=p["s4bq10"].astype(str).str.lower().str.contains("smart"),
        internet=is_yes(p["s4bq15"]),
        momo=is_yes(p["s4bq23c"]),
        wage_job=is_yes(p["s6aq5"]),
        nonfarm_biz=is_yes(p["s6aq6"]),
    )
    g = p.groupby("hhid")
    adults = p[age >= 15].groupby("hhid")
    f = pd.DataFrame({
        "hh_size": g.size(),
        "share_children": g["child"].mean(),
        "share_elderly": g["elderly"].mean(),
        "share_female": g["female"].mean(),
        "n_disabled": g["disabled"].sum(),
        "dependency_ratio": (g["child"].sum() + g["elderly"].sum()) / g["working_age"].sum().clip(lower=1),
        "max_edu": g["edu"].max(),
        "share_adults_literate": adults["literate"].mean(),
        "share_insured": g["insured"].mean(),
        "share_cbhi": g["cbhi"].mean(),
        "n_phones": g["phone"].sum(),
        "any_smartphone": g["smartphone"].max(),
        "any_internet_user": g["internet"].max(),
        "any_momo_user": g["momo"].max(),
        "n_wage_workers": g["wage_job"].sum(),
        "any_nonfarm_biz": g["nonfarm_biz"].max(),
    })
    head = p[p["s1q2"].astype(str).str.startswith("Household head")].set_index("hhid")
    assert head.index.is_unique, "more than one head in a household"
    f["head_age"] = head["age"]
    f["head_female"] = head["female"]
    f["head_edu"] = head["edu"]
    f["head_disabled"] = head["disabled"]
    f["head_marital"] = head["s1q4"].astype("string")
    f["head_never_school"] = head["s4aq1"].astype(str).str.lower().eq("no")
    doc = {c: "person file (aggregated)" for c in f.columns}
    return f, doc


def durable_features(raw: Path) -> tuple[pd.DataFrame, dict]:
    d = read_dta(raw / "CS_S10B_durables.dta", columns=["hhid", "s10bq0", "s10bq2"])
    d["n"] = pd.to_numeric(d["s10bq2"], errors="coerce").fillna(0)
    wide = d.pivot_table(index="hhid", columns="s10bq0", values="n", aggfunc="sum", observed=True)
    wide.columns = ["dur_" + "".join(ch if ch.isalnum() else "_" for ch in str(c).strip().lower())
                    .strip("_")[:30] for c in wide.columns]
    wide["dur_n_types"] = (wide > 0).sum(axis=1)
    return wide, {c: "durables file (count owned, s10bq2)" for c in wide.columns}


def main(raw: Path, out: Path) -> None:
    hh = read_dta(raw / "CS_S01_S5_S7_Household.dta",
                  columns=["hhid", "district", *HH_CATEGORICAL, *HH_YESNO, *HH_NUMERIC])
    assert hh["hhid"].is_unique
    f = hh[["hhid"]].copy()
    doc = {"district": "household file: district"}
    f["district"] = hh["district"].astype("string")
    for c, lab in HH_CATEGORICAL.items():
        f[c] = hh[c].astype("string")
        doc[c] = f"household file: {lab}"
    for c, lab in HH_YESNO.items():
        f[c] = is_yes(hh[c])
        doc[c] = f"household file: {lab}"
    for c, lab in HH_NUMERIC.items():
        f[c] = pd.to_numeric(hh[c], errors="coerce")
        doc[c] = f"household file: {lab}"
    for c in ["s7aq4a", "s7aq4b", "s7aq4c", "s7aq4d", "s7aq4e"]:
        f[c] = f[c].fillna(0)  # skipped when the household has no livestock
    f = f.set_index("hhid")

    for builder in (person_features, durable_features):
        part, part_doc = builder(raw)
        f = f.join(part, how="left")
        doc.update(part_doc)
    assert f["hh_size"].notna().all(), "household without person rows"
    f["rooms_per_person"] = f["s5aq3"] / f["hh_size"]
    doc["rooms_per_person"] = "derived: sleeping rooms / household size"

    f = f.reset_index()
    out.parent.mkdir(parents=True, exist_ok=True)
    f.to_parquet(out, index=False)
    rep = Path("reports/feature_list.csv")
    rep.parent.mkdir(exist_ok=True)
    pd.DataFrame({"feature": list(doc), "source": list(doc.values())}).to_csv(rep, index=False)
    print(f"Wrote {out}  shape={f.shape}")
    print(f"Wrote {rep}  ({len(doc)} features)")
    miss = f.isna().mean().sort_values(ascending=False)
    print("Most missing:\n" + miss[miss > 0].head(10).round(3).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw/Cross_Section"))
    ap.add_argument("--out", type=Path, default=Path("data/processed/features.parquet"))
    a = ap.parse_args()
    main(a.raw, a.out)
