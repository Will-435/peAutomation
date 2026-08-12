"""
This file will resolve group structure so subsidiaries of larger groups can be
deprioritised - procurement for a subsidiary is usually handled centrally by the parent.

Input:
	Company number, queried against the Companies House Persons with Significant
	Control register and parent/subsidiary links

Output:
	Ownership chain per company, with a flag for subsidiaries of a larger group
"""
