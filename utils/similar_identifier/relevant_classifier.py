"""
By using Python's sklearn library, this library will classify companies into industries, rough valuations, and suitability for the PE firm, given inputted constraints. Additionaly, this is where the pipeline will pull from the sql data base and collate a portfolio of similar comapnies that we could namedrop. **IF AND ONLY IF** we have worked with an exceptionally similar cmpany we can retrain our outputter model to hyper-fit this companies specifications.

Input:
	Key mindustries and specialities for the PE firm.
	SQL Database appended data
	
Output:
	A portfolio (as an array) of similar companies that we have worked with
	A classification decision on the suitability of the company for our PE firm.
"""
