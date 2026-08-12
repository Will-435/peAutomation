"""
This file will cross-check revenue as headcount x industry revenue-per-employee
benchmark. This is a sanity check against valuation_multiples.py, not a standalone
estimator - within-industry productivity dispersion alone produces roughly +/-2x error.

Input:
	Headcount from statutory_filings.py (filed average employee count, the most
	reliable source), cross-checked against the company website

Output:
	Cross-check revenue estimate per company; flagged unusable where it disagrees
	with valuation_multiples.py by more than ~2x
"""
