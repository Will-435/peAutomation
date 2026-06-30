 /*
This file will convert the entire intaken SQL tabular data using a one hot encoding method, and then treat the rows as vectors. This will then calculate the euciladian distance, (with an added measure to mitigate the "curse of high dimensionality" once I have made one)

Input:
	SQL data in tabular form
	A specified refrence vector, from which we will calculate distance (the refrence vector will be the company under investigation)


Output: 
	An array of companies that we can deem "similar" - human evaluation needed.
*/
