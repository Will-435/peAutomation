"""
This file will reclassify companies from their website text where the registered
SIC code is stale or wrong. Classification error propagates into every peer-based
estimate downstream, so disagreements are flagged for manual review rather than
silently resolved.

Input:
	Company website text, cross-checked against the filed SIC code from
	statutory_filings.py

Output:
	Industry classification per company with a confidence score, at the finest
	granularity the labelled data supports
"""
