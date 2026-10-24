"""Targeting simulation: same number of beneficiaries, current VUP vs model-based.

Scores are out-of-fold predictions from src/model.py (logit, no_program variant),
so every household is scored by a model that never saw its cluster.

Allocation rules (each selects the same weighted number of households)
  current            VUP as reported in the survey
  model_national     highest-scoring households nationwide
  model_same_quota   highest-scoring within each district, keeping each district's
                     current number of beneficiaries (no budget moves between districts)
  model_poor_quota   district budgets proportional to their number of poor households,
                     highest-scoring within each district

Budgets
  survey   current VUP households as reported (~380k)
  admin    scaled to MINALOC's count (survey x admin/survey component ratio, ~500k);
           compared against the undercount-corrected range for current VUP.

Usage:
    python src/targeting.py
Writes reports/targeting_national.csv and reports/targeting_district.csv (aggregates).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import svy_ratio, svy_total

SCORE = "logit_no_program"
ADMIN_OVER_SURVEY = 540_684 / 410_039  # component-pair ratio from src/reconcile_vup.py
KIGALI = {"Nyarugenge", "Gasabo", "Kicukiro"}


def top_share(score, w, budget_w):
    """Select highest scores until the selected weight reaches budget_w."""
    order = np.argsort(-score)
    sel = np.zeros(len(score), bool)
    sel[order[np.cumsum(w[order]) <= budget_w]] = True
    return sel


def within_district(df, quotas):
    sel = np.zeros(len(df), bool)
    for d, idx in df.groupby("district").indices.items():
        sel[idx] = top_share(df[SCORE].to_numpy()[idx], df["weight"].to_numpy()[idx], quotas.get(d, 0.0))
    return sel


def evaluate(df, sel):
    a = (df["district"], df["clust"])
    w = df["weight"]
    poor, xpoor = df["poor"].to_numpy(), df["extreme_poor"].to_numpy()
    cov, se = svy_ratio(sel & poor, poor, w, *a)
    xcov, _ = svy_ratio(sel & xpoor, xpoor, w, *a)
    inc, inc_se = svy_ratio(sel & ~poor, sel, w, *a)
    return {"selected_hh": svy_total(sel, w, *a)[0],
            "poor_reached": svy_total(sel & poor, w, *a)[0],
            "exclusion_error": 100 * (1 - cov),
            "exclusion_error_lo": 100 * (1 - cov - 1.96 * se), "exclusion_error_hi": 100 * (1 - cov + 1.96 * se),
            "inclusion_error": 100 * inc,
            "inclusion_error_lo": 100 * (inc - 1.96 * inc_se), "inclusion_error_hi": 100 * (inc + 1.96 * inc_se),
            "extreme_poor_reached_pct": 100 * xcov}


def main(table: Path, oof: Path) -> None:
    df = pd.read_parquet(table, columns=["hhid", "district", "clust", "weight", "poor", "extreme_poor", "vup_any"])
    df = df.merge(pd.read_parquet(oof, columns=["hhid", SCORE]), on="hhid", validate="1:1")
    df["district"] = df["district"].astype(str)
    for c in ["poor", "extreme_poor", "vup_any"]:
        df[c] = df[c].astype(bool)
    w = df["weight"].to_numpy()

    cur_quota = df[df.vup_any].groupby("district")["weight"].sum()
    poor_hh = df[df.poor].groupby("district")["weight"].sum()

    nat_rows, dist_rows = [], []
    for budget_name, scale in [("survey", 1.0), ("admin", ADMIN_OVER_SURVEY)]:
        budget = scale * cur_quota.sum()
        rules = {
            "model_national": top_share(df[SCORE].to_numpy(), w, budget),
            "model_same_quota": within_district(df, (scale * cur_quota).to_dict()),
            "model_poor_quota": within_district(df, (budget * poor_hh / poor_hh.sum()).to_dict()),
        }
        if budget_name == "survey":
            rules = {"current": df["vup_any"].to_numpy(), **rules}
        for rule, sel in rules.items():
            nat_rows.append({"budget": budget_name, "rule": rule, **evaluate(df, sel)})
            if budget_name == "survey":
                for d, idx in df.groupby("district").indices.items():
                    g = df.iloc[idx]
                    s = sel[idx]
                    dist_rows.append({"district": d, "rule": rule,
                                      "selected_hh": (g.weight * s).sum(),
                                      "poor_hh": (g.weight * g.poor).sum(),
                                      "poor_reached": (g.weight * (s & g.poor)).sum()})

    nat = pd.DataFrame(nat_rows)
    dist = pd.DataFrame(dist_rows)
    dist["exclusion_error"] = 100 * (1 - dist.poor_reached / dist.poor_hh)
    wide = dist.pivot(index="district", columns="rule", values=["selected_hh", "poor_reached", "exclusion_error"])
    wide.columns = [f"{v}_{r}" for v, r in wide.columns]
    wide["poor_hh"] = dist.groupby("district")["poor_hh"].first()
    wide["kigali_flag"] = wide.index.isin(KIGALI)
    wide["extra_poor_reached_same_quota"] = wide["poor_reached_model_same_quota"] - wide["poor_reached_current"]
    wide = wide.sort_values("extra_poor_reached_same_quota", ascending=False).reset_index()

    Path("reports").mkdir(exist_ok=True)
    nat.round(2).to_csv("reports/targeting_national.csv", index=False)
    wide.round(1).to_csv("reports/targeting_district.csv", index=False)

    pd.set_option("display.width", 220)
    f = lambda v: f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.1f}"
    print(nat.to_string(index=False, float_format=f))
    print("\nCurrent VUP at admin scale (undercount-corrected, src/reconcile_vup.py): exclusion 68.4-79.0%")
    print("\nDistricts, survey budget (exclusion error %, poor households reached):")
    print(wide[["district", "poor_hh", "exclusion_error_current", "exclusion_error_model_same_quota",
                "exclusion_error_model_poor_quota", "selected_hh_current", "selected_hh_model_poor_quota",
                "extra_poor_reached_same_quota", "kigali_flag"]].to_string(index=False, float_format=f))
    print("Wrote reports/targeting_national.csv, reports/targeting_district.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", type=Path, default=Path("data/processed/hh_table.parquet"))
    ap.add_argument("--oof", type=Path, default=Path("data/processed/oof_predictions.parquet"))
    a = ap.parse_args()
    main(a.table, a.oof)
