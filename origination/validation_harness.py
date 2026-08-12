"""
This file will measure real error rates for every estimation method in origination/
against a sample of medium/large UK companies that file full accounts including the
P&L - a population that is private, UK, and has real financials to check against.

Input:
	Sample of full-filing private UK companies from Companies House, with the
	pipeline blinded to their filed financials

Output:
	Per method: mean error, dispersion (standard deviation, quantiles, worst case),
	direction of bias, and interval calibration (does a stated 80% interval contain
	the truth about 80% of the time)
"""
