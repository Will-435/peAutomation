"""
Classifies companies from their website text where the registered SIC code is stale
or wrong. Classification error propagates into every peer based estimate, so low
confidence labels and disagreements with the filed code are routed to manual review
rather than silently accepted.
"""

from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

MAXIMUM_VOCABULARY_SIZE = 5000
MAXIMUM_ITERATIONS = 1000
# Labels below this confidence go to a human, not into the database.
CONFIDENCE_REVIEW_THRESHOLD = 0.60

DATA_PROCESSED_DIRECTORY = Path("data/processed")
LABELLED_COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "labelled_industry_data.parquet"
CLASSIFICATIONS_FILE = DATA_PROCESSED_DIRECTORY / "industry_classifications.parquet"


def train_classifier(labelled_texts = None, labelled_codes = None):
    """
    Fits a TF IDF and logistic model on hand labelled company descriptions.

    INPUTS:
        * labelled_texts
        * labelled_codes

    OUTPUTS:
        * fitted vectoriser
        * fitted classifier
    """
    vectoriser = TfidfVectorizer(max_features = MAXIMUM_VOCABULARY_SIZE)
    text_features = vectoriser.fit_transform(labelled_texts)
    classifier = LogisticRegression(max_iter = MAXIMUM_ITERATIONS)
    classifier.fit(text_features, labelled_codes)
    return vectoriser, classifier


def classify_with_confidence(vectoriser = None, classifier = None, website_text = None):
    """
    Predicts an industry code with a confidence score for review routing.

    INPUTS:
        * vectoriser
        * classifier
        * website_text

    OUTPUTS:
        * predicted code
        * confidence between zero and one
    """
    text_features = vectoriser.transform([website_text])
    probabilities = classifier.predict_proba(text_features)[0]
    best_position = probabilities.argmax()
    predicted_code = classifier.classes_[best_position]
    confidence = probabilities[best_position]
    return predicted_code, confidence


def build_classification_record(vectoriser = None, classifier = None,
                                company_number = None, website_text = None, filed_sic_code = None):
    """
    Classifies one company and flags disagreement with the filed SIC code.
    Disagreements go to review, neither code is silently preferred.

    INPUTS:
        * vectoriser
        * classifier
        * company_number
        * website_text
        * filed_sic_code

    OUTPUTS:
        * dictionary with predicted code, confidence and review flags
    """
    predicted_code, confidence = classify_with_confidence(
        vectoriser = vectoriser,
        classifier = classifier,
        website_text = website_text,
    )
    needs_review = confidence < CONFIDENCE_REVIEW_THRESHOLD
    disagrees_with_filed = predicted_code != filed_sic_code
    return {
        "company_number": company_number,
        "predicted_code": predicted_code,
        "confidence": confidence,
        "filed_sic_code": filed_sic_code,
        "needs_review": needs_review or disagrees_with_filed,
        "disagrees_with_filed": disagrees_with_filed,
    }


def main():
    """Trains on the labelled set and classifies every company with website text."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not LABELLED_COMPANIES_FILE.exists():
        print("No labelled industry data found, hand label a sample first")
        return
    labelled_data = pd.read_parquet(LABELLED_COMPANIES_FILE)
    vectoriser, classifier = train_classifier(
        labelled_texts = labelled_data["website_text"].tolist(),
        labelled_codes = labelled_data["industry_code"].tolist(),
    )
    records = []
    for company_row in labelled_data.itertuples():
        records.append(build_classification_record(
            vectoriser = vectoriser,
            classifier = classifier,
            company_number = company_row.company_number,
            website_text = company_row.website_text,
            filed_sic_code = company_row.filed_sic_code,
        ))
    classifications = pd.DataFrame(records)
    classifications.to_parquet(CLASSIFICATIONS_FILE)
    print(f"Saved classifications for {len(classifications)} companies")


if __name__ == "__main__":
    main()
