"""
This file will check each company against the UK public tender portals to see whether
it has ever bid for or won a public contract. Absence of tender history is the strongest
origination signal in the pipeline; frequent winners are deprioritised.

Input:
	Resolved company identity (from utils/similar_identifier) to search across
	Find a Tender, Contracts Finder, Sell2Wales, Public Contracts Scotland, eTendersNI,
	and bidstats.uk

Output:
	Per company: award count, most recent award date, buying authority
"""
