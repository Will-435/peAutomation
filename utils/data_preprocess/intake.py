"""
This file will take in the initial csv format of the data and transform it into a parquet file.
Parquet will store more efficiently, conserve datatypes and feed into SQL naturaly.

Input:
	Intake key data from surfer.py and format a pandas df

Output:
	Output a converted parquet file, for import by handler.py
"""
