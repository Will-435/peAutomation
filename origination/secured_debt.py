"""
This file will read leverage and lender relationships from the Companies House
charges register - the UK functional equivalent of a US UCC-1 filing.

Input:
	Company number, queried against the Companies House charges register

Output:
	Per charge: type, date, and lender where available
"""
