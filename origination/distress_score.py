"""
This file will rank companies by financial distress using the Altman Z'' formula
(private-company variant). The EBIT term needs the profit and loss account, which
most small UK companies withhold - do not substitute a guessed EBIT; run the
reduced-form three-term score instead where the P&L is missing.

Input:
	Filed balance sheet line items from statutory_filings.py (working capital,
	retained earnings, EBIT where available, book value of equity, total liabilities,
	total assets)

Output:
	Z'' score per company, recalibrated on UK data rather than a single global cut-off
"""
