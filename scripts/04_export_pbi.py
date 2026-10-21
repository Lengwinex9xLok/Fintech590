"""Export the star schema Power BI imports (slide 35), small enough to commit.

Output: data/phase3/pbi/
    dim_bank.parquet          RSSD ID (PK), name, city, state, latest form type, asset tier, CBLR elector
    dim_quarter.parquet       quarter (PK), year, label, rate regime label
    dim_metric.csv            metric key (PK), friendly name, schedule, MDRM, construction, kept flag
    fact_score.parquet        bank x quarter: P(stress, next 4Q), flag, rank, deposits, outcome, model version
    fact_metric.parquet       bank x quarter x metric (kept features only, 2017+), long, with tier median
    fact_shap.parquet         bank x quarter x feature SHAP (last 8 quarters) + base value, for the waterfall
    threshold.json            flag threshold and how it was chosen
"""
import json

import numpy as np
import pandas as pd

from config import GAP_END, MODEL_VERSION, OUT_DIR, TEST_END, TRAIN_START

PBI = OUT_DIR / "pbi"
PBI.mkdir(exist_ok=True)

f = pd.read_parquet(OUT_DIR / "features.parquet")
p = pd.read_parquet(OUT_DIR / "panel_raw.parquet")
s = pd.read_parquet(OUT_DIR / "fact_score.parquet")
card = json.load(open(OUT_DIR / "model_card_inputs.json"))
KEEP = card["features"]

# ---- Flag threshold: sized to review capacity (slide 42) ------------------------------------
# The committee can review about K banks a quarter. Pick the score cutoff that, on the out of time
# test set (2023-2024), flags K banks per quarter on average. F1-optimal flagged ~420/quarter: not triage.
K_CAPACITY = 50
d = s.merge(f[["rssd_id", "quarter", "target"]], on=["rssd_id", "quarter"])
test = d[(d.quarter > GAP_END) & (d.quarter <= TEST_END) & d.target.notna()]
n_q = test.quarter.nunique()
THRESH = float(test.p_stress_4q.sort_values(ascending=False).iloc[K_CAPACITY * n_q - 1])
fl = test[test.p_stress_4q >= THRESH]
prec, rec = fl.target.mean(), fl.target.sum() / test.target.sum()
json.dump({"threshold": THRESH, "rule": f"cutoff that flags {K_CAPACITY} banks per quarter on average "
           "in the out of time test set (2023-2024)", "review_capacity_per_quarter": K_CAPACITY,
           "test_precision": float(prec), "test_recall": float(rec),
           "test_base_rate": float(test.target.mean()), "model_version": MODEL_VERSION,
           "note": "scores are not calibrated probabilities (scale_pos_weight); read as a ranking"},
          open(PBI / "threshold.json", "w"), indent=2)
print(f"flag threshold {THRESH:.3f}: test precision {prec:.2f}, recall {rec:.2f}, base {test.target.mean():.3f}")

# ---- fact_score -----------------------------------------------------------------------------
dep = (p["dep_domestic"].fillna(0) + p["dep_foreign"].fillna(0)).where(p["dep_domestic"].notna())
base = p[["rssd_id", "quarter", "total_assets"]].assign(total_deposits=dep)
fs = s.merge(base, on=["rssd_id", "quarter"]).merge(
    f[["rssd_id", "quarter", "in_breach", "target", "asset_tier"]], on=["rssd_id", "quarter"])
# Early warning flag only for banks NOT already in breach at t (they were excluded from training and
# are a known problem, not a warning). They are reported separately as "Already in breach".
fs["flag"] = ((fs.p_stress_4q >= THRESH) & (fs.in_breach == 0)).astype(int)
fs["status"] = np.select([fs.in_breach == 1, fs.flag == 1], ["Already in breach", "Flagged"], "Not flagged")
fs["risk_rank"] = fs.p_stress_4q.where(fs.in_breach == 0).groupby(fs.quarter).rank(ascending=False, method="first")
fs["flag_prev_q"] = fs.sort_values("quarter").groupby("rssd_id").flag.shift(1)
fs["mover"] = np.select([(fs.flag == 1) & (fs.flag_prev_q == 0), (fs.flag == 0) & (fs.flag_prev_q == 1)],
                        ["New flag", "Dropped off"], "")
fs["asset_tier"] = fs.asset_tier.astype(str)
fs["outcome"] = fs.target.map({1.0: "Breached within 4Q", 0.0: "No breach"}).fillna(
    pd.Series(np.where(fs.in_breach == 1, "Already in breach", "Not yet resolved"), index=fs.index))
fs["threshold"] = THRESH
fs = fs[fs.quarter >= TRAIN_START]
fs.to_parquet(PBI / "fact_score.parquet", index=False)

# ---- dim_quarter ----------------------------------------------------------------------------
q = pd.DataFrame({"quarter": sorted(p.quarter.unique())})
q["year"] = q.quarter.dt.year
q["quarter_label"] = q.quarter.dt.year.astype(str) + " Q" + q.quarter.dt.quarter.astype(str)
q["rate_regime"] = pd.cut(q.quarter, pd.to_datetime(["2000-01-01", "2020-03-01", "2022-03-01", "2023-09-01", "2100-01-01"]),
                          labels=["Pre COVID", "Zero rates", "Hiking", "Restrictive / easing"]).astype(str)
q["split"] = np.select([q.quarter < TRAIN_START, q.quarter <= card["train_end"], q.quarter <= GAP_END,
                        q.quarter <= TEST_END], ["History only", "Train", "Gap", "Test"], "Score live")
q.to_parquet(PBI / "dim_quarter.parquet", index=False)

# ---- dim_bank -------------------------------------------------------------------------------
db = pd.read_parquet(OUT_DIR / "dim_bank.parquet")
last = f.sort_values("quarter").groupby("rssd_id").last()[["asset_tier", "cblr_elector", "quarter"]]
db = db.drop(columns=["quarter"], errors="ignore").merge(
    last.rename(columns={"quarter": "last_filed"}).reset_index(), on="rssd_id", how="left")
db["asset_tier"] = db.asset_tier.astype(str)
db["bank_label"] = db.name.str.title() + " (" + db.rssd_id.astype(str) + ")"
db.to_parquet(PBI / "dim_bank.parquet", index=False)

# ---- dim_metric -----------------------------------------------------------------------------
NAMES = {
    "noncurrent_ratio": "Noncurrent loans / total loans", "log_assets": "Bank size (log10 assets)",
    "tier1_leverage": "Tier 1 leverage ratio (%)", "roa_chg4q": "ROA, 4 quarter change",
    "roa_pct": "ROA, percentile within size tier", "unreal_loss_t1_chg4q": "Unrealized losses / Tier 1, 4Q change",
    "cre_to_capital": "CRE / total risk based capital", "unreal_loss_t1": "Unrealized securities losses / Tier 1",
    "brokered_share": "Brokered deposits / total deposits", "tier1_leverage_chg4q": "Tier 1 leverage, 4 quarter change",
    "nim": "Net interest margin (annualized)", "loans_to_deposits": "Loans / deposits",
}
dm = pd.read_csv(OUT_DIR / "dim_metric.csv")
dm["kept"] = dm.metric_key.isin(KEEP).astype(int)
dm["friendly_name"] = dm.metric_key.map(NAMES).fillna(dm.description)
dm["shap_rank"] = dm.metric_key.map({k: i + 1 for i, k in enumerate(KEEP)})
dm["lineage"] = dm.schedule + " | " + dm.mdrm.fillna("") + " | " + dm["transform"]
dm.to_csv(PBI / "dim_metric.csv", index=False)

# ---- fact_metric (kept features, long) with size tier median for peer comparison -------------
fm = f.loc[f.quarter >= TRAIN_START, ["rssd_id", "quarter", "asset_tier"] + KEEP]
fm = fm.melt(id_vars=["rssd_id", "quarter", "asset_tier"], var_name="metric_key", value_name="value")
fm["tier_median"] = fm.groupby(["quarter", "asset_tier", "metric_key"], observed=True).value.transform("median")
fm["is_reported"] = fm.value.notna().astype(int)
fm = fm.drop(columns="asset_tier")
fm.to_parquet(PBI / "fact_metric.parquet", index=False)

# ---- fact_shap ------------------------------------------------------------------------------
sh = pd.read_parquet(OUT_DIR / "fact_shap.parquet")
sh = sh.merge(fm[["rssd_id", "quarter", "metric_key", "value"]], on=["rssd_id", "quarter", "metric_key"], how="left")
sh.to_parquet(PBI / "fact_shap.parquet", index=False)

for x in sorted(PBI.iterdir()):
    print(f"{x.name:24s} {x.stat().st_size / 1e6:6.1f} MB")
lq = fs[fs.quarter == fs.quarter.max()]
print(f"\nlatest quarter {lq.quarter.max():%Y-%m-%d}: {lq.flag.sum()} of {len(lq)} banks flagged "
      f"({(lq.in_breach == 1).sum()} more already in breach), "
      f"holding {lq.loc[lq.flag == 1, 'total_deposits'].sum() / lq.total_deposits.sum():.1%} of system deposits; "
      f"{(lq.mover == 'New flag').sum()} new this quarter")
