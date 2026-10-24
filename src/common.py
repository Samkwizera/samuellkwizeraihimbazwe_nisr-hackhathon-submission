"""Shared helpers for reading EICV7 Stata files."""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Some EICV7 text fields are not valid UTF-8; pandas falls back to latin-1 and warns.
warnings.filterwarnings("ignore", category=UnicodeWarning)


def read_dta(path: Path, columns=None) -> pd.DataFrame:
    """Read a .dta file and make `hhid` a clean int64 key.

    hhid is stored as float32 in some files; rounding to int64 keeps merges exact
    as long as every file stores it the same way (build_table.py asserts this).
    """
    df = pd.read_stata(path, columns=columns)
    if "hhid" in df.columns:
        df["hhid"] = np.round(df["hhid"]).astype("int64")
    return df


def is_yes(series: pd.Series) -> pd.Series:
    """True where a categorical/string answer is 'Yes' (NaN -> False)."""
    return series.astype(str).str.strip().str.lower().eq("yes")


def svy_total(y, w, strata, clust) -> tuple[float, float]:
    """Weighted total and its design-based SE (stratified cluster, with replacement).

    Linearization: sum cluster totals of w*y within each stratum and use the
    between-cluster variance, n_h/(n_h-1) * sum (z_hc - mean_h)^2.
    """
    d = pd.DataFrame({"z": np.asarray(y, float) * np.asarray(w, float),
                      "h": np.asarray(strata), "c": np.asarray(clust)})
    z = d.groupby(["h", "c"], observed=True)["z"].sum()
    var = 0.0
    for _, zh in z.groupby(level="h", observed=True):
        n = len(zh)
        if n > 1:
            var += n / (n - 1) * ((zh - zh.mean()) ** 2).sum()
    return float(d["z"].sum()), var ** 0.5


def svy_ratio(y, x, w, strata, clust) -> tuple[float, float]:
    """Weighted ratio sum(w*y)/sum(w*x) and its linearized SE (e.g. a mean or share)."""
    y, x, w = (np.asarray(a, float) for a in (y, x, w))
    r = (w * y).sum() / (w * x).sum()
    _, se = svy_total((y - r * x) / (w * x).sum(), w, strata, clust)
    return float(r), se
