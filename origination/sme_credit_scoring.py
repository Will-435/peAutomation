"""
This file will score default risk with logistic regression / gradient boosting on
financial ratios, plus company text as an additional feature set - not as a
standalone credit opinion. Benchmark against a bought Creditsafe or Experian score.

Input:
	Financial ratios from statutory_filings.py, plus text features (directors'
	reports, filing narratives) from company filings

Output:
	Calibrated default probability per company, with AUC measured with and without
	the text features
"""
