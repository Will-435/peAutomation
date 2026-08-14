# PE Automation

An origination and screening pipeline for private equity deal sourcing. The pipeline finds and ranks private UK companies worth approaching, then screens the shortlist for risk and fit. Full architecture detail lives in `PE_Pipeline_Architecture.md`.

## Pipeline order

**Data.** Raw company, financial and procurement data is ingested and aggregated into one row per company per decision date, using SQL window functions to keep only information that was actually knowable at that point in time.

**Origination.** The `origination/` directory builds the signals used to find and rank prospects, in three tiers by evidence strength.

Tier 1 pulls facts directly from public registers, so there is no estimation error. This covers tender participation history, statutory filings from Companies House, secured debt and charges, ownership and group structure, and accreditation status from company websites.

Tier 2 covers modelled methods with a measured error band: entity resolution to match company records across sources, an Altman Z-double-prime distress score, SME credit scoring from financial ratios, and industry classification from company text.

Tier 3 covers estimates that should only ever be used as a range, never a single figure: valuation by industry multiples, and revenue estimated from headcount as a cross check rather than a standalone number.

A validation harness measures how accurate each method actually is, by testing it against companies that file full accounts and comparing the estimate to the real filed figures.

**Screening.** Shortlisted companies get a deeper pass, covering nearest-neighbour comparables, a predictive score, calibration, explanation of the score, and counterfactual drivers. Not yet built.

**Output.** A written brief per surviving candidate. Not yet built.

## Setup

Python dependencies are listed in `requirements.txt`. Companies House and other API keys go in `config.py`, which is not committed.
