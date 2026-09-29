# Institutional Risk Memo

**To:** Risk Committee  
**From:** Abhinav Saraf and Ziye Luo  
**Date:** September 29, 2026  
**Subject:** JPMorgan Chase funding exposure under the Defense 1 stress paths

## Recommendation

Place JPMorgan Chase on a targeted funding-liquidity watch. Ask Treasury to validate deposit repricing and runoff assumptions, committed wholesale/FHLB capacity, and collateral available for replacement funding before the next committee review. A broad capital action is not the first response to this modeled exposure: JPMorgan has the strongest starting Tier 1 ratio of the five firms, while its 12-month repricing-gap proxy is the weakest.

## Capital and liquidity evidence

At Q0, JPMorgan's Tier 1 ratio is **15.1%**, the highest in the peer set, but its 12-month liquidity gap is **29.7% of assets**, versus **36.3%–39.5%** for the other four. Liabilities repricing within a year are **16.4% of JPMorgan's assets**, compared with **8.8%–11.6%** for peers. The gap is a contractual repricing proxy, not immediately available cash or a liquidity coverage ratio; it points to relative funding sensitivity rather than a predicted failure.

## Adverse and Severely Adverse impacts

| Class scenario | JPMorgan Q9 Tier 1 | JPMorgan Q9 12-month gap | Committee reading |
|---|---:|---:|---|
| Adverse | **14.1%** (−1.0 percentage point from Q0) | **27.0%** (−2.7 points) | Gradual 5% deposit runoff by Q4 narrows the already-lowest peer gap. |
| Severely Adverse | **13.8%** (−1.3 points) | **21.6%** (−8.1 points) | 15% runoff by Q2 makes JPMorgan the clearest funding watch item, despite remaining capital strength. |

Under the Severe scenario, the 10% securities haircut equals **24.9% of JPMorgan's starting Tier 1 capital** as a mark-to-market exposure; it is displayed separately and not deducted again from the prescribed Tier 1 path. Wells Fargo deserves a separate capital watch: its Tier 1 path reaches **9.6% at Q4** before recovering to **10.1% at Q9**, the lowest Q9 capital ratio in the group.

## Conditions for changing the recommendation

Reduce the JPMorgan watch if Treasury substantiates stickier deposits, usable committed replacement funding, and a revised repricing schedule that materially closes the peer gap. Escalate to a funding contingency review if runoff exceeds the modeled path, replacement funding is unavailable or materially more expensive, or the gap deteriorates beyond this scenario. Revisit capital measures only if realized securities losses or a revised capital path erode the apparent Tier 1 headroom; the current stress path alone does not establish that need.

## Model and source note

The course brief's stated cumulative Tier 1 drops conflict with its explicit quarterly steps: the steps sum to **−1.0 point** (Adverse) and **−1.3 points** (Severely Adverse) at Q9, versus its approximate **−1.6** and **−3.1** point headlines. The console and this memo use the quarterly steps so every quarter is reproducible. Deposit runoff is assumed to be replaced by wholesale/FHLB funding that reprices within 12 months; securities haircuts are phased to the brief's Q4/Q2 endpoints as a team assumption. These are classroom scenarios, not Federal Reserve CCAR projections or a cash-flow liquidity forecast.

**Sources:** FFIEC FR Y-9C holding-company bulk file for 2026-06-30 (`BHCF20260630.ZIP`, included in the [team repository](https://github.com/Lengwinex9xLok/Fintech590)); FINTECH 590 Defense 1 assignment brief; team Power BI console and `Defense 1/stress_paths_Q0_Q9.csv`. The [Federal Reserve's FR Y-9C description](https://www.federalreserve.gov/apps/reportingforms/Report/Index/FR_Y-9C) identifies the report as consolidated holding-company financial statements. Every quoted scenario figure was independently recomputed from the source fields in the accompanying audit workbook.
