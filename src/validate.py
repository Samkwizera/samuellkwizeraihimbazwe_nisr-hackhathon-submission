"""Check our weights against NISR's published district poverty rates.

Source: EICV7 Methodological Note, Appendix 1 (person-level headcount, %).
Run this first: if it fails, do not trust anything downstream.

Usage:
    python src/validate.py --raw data/raw/Cross_Section
"""
import argparse
from pathlib import Path

import pandas as pd

from common import read_dta

PUBLISHED = {
    "Nyarugenge": 6.8, "Gasabo": 11.1, "Kicukiro": 6.9, "Nyanza": 43.3, "Gisagara": 45.6,
    "Nyaruguru": 39.7, "Huye": 24.2, "Nyamagabe": 51.4, "Ruhango": 15.0, "Muhanga": 15.0,
    "Kamonyi": 39.7, "Karongi": 38.2, "Rutsiro": 40.8, "Rubavu": 38.8, "Nyabihu": 20.2,
    "Ngororero": 30.2, "Rusizi": 44.2, "Nyamasheke": 42.8, "Rulindo": 21.6, "Gakenke": 24.5,
    "Musanze": 21.0, "Burera": 22.0, "Gicumbi": 13.3, "Rwamagana": 23.8, "Nyagatare": 36.4,
    "Gatsibo": 18.4, "Kayonza": 36.6, "Kirehe": 14.2, "Ngoma": 30.9, "Bugesera": 23.7,
}


def main(raw: Path) -> None:
    pov = read_dta(raw / "CS_EICV7_poverty_file.dta")
    pov["poor"] = pov["pov_jan"].astype(str).eq("Poor")
    mine = pov.groupby("district", observed=True).apply(
        lambda x: 100 * (x.poor * x.pop_wt).sum() / x.pop_wt.sum()
    )
    cmp = pd.DataFrame({"ours": mine.round(1), "published": pd.Series(PUBLISHED)})
    cmp["diff"] = (cmp["ours"] - cmp["published"]).round(2)
    print(cmp.to_string())
    worst = cmp["diff"].abs().max()
    print(f"\nLargest absolute difference: {worst}")
    assert worst < 0.15, "District rates do not match NISR - check weights/columns"
    print("OK: weights reproduce NISR's published district poverty rates.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, default=Path("data/raw/Cross_Section"))
    main(p.parse_args().raw)
