"""
This file will estimate value as target scaling variable x median peer multiple.
The peer set gives a distribution, not a number - never collapse to the median
before the final output.

Input:
	Target company's scaling variable, peer set selected by industry_classification.py
	(three-digit granularity, widening only if peer count is insufficient)

Output:
	Full peer multiple distribution per company, carried forward uncollapsed
"""
