# FFIEC Balance Sheet Scorecard

FINTECH 590, Lecture 5 Team Assignment

## Conclusion

**JPMorgan Chase has the thinnest 12 month liquidity cushion in the peer group (29.7% of total assets, versus 36.3% to 39.5% for the other four banks), despite having the strongest Tier 1 capital ratio (15.1%).** The exposure is a funding and repricing issue, not a capital issue, so the recommended committee action is a review of JPMorgan's short term liability mix and deposit repricing assumptions rather than any capital action.

"Most exposed" is a relative ranking among these five banks. It does not imply JPMorgan Chase is distressed or below any regulatory minimum; all five banks are well above the 8% Tier 1 threshold.

## Bank Peer Group

| Holding company (FR Y-9C filer) | RSSD ID | Lead bank (Call Report filer) | Bank RSSD ID |
| --- | ---: | --- | ---: |
| Bank of America Corporation | 1073757 | Bank of America, National Association | 480228 |
| Citigroup Inc. | 1951350 | Citibank, N.A. | 476810 |
| The Goldman Sachs Group, Inc. | 2380443 | Goldman Sachs Bank USA | 2182786 |
| JPMorgan Chase & Co. | 1039502 | JPMorgan Chase Bank, National Association | 852218 |
| Wells Fargo & Company | 1120754 | Wells Fargo Bank, National Association | 451965 |

All RSSD IDs were verified on the FFIEC National Information Center (ffiec.gov/npw). Holding company and bank level data are kept in separate tables and are never mixed under the same name.

## Data Sources

Both sources refresh inside Power BI (Home > Refresh). Neither uses a static export.

### 1. Holding company metrics: FFIEC NIC, FR Y-9C (query `Metrics`)

- File: `data/BHCF20260630.ZIP`, the official FR Y-9C bulk file for the June 30, 2026 quarter, downloaded from `https://www.ffiec.gov/npw/FinancialReport/ReturnBHCFZipFiles?zipfilename=BHCF20260630.ZIP`.
- Power Query unzips the file, filters to the five RSSD IDs above and pulls the MDRM fields listed below. Values are in thousands of dollars, as reported.
- To load a new quarter: download that quarter's `BHCF<yyyymmdd>.ZIP` into `data/`, change `ReportingPeriod` at the top of the `Metrics` query, then Refresh.
- Why a local copy: www.ffiec.gov drops connections from the Power BI web connector, so the official ZIP is kept in the repo as the source of record.

### 2. Authenticated FFIEC CDR API: Call Report RC-R (query `CDR_Bank_RCR`)

- Endpoint: FFIEC CDR Public Data Distribution REST API (`https://ffieccdr.azure-api.us/public/RetrieveFacsimile`), Call Report series, SDF format, reporting period 06/30/2026.
- Pulls Schedule RC-R (Tier 1 capital RCFA/RCOA 8274, risk weighted assets A223, reported ratios 7206 and 7204) for each holding company's lead bank. The results are shown on the Bank Detail page as a bank level cross check, clearly labeled.
- Credentials are **not** in this repo or the PBIX. The query reads a local file one level above the repo, `..\cdr_credentials.txt` (line 1 = CDR user ID, line 2 = 90 day bearer token from the CDR account page). `.gitignore` also blocks any `cdr_credentials*.txt`. To refresh this query on your own machine, create that file with your own CDR credentials; without it, the PBIX still opens and shows the last saved data.

## Required Metrics (FR Y-9C MDRM fields)

| Metric | Calculation | FR Y-9C fields |
| --- | --- | --- |
| Tier 1 capital ratio | Tier 1 capital / risk weighted assets | BHCA8274 / BHCAA223 (HC-R) |
| Leverage ratio | Tier 1 capital / average total assets for leverage | BHCA8274 / BHCAA224 (HC-R) |
| Loan to deposit ratio | Total loans / total deposits | BHCK2122 (HC-C) / (BHDM6631 + BHDM6636 + BHFN6631 + BHFN6636) (HC) |
| NPL ratio | (Loans 90+ days past due and still accruing + nonaccrual) / total loans | (BHCK1407 + BHCK1403) (HC-N) / BHCK2122 |
| 12 month cumulative liquidity gap | (Rate sensitive assets - rate sensitive liabilities, 1 year) / total assets | (BHCK3197 - (BHCK3296 + BHCK3298 + BHCK3408 + BHCK3409)) (HC-H) / BHCK2170 (HC) |

All five metrics are DAX measures computed from the raw fields, so every number traces to a schedule, an MDRM field and an RSSD ID.

Note on the liquidity gap: it is a contractual repricing gap from Schedule HC-H. Non maturity deposits (savings and checking) are not counted as repricing within a year, which is why every bank shows a large positive gap. JPMorgan ranks last because its liabilities repricing within a year are much larger (16.4% of assets versus 8.8% to 11.6% for peers).

## Results (Q2 2026)

| Bank | Tier 1 | Leverage | Loan to deposit | NPL | 12M liquidity gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| JPMorgan Chase | 15.1% | 6.6% | 59.9% | 0.8% | **29.7%** |
| Wells Fargo | 11.4% | 6.9% | 68.9% | 1.0% | 36.3% |
| Bank of America | 12.6% | 6.6% | 62.7% | 0.6% | 37.1% |
| Goldman Sachs | 14.5% | 5.4% | 66.3% | 1.4% | 37.3% |
| Citigroup | 14.7% | 6.2% | 54.9% | 0.7% | 39.5% |

## Power BI Report (`Fintech590_Lecture5_Scorecard.pbix`)

**Scorecard page**
- Action title (DAX measure `Action Title`) naming the most exposed bank; it updates automatically on refresh.
- Conclusion card, top left: most exposed bank and its 12 month liquidity gap.
- Ranked bar chart of the 12 month liquidity gap, most exposed first. The red highlight on the most exposed bank is driven by the DAX measure `Gap_Bar_Color`.
- Tier 1 capital ratio card for all five banks. Font color comes from the DAX measure `Tier1_Ratio_Color` (Field value conditional formatting, not a manual rule): green at 10% or above, amber 8% to 10%, red below 8%.
- Exposure note text box.

**Bank Detail page (drill through)**
- Right click any bank on the Scorecard bar chart > Drill through > Bank Detail.
- Supporting metrics (leverage, loan to deposit, NPL) with RSSD ID and source file for each bank.
- Data quality checks: Row Count = 5, Distinct RSSD = 5, Name Mismatches = 0 (the FR Y-9C legal name is matched against the NIC lookup by RSSD ID).
- Authenticated CDR panel: bank level Tier 1 ratios from the Call Report RC-R for each lead bank.

```
Tier1_Ratio_Color =
SWITCH ( TRUE (),
    [Tier 1 Ratio] >= 0.10, "#2E7D32",   -- green
    [Tier 1 Ratio] >= 0.08, "#F9A825",   -- amber
    "#C62828" )                          -- red
```

## Repository Contents

```text
Fintech590/
|-- Fintech590_Lecture5_Scorecard.pbix   Power BI scorecard (Scorecard + Bank Detail pages)
|-- Exposure_note.txt                    3 sentence exposure note
|-- data/BHCF20260630.ZIP                Official FFIEC NIC FR Y-9C bulk file, Q2 2026
|-- ffiec_metrics_2026Q2.xlsx            Original metrics workbook (reference only; no longer used by the PBIX)
|-- Book1.xlsx                           Same workbook, original upload (reference only)
|-- .gitignore                           Blocks credentials and the unzipped data file
`-- README.md
```

## How to Review

1. Clone or pull this repository and open `Fintech590_Lecture5_Scorecard.pbix` in Power BI Desktop. All visuals render from the saved data; no refresh is needed.
2. Check the Scorecard page: title, conclusion card, liquidity ranking, Tier 1 cards and exposure note.
3. Right click the JPMorgan Chase bar > Drill through > Bank Detail to see the supporting metrics and data checks.
4. Optional: to refresh on your machine, update the file path in the `Metrics` query (`DataFolder`) and create your own `cdr_credentials.txt` as described above.

## Team Responsibilities

| Responsibility | Owner |
| --- | --- |
| FFIEC data collection, RSSD verification, metric calculations and exposure note draft | Ziye Luo |
| Power BI model, FFIEC data connections, DAX conditional formatting, dashboard design and PBIX delivery | Abhinav Saraf |
| Final formula, ranking, visual and submission review | Both team members |

## Submission Checklist

- [x] All five holding companies are included, matched by RSSD ID.
- [x] The June 30, 2026 reporting quarter is used consistently.
- [x] All five required metrics are visible in the report or drill through page.
- [x] Tier 1 capital colors are driven by a DAX formula.
- [x] The liquidity gap ranking places the most exposed bank first.
- [x] The action title names the most exposed bank and states the conclusion.
- [x] The exposure note refers to at least two required metrics and states a recommended action.
- [x] Authenticated FFIEC CDR API connection working (Call Report RC-R pulled for each lead bank).
- [x] The PBIX opens with all panels rendered without manual refresh.
- [x] No API keys, passwords or credentials are committed.
- [ ] Teammate review of this version.
