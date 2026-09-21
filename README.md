# FFIEC Balance Sheet Scorecard

FINTECH 590 - Lecture 5 Team Assignment

## Project Overview

This project compares five U.S. bank holding companies using FFIEC Consolidated Financial Statements for Holding Companies (FR Y-9C) data. The analysis uses the most recent available reporting quarter, June 30, 2026, and presents the results in a one-page Power BI balance sheet scorecard.

The scorecard focuses on relative liquidity vulnerability while also reporting capital adequacy, leverage, lending, deposits, and credit quality metrics.

## Bank Peer Group

| Bank Holding Company | RSSD ID |
| --- | ---: |
| Bank of America Corporation | 1073757 |
| Citigroup Inc. | 1951350 |
| The Goldman Sachs Group, Inc. | 2380443 |
| JPMorgan Chase & Co. | 1039502 |
| Wells Fargo & Company | 1120754 |

The RSSD IDs were verified through the FFIEC National Information Center. Holding-company data were used consistently to avoid mixing parent companies with bank subsidiaries.

## Data Source and Reporting Period

- Source: FFIEC Central Data Repository bulk-download service
- Report: FR Y-9C
- Reporting quarter: June 30, 2026
- Relevant schedules: RC, RC-C, RC-N, and RC-R
- Unit treatment: Source values are retained in their original FFIEC reporting units

The source records were matched by RSSD ID and checked for duplicate rows and institution-name mismatches.

## Required Metrics

| Metric | Calculation |
| --- | --- |
| Tier 1 capital ratio | Tier 1 capital / risk-weighted assets |
| Leverage ratio | Tier 1 capital / average total assets |
| Loan-to-deposit ratio | Total loans / total deposits |
| Non-performing loan ratio | Loans 90+ days past due or nonaccrual / total loans |
| 12-month cumulative liquidity gap | (Rate-sensitive assets - rate-sensitive liabilities through 12 months) / total assets |

## Key Finding

JPMorgan Chase is the most exposed bank from a short-term liquidity perspective within this peer group, with the lowest 12-month cumulative liquidity gap at 29.68%. However, its Tier 1 capital ratio remains strong at 15.13% and its non-performing loan ratio is relatively low at 0.76%, indicating that its relative vulnerability is driven primarily by liquidity rather than capital adequacy or credit quality.

"Most exposed" is a relative ranking among the five banks and does not imply that JPMorgan Chase is distressed or below its regulatory capital requirements.

## Power BI Requirements

The completed scorecard should include:

- An action-oriented title that explicitly identifies the most exposed bank.
- The conclusion metric in the top-left area of the page.
- Tier 1 capital ratio cards for all five banks.
- Formula-driven conditional colors for the Tier 1 capital ratio:
  - Green: ratio greater than or equal to 10%
  - Amber: ratio from 8% to below 10%
  - Red: ratio below 8%
- A ranked bar chart or table showing the 12-month cumulative liquidity gap, with the most exposed bank first.
- Leverage ratio, loan-to-deposit ratio, and non-performing loan ratio on a secondary panel or drill-through page.
- A two- to three-sentence exposure note referring to at least two required metrics.

## Repository Contents

```text
Fintech590-Lecture5/
|-- Fintech590_Lecture5_Scorecard.pbix
|-- exposure_note.txt
|-- Book1.xlsx
`-- README.md
```

- `Fintech590_Lecture5_Scorecard.pbix`: Final Power BI scorecard.
- `exposure_note.txt`: Short interpretation of the most exposed bank.
- `Book1.xlsx`: Clean five-bank metrics table used by Power BI.
- `README.md`: Project methodology, findings, and usage notes.

## How to Review

1. Download or clone this repository.
2. Open `Fintech590_Lecture5_Scorecard.pbix` in Microsoft Power BI Desktop.
3. Confirm that the scorecard opens with all visuals populated.
4. Review the liquidity ranking, Tier 1 capital cards, supporting metrics, and exposure note.

## Team Responsibilities

| Responsibility | Owner |
| --- | --- |
| FFIEC data collection, RSSD verification, metric calculations, and exposure-note draft | [Name] |
| Power BI model, DAX conditional formatting, dashboard design, and PBIX delivery | [Name] |
| Final formula, ranking, visual, and submission review | Both team members |

## Submission Checklist

- [ ] All five holding companies are included.
- [ ] The June 30, 2026 reporting quarter is used consistently.
- [ ] All five required metrics are visible in the Power BI report or supporting panel.
- [ ] The Tier 1 capital colors are driven by a DAX formula.
- [ ] The liquidity gap ranking places the most exposed bank first.
- [ ] The action title names the most exposed bank and states the conclusion.
- [ ] The exposure note refers to at least two required metrics.
- [ ] The PBIX opens with all panels rendered without manual refresh steps.
- [ ] The PBIX and exposure note are committed to this repository.
- [ ] No API keys, passwords, or other credentials are committed.

## Security Note

Do not commit FFIEC credentials, API keys, passwords, local configuration files containing secrets, or other sensitive information to this repository.
