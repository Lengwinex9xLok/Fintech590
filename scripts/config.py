"""Shared config for the Phase 3 pipeline: paths, MDRM lineage, target definition."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULK_DIR = ROOT / "data" / "cdr_bulk"          # one CDR "Call Bulk All Schedules" ZIP per quarter
OUT_DIR = ROOT / "data" / "phase3"             # parquet outputs that Power BI imports
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Raw fields pulled from the bulk files.
# key -> (schedule, [MDRM codes in coalesce priority order], description)
# Consolidated (RCFD / RCFA) first, domestic (RCON / RCOA) second: 031 filers
# populate RCFD, 041/051 filers populate RCON. Coalesce before comparing banks.
# ---------------------------------------------------------------------------
RAW_FIELDS = {
    "total_assets":        ("RC",   ["RCFD2170", "RCON2170"], "Total assets"),
    "total_loans":         ("RC-C", ["RCFD2122", "RCON2122"], "Total loans and leases, gross"),
    "acl_loans":           ("RC",   ["RCFD3123", "RCON3123"], "Allowance for loan and lease losses / ACL on loans"),
    "dep_domestic":        ("RC",   ["RCON2200"],             "Deposits in domestic offices"),
    "dep_foreign":         ("RC",   ["RCFN2200"],             "Deposits in foreign offices (031 only)"),
    "tier1_capital":       ("RC-R", ["RCFA8274", "RCOA8274"], "Tier 1 capital"),
    "total_rb_capital":    ("RC-R", ["RCFA3792", "RCOA3792"], "Total risk-based capital"),
    "lev_ratio_rep":       ("RC-R", ["RCFA7204", "RCOA7204"], "Tier 1 leverage ratio (reported, %)"),
    "avg_assets_lev":      ("RC-R", ["RCFAA224", "RCOAA224"], "Average total assets for the leverage ratio"),
    "cblr_optin":          ("RC-R", ["RCOALE74"],             "CBLR framework election (1 = opted in)"),
    "t1_rb_ratio_rep":     ("RC-R", ["RCFA7206", "RCOA7206"], "Tier 1 risk-based ratio (reported, %); blank for CBLR electors"),
    "pd90":                ("RC-N", ["RCFD1407", "RCON1407"], "Loans 90+ days past due and still accruing"),
    "nonaccrual":          ("RC-N", ["RCFD1403", "RCON1403"], "Nonaccrual loans"),
    "uninsured_dep":       ("RC-O", ["RCON5597"],             "Estimated uninsured deposits ($1B+ filers only)"),
    "brokered_dep":        ("RC-E", ["RCON2365"],             "Total brokered deposits"),
    "cre_constr_1to4":     ("RC-C", ["RCONF158"],             "1-4 family residential construction loans"),
    "cre_constr_other":    ("RC-C", ["RCONF159"],             "Other construction and land development loans"),
    "cre_multifamily":     ("RC-C", ["RCON1460"],             "Multifamily residential RE loans"),
    "cre_nonowner":        ("RC-C", ["RCONF161"],             "Nonfarm nonresidential, non-owner-occupied"),
    "htm_amort":           ("RC-B", ["RCFD1754", "RCON1754"], "HTM securities, amortized cost"),
    "htm_fv":              ("RC-B", ["RCFD1771", "RCON1771"], "HTM securities, fair value"),
    "afs_amort":           ("RC-B", ["RCFD1772", "RCON1772"], "AFS securities, amortized cost"),
    "afs_fv":              ("RC-B", ["RCFD1773", "RCON1773"], "AFS securities, fair value"),
    "nii_ytd":             ("RI",   ["RIAD4074"],             "Net interest income, YTD"),
    "net_income_ytd":      ("RI",   ["RIAD4340"],             "Net income, YTD"),
    "chargeoffs_ytd":      ("RI-B", ["RIAD4635"],             "Total charge-offs, YTD"),
    "recoveries_ytd":      ("RI-B", ["RIAD4605"],             "Total recoveries, YTD"),
}

# ---------------------------------------------------------------------------
# Early-warning target: does the bank breach a stress threshold within the
# next 4 quarters? This is YOUR claim to defend (slide 39). Defaults start
# from the Phase 2 bands; tune them and record why in the model card.
# ---------------------------------------------------------------------------
STRESS = {
    "lev_ratio_lt": 7.0,          # Tier 1 leverage below 7% (well-capitalized line is 5%; CBLR minimum is 9%)
    "noncurrent_gt": 0.03,        # noncurrent loans above 3% of total loans
    "roa_lt": -0.005,             # annualized ROA below -0.5%
}
HORIZON_Q = 4

# Out-of-time split (slide 41). Training starts 2017Q1: before the 2017 RC-N revision the bulk files
# carry no total 90+ PD (1407) / nonaccrual (1403) columns, so noncurrent loans and the target are
# undefined for 2015-2016. Those quarters stay in the panel (and feed 4Q trend lags) but are not trained on.
TRAIN_START = "2017-03-31"
TRAIN_END = "2021-12-31"
GAP_END = "2022-12-31"
TEST_END = "2024-12-31"

ASSET_TIERS = [0, 1e6, 10e6, 100e6, float("inf")]   # $ thousands: <1B, 1-10B, 10-100B, 100B+
TIER_LABELS = ["<$1B", "$1-10B", "$10-100B", "$100B+"]

MODEL_VERSION = "ews-xgb-0.2"
