"""Coverage and targeting errors of VUP, nationally by component and by district.

Household-level shares use `weight`; the district poverty rate uses `pop_wt`
(person level, matches NISR). 95% CIs are design-based (strata = district,
cluster = clust). All outputs are aggregates.

Definitions (household level)
  coverage            share of households in the group receiving the component
  poor_coverage       share of poor households receiving it (1 - exclusion error)
  exclusion_error     share of poor households NOT receiving it
  inclusion_error     share of recipients who are not poor
  poor_uncovered      weighted number of poor households without any VUP

Usage:
    python src/coverage.py
Writes reports/coverage_national.csv and reports/coverage_district.csv.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import svy_ratio, svy_total

COMPONENTS = {"vup_any": "Any VUP (5 components)", "ds": "Direct Support",
              "nsds": "Nutrition-Sensitive DS", "cpw": "Classic Public Works",
              "epw": "Expanded Public Works", "fin": "Financial Services"}
KIGALI = {"Nyarugenge", "Gasabo", "Kicukiro"}
MIN_POOR_SAMPLE = 50  # below this, district error rates are flagged as unreliable


def share(df, y, domain, wcol="weight"):
    """Share of y within domain, with 95% CI, as percentages."""
    r, se = svy_ratio(df[y] & df[domain] if domain else df[y],
                      df[domain] if domain else np.ones(len(df)),
                      df[wcol], df["district"], df["clust"])
    # Normal-approximation CI, clipped to [0, 100] (it can overshoot for small domains).
    return 100 * r, 100 * max(r - 1.96 * se, 0.0), 100 * min(r + 1.96 * se, 1.0)


def metrics(df: pd.DataFrame, comp: str) -> dict:
    df = df.assign(nonpoor=~df["poor"], all=True)
    out = {}
    for name, y, dom in [("coverage", comp, None), ("poor_coverage", comp, "poor"),
                         ("extreme_poor_coverage", comp, "extreme_poor")]:
        out[name], out[name + "_lo"], out[name + "_hi"] = share(df, y, dom)
    out["exclusion_error"] = 100 - out["poor_coverage"]
    out["exclusion_error_lo"], out["exclusion_error_hi"] = 100 - out["poor_coverage_hi"], 100 - out["poor_coverage_lo"]
    # inclusion error: non-poor among recipients
    out["inclusion_error"], out["inclusion_error_lo"], out["inclusion_error_hi"] = share(df, "nonpoor", comp)
    out["recipients"] = svy_total(df[comp], df["weight"], df["district"], df["clust"])[0]
    out["poor_uncovered"] = svy_total(df["poor"] & ~df[comp], df["weight"], df["district"], df["clust"])[0]
    out["sample_hh"], out["sample_poor"], out["sample_recipients"] = len(df), int(df["poor"].sum()), int(df[comp].sum())
    return out


def main(table: Path) -> None:
    df = pd.read_parquet(table)
    df["district"] = df["district"].astype(str)
    for c in ["poor", "extreme_poor", *COMPONENTS]:
        df[c] = df[c].astype(bool)

    nat = pd.DataFrame([{"component": lab, **metrics(df, k)} for k, lab in COMPONENTS.items()])

    rows = []
    for d, g in df.groupby("district"):
        pov, pov_lo, pov_hi = share(g, "poor", None, wcol="pop_wt")
        rows.append({"district": d, "province": str(g["province"].iloc[0]),
                     "poverty_rate": pov, "poverty_rate_lo": pov_lo, "poverty_rate_hi": pov_hi,
                     **metrics(g, "vup_any")})
    dist = pd.DataFrame(rows)
    dist["kigali_flag"] = dist["district"].isin(KIGALI)
    dist["small_sample_flag"] = dist["sample_poor"] < MIN_POOR_SAMPLE
    # Rank by uncovered poor households only where estimates are reliable (CLAUDE.md: never rank Kigali).
    rankable = ~dist["kigali_flag"] & ~dist["small_sample_flag"]
    dist["rank_poor_uncovered"] = dist["poor_uncovered"].where(rankable).rank(ascending=False)
    dist["rank_exclusion_error"] = dist["exclusion_error"].where(rankable).rank(ascending=False)
    dist = dist.sort_values("poor_uncovered", ascending=False)

    Path("reports").mkdir(exist_ok=True)
    nat.round(2).to_csv("reports/coverage_national.csv", index=False)
    dist.round(2).to_csv("reports/coverage_district.csv", index=False)

    pd.set_option("display.width", 220)
    f = lambda v: f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.1f}"
    print("NATIONAL (household level, %)")
    print(nat[["component", "coverage", "poor_coverage", "poor_coverage_lo", "poor_coverage_hi",
               "extreme_poor_coverage", "inclusion_error", "inclusion_error_lo", "inclusion_error_hi",
               "recipients"]].to_string(index=False, float_format=f))
    print("\nDISTRICTS (any VUP), sorted by poor households left uncovered")
    print(dist[["district", "poverty_rate", "coverage", "exclusion_error", "exclusion_error_lo",
                "exclusion_error_hi", "inclusion_error", "poor_uncovered", "sample_poor",
                "kigali_flag", "rank_poor_uncovered"]].to_string(index=False, float_format=f))
    r = np.corrcoef(dist["poverty_rate"], dist["coverage"])[0, 1]
    print(f"\nCorrelation across districts, poverty rate vs coverage: {r:.2f}")
    print("Wrote reports/coverage_national.csv, reports/coverage_district.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", type=Path, default=Path("data/processed/hh_table.parquet"))
    main(ap.parse_args().table)
