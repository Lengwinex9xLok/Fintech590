"""Gate 2: baseline XGBoost early-warning model on the out-of-time split, global SHAP ranking,
prune to the top features, retrain, and compare out-of-time PR-AUC.

Output: data/phase3/shap_global_full.png / .csv     mean |SHAP| for every candidate
        data/phase3/feature_log.csv                  before/after pruning with OOT metrics
        data/phase3/fact_score.parquet               P(stress, next 4Q) for every bank-quarter + model version
        data/phase3/fact_shap.parquet                per-bank SHAP values (pruned model), for the waterfall
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, precision_recall_curve

from config import GAP_END, MODEL_VERSION, OUT_DIR, TEST_END, TRAIN_END, TRAIN_START

KEEP_N = 12
K_LIST = [50, 100]

f = pd.read_parquet(OUT_DIR / "features.parquet")
NON_FEATURES = {"rssd_id", "quarter", "form_type", "asset_tier", "target", "in_breach", "exits_panel_4q",
                "fwd_quarters_observed",
                "total_assets"}
FEATS = [c for c in f.columns if c not in NON_FEATURES]

lab = f[f["target"].notna()]
train = lab[(lab["quarter"] >= TRAIN_START) & (lab["quarter"] <= TRAIN_END)]
test = lab[(lab["quarter"] > GAP_END) & (lab["quarter"] <= TEST_END)]
print(f"train {len(train):,} rows (base {train.target.mean():.2%}), "
      f"test {len(test):,} rows (base {test.target.mean():.2%})")

# Every non-default choice is written down: library defaults are vendor assumptions (SR 26-2).
PARAMS = dict(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
              min_child_weight=5, eval_metric="aucpr", tree_method="hist", random_state=590,
              scale_pos_weight=float((train.target == 0).sum() / max((train.target == 1).sum(), 1)))


def precision_at_k(df, score, k):
    """Of the k highest-scored banks in each test quarter, share that breached; averaged over quarters."""
    d = df.assign(s=score)
    return d.groupby("quarter").apply(lambda x: x.nlargest(k, "s")["target"].mean(), include_groups=False).mean()


def recall_at_k(df, score, k):
    d = df.assign(s=score)
    hits = d.groupby("quarter").apply(lambda x: x.nlargest(k, "s")["target"].sum(), include_groups=False).sum()
    return hits / d["target"].sum()


def tree_shap(model, X):
    """Exact Tree SHAP via XGBoost's built-in pred_contribs (same algorithm as shap.TreeExplainer,
    no extra dependency). Returns (per-feature SHAP in log-odds, base value)."""
    c = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)
    return c[:, :-1], float(c[0, -1])


def fit_eval(feats, tag):
    m = xgb.XGBClassifier(**PARAMS)
    m.fit(train[feats], train["target"])
    s = m.predict_proba(test[feats])[:, 1]
    res = {"step": tag, "n_features": len(feats), "oot_pr_auc": average_precision_score(test.target, s),
           "test_base_rate": test.target.mean()}
    for k in K_LIST:
        res[f"precision_at_{k}"] = precision_at_k(test, s, k)
        res[f"recall_at_{k}"] = recall_at_k(test, s, k)
    return m, s, res


# 1. Full candidate set
m_full, s_full, r_full = fit_eval(FEATS, "all candidates")
bg = train.sample(min(5000, len(train)), random_state=590)
sv, base_full = tree_shap(m_full, bg[FEATS])
glob = pd.Series(np.abs(sv).mean(axis=0), index=FEATS).sort_values(ascending=False)
glob.rename("mean_abs_shap").to_csv(OUT_DIR / "shap_global_full.csv")

# Correlation check before cutting (correlated features split credit)
corr = train[FEATS].sample(min(20000, len(train)), random_state=590).corr(method="spearman").abs().fillna(0)
top = glob.index[:KEEP_N]
near_dupes = [(a, b, round(corr.loc[a, b], 2)) for i, a in enumerate(glob.index[:25])
              for b in glob.index[i + 1:25] if corr.loc[a, b] > 0.85]

fig, ax = plt.subplots(figsize=(8, 9))
show = glob.head(25)[::-1]
KEEP_SET = set()
for c in glob.index:   # same rule as step 2b, computed here so the chart can mark kept features
    if all(corr.loc[c, k] <= 0.85 for k in KEEP_SET):
        KEEP_SET.add(c)
    if len(KEEP_SET) == KEEP_N:
        break
ax.barh(show.index, show.values, color=["#2b6cb0" if i in KEEP_SET else "#a0aec0" for i in show.index])
ax.set_xlabel("mean |SHAP| (log-odds), train background sample")
ax.set_title(f"Global SHAP, all {len(FEATS)} candidates (top 25 shown; blue = kept)\n"
             f"Base value E[f(x)] = {base_full:.3f} log-odds, "
             f"background = {len(bg):,} train bank-quarters {train.quarter.min():%Y}-{train.quarter.max():%Y}",
             fontsize=10)
for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
plt.tight_layout()
plt.savefig(OUT_DIR / "shap_global_full.png", dpi=160)

# 2a. Naive cut: top 12 by mean |SHAP|
NAIVE = list(top)
_, _, r_naive = fit_eval(NAIVE, f"top {KEEP_N} by mean |SHAP| (naive)")

# 2b. Correlation-aware cut: walk the SHAP ranking, skip a feature if |Spearman rho| > 0.85
# with one already kept (near-duplicates split credit; keep the stronger one, free the slot)
KEEP = []
for c in glob.index:
    if all(corr.loc[c, k] <= 0.85 for k in KEEP):
        KEEP.append(c)
    if len(KEEP) == KEEP_N:
        break
m_pr, s_pr, r_pr = fit_eval(KEEP, f"top {KEEP_N} by mean |SHAP|, deduped at rho 0.85")

log = pd.DataFrame([r_full, r_naive, r_pr])
log["features"] = [", ".join(FEATS), ", ".join(NAIVE), ", ".join(KEEP)]
log.to_csv(OUT_DIR / "feature_log.csv", index=False)
print("\n", log.drop(columns="features").round(4).to_string(index=False))
print("\nKept:", KEEP)
if near_dupes:
    print("\nNear-duplicate pairs among the top 25 (|rho| > 0.85), check before cutting:")
    for a, b, r in near_dupes:
        print(f"  {a} ~ {b}: {r}")

# 3. Score every bank-quarter with the pruned model; SHAP per bank for the drill-through waterfall
m_pr.save_model(OUT_DIR / f"{MODEL_VERSION}.json")
score = f[["rssd_id", "quarter"]].copy()
score["p_stress_4q"] = m_pr.predict_proba(f[KEEP])[:, 1]
score["model_version"] = MODEL_VERSION
score.to_parquet(OUT_DIR / "fact_score.parquet", index=False)

recent = f[f["quarter"] >= f["quarter"].max() - pd.DateOffset(months=21)]   # last 8 quarters
sv_pr, base_pr = tree_shap(m_pr, recent[KEEP])
fs = pd.DataFrame(sv_pr, columns=KEEP)
fs["rssd_id"], fs["quarter"] = recent["rssd_id"].values, recent["quarter"].values
fs = fs.melt(id_vars=["rssd_id", "quarter"], var_name="metric_key", value_name="shap_logodds")
fs["base_value_logodds"] = base_pr
fs.to_parquet(OUT_DIR / "fact_shap.parquet", index=False)

prec, rec, _ = precision_recall_curve(test.target, s_pr)
pd.DataFrame({"precision": prec, "recall": rec}).iloc[::max(1, len(prec) // 500)].to_csv(
    OUT_DIR / "oot_pr_curve.csv", index=False)
json.dump({"model_version": MODEL_VERSION, "params": PARAMS, "features": KEEP,
           "train_end": TRAIN_END, "gap_end": GAP_END, "test_end": TEST_END},
          open(OUT_DIR / "model_card_inputs.json", "w"), indent=2, default=str)
print(f"\nScored {len(score):,} bank-quarters -> fact_score.parquet")
