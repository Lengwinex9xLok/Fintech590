# Phase 3 Governance Audit: Handoff to Loki

Abhi built the data pipeline, the model and the Power BI tables (this branch). Everything below is what is left for the submission, in the order to do it.

## What we submit

1. Power BI bank health dashboard + SHAP explainability panel (PBIX, committed to GitHub)
2. PDF report (Backwards First: page 1 is the whole story)
3. Governance memo, 2 to 3 pages: recommendation first, failure mode inventory (at least 3), override policy
4. LLM validation log committed to GitHub

## Status

| Deliverable | Status | Owner |
|---|---|---|
| Pipeline, model, SHAP, Power BI tables | Done (this branch) | Abhi |
| LLM validation log | Draft done in `Phase 3/LLM_Validation_Log.md` (rows P1 to P11). Needs your spot check column | Loki |
| Stress threshold | **Placeholder. Decide first** | Loki + Abhi |
| PBIX dashboard + SHAP panel | Not started. Tables are ready | Loki |
| PDF report | Not started | Loki |
| Governance memo | Not started | Loki |

## Step 0: setup (10 minutes)

```
git fetch origin
git checkout abhi/phase3-ews-pipeline
pip install -r scripts/requirements.txt
```

You only need the raw data if you change the stress threshold. It is not in git (341 MB). Either run `python scripts/00_download_cdr.py` (downloads all 46 quarters into `data/cdr_bulk/`; on the Duke network it may fail on a certificate error, then run `pip install truststore` and retry) or ask Abhi for a copy of `data/cdr_bulk/`.

## Step 1: decide the stress threshold

The model predicts "does this bank breach the stress threshold within the next 4 quarters". The threshold is our call and the memo has to defend it (slide 39). Current placeholder in `scripts/config.py`:

```python
STRESS = {
    "lev_ratio_lt": 7.0,      # Tier 1 leverage below 7%
    "noncurrent_gt": 0.03,    # noncurrent loans above 3% of total loans
    "roa_lt": -0.005,         # annualized ROA below -0.5%
}
```

About 6% of bank quarters breach. Noncurrent loans drive most of it (3 to 7% of banks a year), ROA 2 to 3%, leverage under 2%. If you change it, rerun and every number in this file changes:

```
python scripts/01_ingest.py      # only needed once, about 20 seconds
python scripts/02_features.py
python scripts/03_model.py
python scripts/04_export_pbi.py
```

`04_export_pbi.py` prints the headline numbers (flag threshold, test precision, banks flagged this quarter) at the end.

## Step 2: build the PBIX

Save it as `Fintech590_Phase3_UniverseConsole.pbix` in the repo root.

**Load** (Get Data → Parquet / Text): everything in `data/phase3/pbi/`.

| Table | Grain | Key columns |
|---|---|---|
| `dim_bank` | one row per RSSD ID | `rssd_id`, `name`, `bank_label`, `state`, `form_type`, `asset_tier`, `cblr_elector` |
| `dim_quarter` | one row per quarter | `quarter`, `quarter_label`, `rate_regime`, `split` (Train / Gap / Test / Score live) |
| `dim_metric` | one row per feature | `metric_key`, `friendly_name`, `schedule`, `mdrm`, `lineage`, `kept`, `shap_rank` |
| `fact_score` | bank x quarter | `p_stress_4q`, `flag`, `status`, `risk_rank`, `mover`, `total_deposits`, `outcome`, `threshold`, `model_version` |
| `fact_metric` | bank x quarter x feature | `value`, `tier_median`, `is_reported` |
| `fact_shap` | bank x quarter x feature (last 8 quarters) | `shap_logodds`, `base_value_logodds`, `value` |

**Relationships** (single direction, dimension to fact): `dim_bank[rssd_id]` and `dim_quarter[quarter]` to all three facts; `dim_metric[metric_key]` to `fact_metric` and `fact_shap`.

**Set every ratio column to Don't summarize** (slide 47: summing ratios across banks is meaningless).

**Starter measures**

```DAX
Latest Quarter = MAX ( fact_score[quarter] )

Banks Flagged = CALCULATE ( COUNTROWS ( fact_score ), fact_score[flag] = 1 )

Banks Already In Breach = CALCULATE ( COUNTROWS ( fact_score ), fact_score[status] = "Already in breach" )

New Flags = CALCULATE ( COUNTROWS ( fact_score ), fact_score[mover] = "New flag" )

Flagged Deposit Share =
DIVIDE (
    CALCULATE ( SUM ( fact_score[total_deposits] ), fact_score[flag] = 1 ),
    CALCULATE ( SUM ( fact_score[total_deposits] ), REMOVEFILTERS ( fact_score[flag], fact_score[status] ) )
)

Conclusion Title =
FORMAT ( [Banks Flagged], "#,0" ) & " banks flagged for review, holding "
    & FORMAT ( [Flagged Deposit Share], "0.0%" ) & " of system deposits; "
    & FORMAT ( [New Flags], "#,0" ) & " new this quarter"

Risk Score = MAX ( fact_score[p_stress_4q] )
Flag Threshold = MAX ( fact_score[threshold] )

SHAP Contribution = SUM ( fact_shap[shap_logodds] )
SHAP Base Value = MAX ( fact_shap[base_value_logodds] )

Metric Value = MAX ( fact_metric[value] )
Peer Median = MAX ( fact_metric[tier_median] )
```

**Pages** (slides 45 to 47)

1. **Universe screen (overview):** `Conclusion Title` as the page title card; cards for Banks Flagged, Already In Breach, New Flags; histogram of `p_stress_4q` for all banks with a constant line at `Flag Threshold`; slicers for asset tier, state, form type, quarter (default to the latest quarter).
2. **Watchlist (filter):** table of flagged banks only, sorted by `risk_rank`, top 50: bank, state, asset tier, score, mover, top SHAP driver. A second small table: banks that moved in or out this quarter.
3. **Bank drill through (details on demand):** drill through on `dim_bank[rssd_id]`. SHAP waterfall (Waterfall chart: category `dim_metric[friendly_name]`, value `SHAP Contribution`, sorted by absolute size, with the base value stated in a text box) plus line charts of each kept feature vs `Peer Median` over time. Tooltip with `dim_metric[lineage]` so every number traces to schedule, MDRM, RSSD ID and quarter.
4. **Model governance:** global SHAP chart (image `data/phase3/shap_global_full.png` or a bar chart from `shap_global_full.csv`), out of time results from `feature_log.csv`, threshold rule from `threshold.json`, the SVB / Signature / First Republic backtest.

**Power BI traps:** raise any scatter chart's point limit (default 3,500 drops about 800 banks silently); never show the full 4,297 row table, cut to top k; label scores as "risk score", not probability (see failure mode 4).

## Step 3: spot check the LLM validation log

Open `Phase 3/LLM_Validation_Log.md`. For each row P1 to P11, check one thing yourself and write what you checked in the "Human spot check" column. Quick ones:
* P2: open `data/phase3/reconciliation.csv`, confirm `diff` is 0 for every quarter.
* P3: pick any bank on the FFIEC CDR site (cdr.ffiec.gov, Institution Reports), compare its Tier 1 leverage for 2026 Q2 with `fact_metric`.
* P10: in the PBIX, confirm no bank with status "Already in breach" appears on the watchlist.
* P11: filter the PBIX to Silicon Valley Bank (RSSD 802866) at 2022 Q4 and confirm it is not flagged.

If you use an AI tool for the memo or report, add rows for that too (same format as the Defense 1 log).

## Step 4: governance memo (2 to 3 pages)

Structure: recommendation first, then failure modes, then override policy, then monitoring.

**Recommendation (suggested, edit as you see fit):** use the model as a credit deterioration triage tool for community banks, reviewed quarterly, with a mandatory human liquidity overlay. Do not use it as a system wide failure predictor: it missed all three 2023 failures.

**Failure mode inventory** (need at least 3; each has evidence):

1. **It does not catch liquidity runs.** Backtest at 2022 Q4: SVB ranked 2,472nd, Signature (NY) about 3,900th, First Republic 3,301st out of about 4,700. None flagged. SVB had 86% uninsured deposits and unrealized losses above 100% of Tier 1. The target measures credit and earnings, so the model learned credit and earnings.
2. **Failed banks drop out of the labels.** A bank that fails stops filing, so it has no next 4 quarters and gets no label. The event we care about most is invisible to training (survivorship, slide 32).
3. **Bank size is the second most important feature.** It may be picking up form type and reporting thresholds (051 filers; uninsured deposits only reported at $1B+) rather than risk (slide 43). 53 of the 61 flagged banks are under $1B.
4. **Scores are a ranking, not probabilities.** Training reweighted the rare class (`scale_pos_weight`), so a score of 0.90 does not mean a 90% chance.
5. **Drift.** The 0.904 cutoff flagged about 50 banks a quarter in 2023 to 2024 but 61 in 2026 Q2, and banks already in breach rose from about 6% to 8.5%. The threshold needs a recheck when each Call Report lands.
6. **The threshold is a judgment call.** Our stress definition is not a supervisory standard (slide 39). Change it and the model changes.
7. **Structural missingness.** Uninsured deposits are blank by rule under $1B; CBLR electors do not report risk based capital, so CRE to capital uses Tier 1 as a proxy; past due and nonaccrual totals do not exist in the bulk files before 2017, so training starts in 2017.

**Override policy (draft):**
* A named reviewer who did not build the model can override (SR 26-2 independence, slide 25).
* **Add** a bank below the threshold when there is evidence the model cannot see (liquidity, news, exam findings). This is the SVB case.
* **Remove** a flagged bank only with a written reason naming the SHAP driver being overridden.
* Log every override: RSSD ID, quarter, direction, reason, reviewer. Review the log quarterly; overrides clustering on one feature or bank type means a model problem.
* If overrides exceed about 20% of the watchlist in a quarter, escalate for revalidation.

## Step 5: PDF report (Backwards First)

Page 1 is the full story on its own: the recommendation, 61 banks flagged in 2026 Q2, 42% precision vs a 6.3% base rate, and the liquidity blind spot. The pages after it are evidence: data and reconciliation, target definition, out of time results, SHAP summary, watchlist, failure modes. Screenshots come from the PBIX.

## Numbers (placeholder threshold, model ews-xgb-0.1)

**Data**
* 46 quarters of FFIEC CDR Call Report bulk files, 2015 Q1 to 2026 Q2. 239,553 bank quarters, 6,581 banks.
* Every quarter reconciles to the CDR Panel of Reporters by form type. 2026 Q2: 80 (031) + 934 (041) + 3,283 (051) = 4,297.

**Model** (train 2017 to 2021, gap 2022, test 2023 to 2024)
* Test base rate 6.3%. PR AUC 0.209 with the final 12 features (0.220 with all 49).
* Flag threshold 0.904, sized so the committee reviews about 50 banks a quarter. Test precision 42% (6.7x the base rate), recall 8%.
* 12 features kept by mean |SHAP|: noncurrent loans, bank size, Tier 1 leverage, ROA 4Q change, ROA percentile in size tier, unrealized losses 4Q change, CRE to capital, unrealized losses to Tier 1, brokered deposit share, leverage 4Q change, net interest margin, loans to deposits.

**2026 Q2**
* 61 banks flagged (not yet in breach), 39 new this quarter, holding 0.4% of system deposits.
* 367 more banks already in breach, listed separately.

## Files

* `scripts/00_download_cdr.py` to `04_export_pbi.py`: rerun in order to rebuild everything.
* `data/phase3/reconciliation.csv`: Gate 1 evidence.
* `data/phase3/feature_log.csv`: features before and after pruning, with out of time results.
* `data/phase3/shap_global_full.png` / `.csv`: global SHAP.
* `data/phase3/model_card_inputs.json`, `ews-xgb-0.1.json`: model settings and the model itself.
* `data/phase3/pbi/`: the tables the PBIX imports, plus `threshold.json`.
