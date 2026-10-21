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
| LLM validation log | Local P1-P16 finalized; selected checks completed and unreviewed items explicitly identified | Loki |
| Stress threshold | Current research thresholds retained by team decision; see decision record | Loki + Abhi |
| PBIX dashboard + SHAP panel | Final v0.2 built and tested; see `PBIX_Usage.txt`; Git publication authorized by Loki | Loki |
| PDF report | Local final `Phase3_Report.pdf`, three pages; evaluated metrics checked by Loki | Loki |
| Governance memo | Local final `Governance_Memo.pdf`, three pages; read and conclusions accepted by Loki | Loki |

The final file list and course-upload steps are in `Submission_Guide.txt`. Old drafts are preserved locally and excluded from this release. Loki authorized Git publication; the commit history records the release. No course upload is claimed. Selected human checks do not certify full independent validation; `Human_Review_Record.json` and the log retain that distinction.

## Step 0: setup (10 minutes)

```
git fetch origin
git checkout abhi/phase3-ews-pipeline
pip install -r scripts/requirements.txt
```

The ingested panel is in git (`data/phase3/panel_raw.parquet` and `dim_bank.parquet`), so you can rerun `02_features.py`, `03_model.py` and `04_export_pbi.py` straight away; skip `01_ingest.py`. The raw CDR files (341 MB) are not in git and you only need them to rerun the ingest: run `python scripts/00_download_cdr.py` (on the Duke network it may fail on a certificate error; `pip install truststore` and retry) or ask Abhi for a copy.

## Step 1: stress threshold decision

Abhi and Loki agreed on 20 October 2026 to retain the existing settings for Phase 3. `Team_Decision_Record.txt` records the stress target, deduplicated 12-feature model, average 50-review budget and override policy. This closes the project-choice items, not independent human verification or approval for live use. The historical instructions below explain the current configuration and what a later change would require.

The model predicts "does this bank breach the stress threshold within the next 4 quarters". The threshold is our call and the memo has to defend it (slide 39). Current placeholder in `scripts/config.py`:

```python
STRESS = {
    "lev_ratio_lt": 7.0,      # Tier 1 leverage below 7%
    "noncurrent_gt": 0.03,    # noncurrent loans above 3% of total loans
    "roa_lt": -0.005,         # annualized ROA below -0.5%
}
```

About 6.6% of labeled bank quarters breach. Noncurrent loans drive most of it (3 to 7% of banks a year), ROA 2 to 3%, leverage under 2%. If you change it, rerun and every number in this file changes:

```
python scripts/02_features.py
python scripts/03_model.py
python scripts/04_export_pbi.py
```

`04_export_pbi.py` prints the headline numbers (flag threshold, test precision, banks flagged this quarter) at the end.

## Step 2: build the PBIX

Updated local file: `Fintech590_Phase3_UniverseConsole_v02.pbix` in the repo root. The older file without `_v02` is preserved, not the current deliverable.

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

Closeout status: the log now records Loki's completed selected checks and explicitly marks items not individually checked. The suggestions below remain available for additional review; they are not claims that every check was performed. Abhi read the final report and memo on 21 October 2026.

For further spot checks, open `Phase 3/LLM_Validation_Log.md` and record what you actually inspect. Examples:
* P2: open `data/phase3/reconciliation.csv`, confirm `diff` is 0 for every quarter.
* P3: pick any bank on the FFIEC CDR site (cdr.ffiec.gov, Institution Reports), compare its Tier 1 leverage for 2026 Q2 with `fact_metric`.
* P10: in the PBIX, confirm no bank with status "Already in breach" appears on the watchlist.
* P11: filter the PBIX to Silicon Valley Bank (RSSD 802866) at 2022 Q4 and confirm it is not flagged.

If you use an AI tool for the memo or report, add rows for that too (same format as the Defense 1 log).

## Step 4: governance memo (2 to 3 pages)

Structure: recommendation first, then failure modes, then override policy, then monitoring.

**Recommendation (suggested, edit as you see fit):** use the model as a credit deterioration triage tool for community banks, reviewed quarterly, with a mandatory human liquidity overlay. Do not use it as a system wide failure predictor: it missed all three 2023 failures.

**Failure mode inventory** (need at least 3; each has evidence):

1. **It does not catch liquidity runs.** Backtest at 2022 Q4: SVB ranked 2,208th, Signature (NY) 3,783rd, First Republic 2,832nd out of about 4,700. None flagged. SVB had 86% uninsured deposits and unrealized losses above 100% of Tier 1. The target measures credit and earnings, so the model learned credit and earnings.
2. **Failed banks drop out of the labels.** A bank that fails stops filing, so it has no next 4 quarters and gets no label. The event we care about most is invisible to training (survivorship, slide 32).
3. **Bank size is the second most important feature.** It may be picking up form type and reporting thresholds (051 filers; uninsured deposits only reported at $1B+) rather than risk (slide 43). 51 of the 61 flagged banks are under $1B.
4. **Scores are a ranking, not probabilities.** Training reweighted the rare class (`scale_pos_weight`), so a score of 0.90 does not mean a 90% chance.
5. **Drift.** The 0.910 cutoff flagged about 50 banks a quarter in 2023 to 2024 but 61 in 2026 Q2, and banks already in breach rose from about 6% to 8.5%. The threshold needs a recheck when each Call Report lands.
6. **The threshold is a judgment call.** Our stress definition is not a supervisory standard (slide 39). Change it and the model changes.
7. **Structural missingness.** Uninsured deposits are blank by rule under $1B; CBLR electors do not report risk based capital, so CRE to capital uses Tier 1 as a proxy; past due and nonaccrual totals do not exist in the bulk files before 2017, so training starts in 2017.

**Override policy (draft):**
* A named reviewer who did not build the model can override (SR 26-2 independence, slide 25).
* **Add** a bank below the threshold when there is evidence the model cannot see (liquidity, news, exam findings). This is the SVB case.
* **Remove** a flagged bank only with a written reason naming the SHAP driver being overridden.
* Log every override: RSSD ID, quarter, direction, reason, reviewer. Review the log quarterly; overrides clustering on one feature or bank type means a model problem.
* If overrides exceed about 20% of the watchlist in a quarter, escalate for revalidation.

## Step 5: PDF report (Backwards First)

Page 1 is the full story on its own: the recommendation, 61 banks flagged in 2026 Q2, 41% precision vs a 6.4% base rate, and the liquidity blind spot. The pages after it are evidence: data and reconciliation, target definition, out of time results, SHAP summary, watchlist, failure modes. Screenshots come from the PBIX.

## Numbers (placeholder threshold, model ews-xgb-0.2)

**Data**
* 46 quarters of FFIEC CDR Call Report bulk files, 2015 Q1 to 2026 Q2. 239,553 bank quarters, 6,581 banks.
* Every quarter reconciles to the CDR Panel of Reporters by form type. 2026 Q2: 80 (031) + 934 (041) + 3,283 (051) = 4,297.

**Target label fix (ews-xgb-0.2, found by Loki)**
* Version 0.1 labeled a bank quarter as "no breach" even when some of the next 4 quarters were never filed (the bank failed, merged, or the quarter was near the end of the data). That counted incomplete follow up as a negative.
* Now: 1 if a breach is observed in any filed forward quarter; 0 only if all 4 forward quarters are filed with no breach; otherwise unlabeled. Forward quarters are matched by calendar date, so a filing gap is never mistaken for the next quarter.
* 16,450 bank quarters moved from 0 to unlabeled. First Republic at 2022 Q4 is one example; SVB and Signature at that quarter were already unlabeled in v0.1. No original positive labels changed. Labeled bank quarters: 200,238.

**Model** (train 2017 to 2021, gap 2022, test 2023 to 2024)
* Train 94,339 bank quarters (base 6.6%), test 33,911 (base 6.4%).
* Test base rate 6.4%. Average precision 0.208 with the final 12 features (0.227 with all 49). After the label fix the naive top 12 scores 0.221. The team retains deduped 12 for broader driver coverage while accepting lower AP; no superiority claim is made.
* Flag threshold 0.910, sized so the committee reviews about 50 banks a quarter. Test precision 41% (6.4x the base rate), recall 8%.
* 12 features kept by mean |SHAP|: noncurrent loans, bank size, Tier 1 leverage, ROA 4Q change, ROA percentile in size tier, unrealized losses 4Q change, CRE to capital, unrealized losses to Tier 1, brokered deposit share, leverage 4Q change, net interest margin, loans to deposits.

**2026 Q2**
* 61 banks flagged (not yet in breach), 42 new this quarter, holding 10.4% of system deposits. Almost all of that is one bank: Bank of America NA (rank 54, score 0.914), flagged mainly because its Tier 1 leverage (7.11%) sits just above the placeholder 7% line. Good example for the memo of how much the threshold choice drives the output.
* 367 more banks already in breach, listed separately.

## Files

* `scripts/00_download_cdr.py` to `04_export_pbi.py`: rerun in order to rebuild everything.
* `data/phase3/reconciliation.csv`: Gate 1 evidence.
* `data/phase3/feature_log.csv`: features before and after pruning, with out of time results.
* `data/phase3/shap_global_full.png` / `.csv`: global SHAP.
* `data/phase3/model_card_inputs.json`, `ews-xgb-0.2.json`: model settings and the model itself.
* `data/phase3/pbi/`: the tables the PBIX imports, plus `threshold.json`.
