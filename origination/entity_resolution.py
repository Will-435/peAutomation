"""
This file will match company records across data sources on name, location, and
industry, with MinHash blocking to keep matching linear in record count. Every
downstream origination method depends on this being correct - a silent mismatch
is worse than a missing record.

Input:
	Raw company records from each data source (tenders, Companies House, web)

Output:
	Resolved company identity per record, for use as the join key everywhere else
	in origination/
"""
