"""
This file will check a company's own website for pre-qualification accreditations -
the most actionable pitch hook in the pipeline, since it is a concrete, fixable blocker.
No registry covers this, so absence and presence must be recorded asymmetrically:
a claimed accreditation needs a cited source, a not-found result is "not found on
site", never "does not hold".

Input:
	Company website URL

Output:
	Per company: accreditation status for ISO 9001, ISO 14001, Constructionline,
	Cyber Essentials, and general pre-qualification readiness
"""
