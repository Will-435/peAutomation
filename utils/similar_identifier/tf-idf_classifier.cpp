/*
This file will use a ine hot encoding method to identify key words in companies descriptions. By encoding them like this, they will be easy to input into a ML model later.

Input:
	The tf-idf outputs from tf-idf_processor, via the SQL database.

Output:
	Encoded arrays, where each index corrolates to known words. this will be fed into a amchine learning model.
*/
