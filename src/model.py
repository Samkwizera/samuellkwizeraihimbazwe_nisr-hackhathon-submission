"""Proxy-targeting model: predict household poverty from leakage-free features.

Models  : logistic regression (baseline), histogram gradient boosting.
Variants: "full" uses all features; "no_program" drops features that partly reflect
          existing programme targeting (CBHI insurance, Girinka cow), so the model
          does not just learn who programmes already reached.
CV      : 5-fold StratifiedGroupKFold grouped by `clust` (no cluster in both train
          and test). Training and scoring use household weights.
Scoring : weighted AUC, and recall/precision of poor households when the top-k%
          of households (weighted) are selected, k = current VUP coverage and the
          poverty rate. Recall at a fixed budget is what matters for targeting.

Usage:
    python src/model.py
Writes reports/model_metrics.csv and reports/model_importance.csv (aggregates) and
data/processed/oof_predictions.parquet (household scores, git-ignored, for task 5).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROGRAM_FEATURES = ["share_insured", "share_cbhi", "s7a2q1"]
N_FOLDS = 5
SEED = 0


def make_model(kind: str, cat: list[str], num: list[str]):
    num_steps = [SimpleImputer(strategy="median")]
    if kind == "logit":
        num_steps.append(StandardScaler())
    pre = ColumnTransformer([
        ("cat", make_pipeline(SimpleImputer(strategy="constant", fill_value="missing"),
                              OneHotEncoder(handle_unknown="ignore", min_frequency=20,
                                            sparse_output=False)), cat),
        ("num", make_pipeline(*num_steps), num),
    ])
    if kind == "logit":
        clf = LogisticRegression(C=0.5, max_iter=3000)
    else:
        clf = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=400, max_leaf_nodes=31,
                                             min_samples_leaf=40, l2_regularization=1.0,
                                             early_stopping=False, random_state=SEED)
    return make_pipeline(pre, clf)


def recall_at_budget(y, score, w, budget):
    """Select highest-scoring households until `budget` share of weighted households."""
    order = np.argsort(-score)
    cw = np.cumsum(w[order]) / w.sum()
    sel = np.zeros(len(y), bool)
    sel[order[cw <= budget]] = True
    tp = (w * y * sel).sum()
    return tp / (w * y).sum(), tp / (w * sel).sum()


def main(table: Path, features: Path) -> None:
    lab = pd.read_parquet(table, columns=["hhid", "poor", "weight", "clust", "vup_any"])
    X = pd.read_parquet(features)
    df = lab.merge(X, on="hhid", validate="1:1")
    y, w, groups = df["poor"].astype(int).to_numpy(), df["weight"].to_numpy(), df["clust"].to_numpy()
    feat_all = [c for c in X.columns if c != "hhid"]
    for c in feat_all:
        if df[c].dtype == bool:
            df[c] = df[c].astype(float)
    budgets = {"vup_coverage": (w * df["vup_any"]).sum() / w.sum(), "poverty_rate": (w * y).sum() / w.sum()}

    folds = list(StratifiedGroupKFold(N_FOLDS, shuffle=True, random_state=SEED).split(df, y, groups))
    rows, oof_all, imp_rows = [], {}, []
    for variant, drop in [("full", []), ("no_program", PROGRAM_FEATURES)]:
        feats = [c for c in feat_all if c not in drop]
        cat = [c for c in feats if df[c].dtype.name in ("string", "object", "category")]
        num = [c for c in feats if c not in cat]
        Xv = df[feats].copy()
        Xv[cat] = Xv[cat].astype(object).where(Xv[cat].notna(), "missing")
        for kind in ["logit", "gbm"]:
            oof = np.zeros(len(df))
            for tr, te in folds:
                m = make_model(kind, cat, num)
                m.fit(Xv.iloc[tr], y[tr], **{m.steps[-1][0] + "__sample_weight": w[tr]})
                oof[te] = m.predict_proba(Xv.iloc[te])[:, 1]
            r = {"variant": variant, "model": kind, "n_features": len(feats),
                 "auc": roc_auc_score(y, oof, sample_weight=w),
                 "auc_fold_sd": np.std([roc_auc_score(y[te], oof[te], sample_weight=w[te]) for _, te in folds])}
            for b, share in budgets.items():
                r[f"budget_{b}"] = share
                r[f"recall_at_{b}"], r[f"precision_at_{b}"] = recall_at_budget(y, oof, w, share)
            rows.append(r)
            oof_all[f"{kind}_{variant}"] = oof
            print(f"{variant:10s} {kind:5s} AUC {r['auc']:.3f} (fold sd {r['auc_fold_sd']:.3f})  "
                  f"recall@{100 * budgets['vup_coverage']:.1f}% = {100 * r['recall_at_vup_coverage']:.1f}%  "
                  f"recall@{100 * budgets['poverty_rate']:.1f}% = {100 * r['recall_at_poverty_rate']:.1f}%")

            if kind == "gbm" and variant == "no_program":
                # Permutation importance on one held-out fold (raw columns, AUC drop).
                tr, te = folds[0]
                m = make_model(kind, cat, num)
                m.fit(Xv.iloc[tr], y[tr], **{m.steps[-1][0] + "__sample_weight": w[tr]})
                pi = permutation_importance(m, Xv.iloc[te], y[te], scoring="roc_auc", n_repeats=5,
                                            random_state=SEED, sample_weight=w[te])
                imp_rows = sorted(zip(feats, pi.importances_mean, pi.importances_std), key=lambda t: -t[1])

    # Reference: how the current VUP allocation does at its own budget.
    cur_recall = (w * y * df["vup_any"]).sum() / (w * y).sum()
    cur_prec = (w * y * df["vup_any"]).sum() / (w * df["vup_any"]).sum()
    rows.append({"variant": "current", "model": "VUP as reported", "auc": np.nan,
                 "budget_vup_coverage": budgets["vup_coverage"],
                 "recall_at_vup_coverage": cur_recall, "precision_at_vup_coverage": cur_prec})
    print(f"current VUP (survey):  recall {100 * cur_recall:.1f}%  precision {100 * cur_prec:.1f}% "
          f"at {100 * budgets['vup_coverage']:.1f}% coverage")

    Path("reports").mkdir(exist_ok=True)
    pd.DataFrame(rows).round(4).to_csv("reports/model_metrics.csv", index=False)
    imp = pd.DataFrame(imp_rows, columns=["feature", "auc_drop", "auc_drop_sd"])
    imp.round(5).to_csv("reports/model_importance.csv", index=False)
    print("\nTop features (gbm, no_program, permutation AUC drop):")
    print(imp.head(15).to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    out = df[["hhid"]].assign(fold=0, **oof_all)
    for i, (_, te) in enumerate(folds):
        out.loc[out.index[te], "fold"] = i
    out.to_parquet("data/processed/oof_predictions.parquet", index=False)
    print("Wrote reports/model_metrics.csv, reports/model_importance.csv, data/processed/oof_predictions.parquet")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", type=Path, default=Path("data/processed/hh_table.parquet"))
    ap.add_argument("--features", type=Path, default=Path("data/processed/features.parquet"))
    a = ap.parse_args()
    main(a.table, a.features)
