"""
This file will pull registered company data directly from the Companies House API.
The filed balance sheet is read, not estimated - small companies may withhold the
profit and loss account, so revenue, margin, and EBIT can be missing.

Input:
	Company number, queried against the Companies House free API

Output:
	Registered address, incorporation date, SIC code, officer names and appointment
	dates, filing history, secured charges, and filed balance sheet line items
	(total assets, net assets, share capital, retained earnings, creditors)
"""
