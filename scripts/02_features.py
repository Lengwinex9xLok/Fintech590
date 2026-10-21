"""Feature build: Phase 2 ratios + peer-relative, trend and missingness features, and the
forward-looking stress target. Features use quarter t and earlier; the target looks at t+1..t+4.

Output: data/phase3/features.parquet     bank x quarter, features + target
        data/phase3/fact_metric.parquet  long format (rssd_id, quarter, metric_key, value, is_reported)
        data/phase3/dim_metric.csv       metric lineage: schedule, MDRM codes, construction
"""
import numpy as np
import pandas as pd

from config import ASSET_TIERS, HORIZON_Q, OUT_DIR, RAW_FIELDS, STRESS, TIER_LABELS

p = pd.read_parquet(OUT_DIR / "panel_raw.parquet").sort_values(["rssd_id", "quarter"]).reset_index(drop=True)
qnum = p["quarter"].dt.quarter
annualize = 4 / qnum                                     # RI items are year to date


def div(a, b):
    return (a / b).where(b > 0)


f = p[["rssd_id", "quarter", "form_type", "total_assets"]].copy()
deposits = p["dep_domestic"].fillna(0) + p["dep_foreign"].fillna(0)
deposits = deposits.where(p["dep_domestic"].notna())
noncurrent = p["pd90"] + p["nonaccrual"]
cre = p[["cre_constr_1to4", "cre_constr_other", "cre_multifamily", "cre_nonowner"]].sum(axis=1, min_count=1)
unreal = (p["htm_amort"] - p["htm_fv"]).fillna(0) + (p["afs_amort"] - p["afs_fv"]).fillna(0)

# --- Level ratios (slide 37) -------------------------------------------------
f["tier1_leverage"]     = p["lev_ratio_rep"].fillna(100 * div(p["tier1_capital"], p["avg_assets_lev"]))  # reported %, RC-R
f["noncurrent_ratio"]   = div(noncurrent, p["total_loans"])
f["reserve_coverage"]   = div(p["acl_loans"], noncurrent)
f["cre_to_capital"]     = div(cre, p["total_rb_capital"].fillna(p["tier1_capital"]))   # CBLR proxy: Tier 1
f["uninsured_share"]    = div(p["uninsured_dep"], deposits)
f["brokered_share"]     = div(p["brokered_dep"], deposits)
f["unreal_loss_t1"]     = div(unreal, p["tier1_capital"])
f["nco_rate"]           = div((p["chargeoffs_ytd"] - p["recoveries_ytd"]) * annualize, p["total_loans"])
f["nim"]                = div(p["nii_ytd"] * annualize, p["total_assets"])
f["roa"]                = div(p["net_income_ytd"] * annualize, p["total_assets"])
f["loans_to_deposits"]  = div(p["total_loans"], deposits)
f["log_assets"]         = np.log10(p["total_assets"].where(p["total_assets"] > 0))

# --- Structural / missingness flags (missing is not zero: flag, don't impute) -
f["form_051"]           = (p["form_type"] == "051").astype(int)
f["form_031"]           = (p["form_type"] == "031").astype(int)
f["cblr_elector"]       = (p["cblr_optin"] == 1).astype(int)
f["miss_uninsured"]     = p["uninsured_dep"].isna().astype(int)
f["miss_brokered"]      = p["brokered_dep"].isna().astype(int)

LEVELS = ["tier1_leverage", "noncurrent_ratio", "reserve_coverage", "cre_to_capital", "uninsured_share",
          "brokered_share", "unreal_loss_t1", "nco_rate", "nim", "roa", "loans_to_deposits"]

# --- Within-bank trends (lag discipline: t and earlier) ----------------------
g = f.groupby("rssd_id", group_keys=False)
consecutive = g["quarter"].diff(4).dt.days.between(360, 370)       # only if the bank filed 4Q ago
for c in ["tier1_leverage", "noncurrent_ratio", "cre_to_capital", "unreal_loss_t1", "roa", "uninsured_share"]:
    f[f"{c}_chg4q"] = (f[c] - g[c].shift(4)).where(consecutive)
for name, s in {"assets": p["total_assets"], "loans": p["total_loans"], "deposits": deposits}.items():
    lag = s.groupby(p["rssd_id"]).shift(4)
    f[f"{name}_growth_yoy"] = (s / lag - 1).where(consecutive & (lag > 0))
f["rapid_growth"] = (f["assets_growth_yoy"] > 0.25).astype(int)

# --- Peer-relative within asset tier x quarter (winsorize, then z and pct rank)
f["asset_tier"] = pd.cut(f["total_assets"], ASSET_TIERS, labels=TIER_LABELS, right=False)
peer = f.groupby(["quarter", "asset_tier"], observed=True)
for c in LEVELS:
    lo, hi = peer[c].transform(lambda s: s.quantile(0.01)), peer[c].transform(lambda s: s.quantile(0.99))
    w = f[c].clip(lo, hi)
    f[f"{c}_pct"] = peer[c].rank(pct=True)
    f[f"{c}_z"] = (w - w.groupby([f["quarter"], f["asset_tier"]], observed=True).transform("mean")) / \
                  w.groupby([f["quarter"], f["asset_tier"]], observed=True).transform("std")

# --- Target: breach within the next 4 quarters, excluding banks already in breach at t
f["in_breach"] = ((f["tier1_leverage"] < STRESS["lev_ratio_lt"]) |
                  (f["noncurrent_ratio"] > STRESS["noncurrent_gt"]) |
                  (f["roa"] < STRESS["roa_lt"])).astype(int)
# Look up the bank's breach status at each of the next 4 calendar quarters (t+1..t+4), keyed on
# quarter end date, so a filing gap is never mistaken for the next quarter.
# Label rule: 1 if a breach is observed in any filed forward quarter; 0 only if all 4 forward
# quarters are filed and none breach; otherwise unlabeled (NaN). A bank that stops filing
# (failure, merger) or a quarter near the end of the panel without an observed breach is NOT a
# negative: its follow-up is incomplete.
status = f.set_index(["rssd_id", "quarter"])["in_breach"]
fwd = pd.concat(
    [pd.Series(status.reindex(pd.MultiIndex.from_arrays(
        [f["rssd_id"], f["quarter"] + pd.offsets.QuarterEnd(k)])).values, index=f.index)
     for k in range(1, HORIZON_Q + 1)], axis=1)
f["fwd_quarters_observed"] = fwd.notna().sum(axis=1)
f["target"] = np.select([fwd.eq(1).any(axis=1), f["fwd_quarters_observed"] == HORIZON_Q], [1.0, 0.0], np.nan)
f["exits_panel_4q"] = (f["fwd_quarters_observed"] < HORIZON_Q) & \
                      (f["quarter"] <= f["quarter"].max() - pd.offsets.QuarterEnd(HORIZON_Q))
f.loc[f["in_breach"] == 1, "target"] = np.nan                       # already in breach: exclude

f.to_parquet(OUT_DIR / "features.parquet", index=False)

# --- Long fact table + lineage for Power BI ---------------------------------
metric_cols = [c for c in f.columns if c not in ("rssd_id", "quarter", "form_type", "asset_tier", "target",
                                                   "in_breach", "exits_panel_4q", "fwd_quarters_observed")]
fact = f.melt(id_vars=["rssd_id", "quarter"], value_vars=metric_cols, var_name="metric_key", value_name="value")
fact["is_reported"] = fact["value"].notna().astype(int)
fact.to_parquet(OUT_DIR / "fact_metric.parquet", index=False)

LINEAGE = {
    "tier1_leverage":   ("RC-R", "RCFA/RCOA 7204", "Tier 1 leverage ratio as reported"),
    "noncurrent_ratio": ("RC-N, RC-C", "(1407 + 1403) / 2122", "90+ PD and nonaccrual / total loans"),
    "reserve_coverage": ("RC, RC-N", "3123 / (1407 + 1403)", "ACL on loans / noncurrent loans"),
    "cre_to_capital":   ("RC-C, RC-R", "(F158+F159+1460+F161) / 3792", "Non-owner-occ CRE / total RBC (Tier 1 for CBLR)"),
    "uninsured_share":  ("RC-O, RC", "RCON5597 / (RCON2200 + RCFN2200)", "Estimated uninsured / total deposits"),
    "brokered_share":   ("RC-E, RC", "RCON2365 / deposits", "Brokered / total deposits"),
    "unreal_loss_t1":   ("RC-B, RC-R", "((1754-1771)+(1772-1773)) / 8274", "Unrealized HTM+AFS losses / Tier 1"),
    "nco_rate":         ("RI-B, RC-C", "(RIAD4635 - RIAD4605) x 4/q / 2122", "Annualized net charge-offs / loans"),
    "nim":              ("RI, RC", "RIAD4074 x 4/q / 2170", "Annualized NII / total assets"),
    "roa":              ("RI, RC", "RIAD4340 x 4/q / 2170", "Annualized net income / total assets"),
    "loans_to_deposits":("RC-C, RC", "2122 / deposits", "Loans / deposits"),
    "log_assets":       ("RC", "log10(2170)", "Size"),
}
rows = []
for m in metric_cols:
    base = next((b for b in LINEAGE if m == b or m.startswith(b + "_")), None)
    sched, mdrm, desc = LINEAGE.get(base, ("derived", "", m))
    suffix = m[len(base):] if base else ""
    kind = {"_pct": "pct rank in tier x quarter", "_z": "winsorized z in tier x quarter",
            "_chg4q": "4 quarter change"}.get(suffix, "level" if base else "flag / growth")
    rows.append({"metric_key": m, "schedule": sched, "mdrm": mdrm, "description": desc, "transform": kind})
pd.DataFrame(rows).to_csv(OUT_DIR / "dim_metric.csv", index=False)

lab = f["target"].dropna()
print(f"features: {len(f):,} rows, {len(metric_cols)} candidate features")
print(f"labeled bank-quarters: {len(lab):,}, base rate {lab.mean():.2%}")
print(f"currently in breach (excluded from training): {f['in_breach'].mean():.2%}")
