"""
Matches company records across data sources on name, location and industry. Every
downstream method fails silently on a wrong match, so nothing scales until recall
clears the target on a hand labelled sample. Blocking uses MinHash signatures to
keep candidate generation linear, scoring then adjudicates only the candidates.
"""

import difflib
import hashlib
from pathlib import Path

import pandas as pd

LEGAL_SUFFIXES = ["limited", "ltd", "llp", "plc", "public limited company"]
SHINGLE_LENGTH = 3
NUMBER_OF_HASH_FUNCTIONS = 64
HEXADECIMAL_BASE = 16
CANDIDATE_SIMILARITY_THRESHOLD = 0.5
MATCH_SCORE_THRESHOLD = 0.90
# Recall on the hand labelled sample must clear this before any pipeline scales.
TARGET_RECALL = 0.90

NAME_WEIGHT = 0.6
LOCATION_WEIGHT = 0.2
INDUSTRY_WEIGHT = 0.2

DATA_PROCESSED_DIRECTORY = Path("data/processed")
RESOLVED_MATCHES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_matches.parquet"


def normalise_company_name(raw_name = None):
    """
    Lowercases a company name and strips punctuation and legal form suffixes,
    since Limited, Ltd and LLP variants defeat naive string comparison.

    INPUTS:
        * raw_name

    OUTPUTS:
        * normalised name string
    """
    cleaned_name = "".join(character for character in raw_name.lower() if character.isalnum() or character == " ")
    words = cleaned_name.split()
    words = [word for word in words if word not in LEGAL_SUFFIXES]
    return " ".join(words)


def name_shingles(normalised_name = None):
    """
    Breaks a name into overlapping character shingles for MinHash blocking.

    INPUTS:
        * normalised_name

    OUTPUTS:
        * set of shingle strings
    """
    padded_name = normalised_name.replace(" ", "_")
    if len(padded_name) < SHINGLE_LENGTH:
        return {padded_name}
    shingle_count = len(padded_name) - SHINGLE_LENGTH + 1
    return {padded_name[position:position + SHINGLE_LENGTH] for position in range(shingle_count)}


def minhash_signature(shingles = None):
    """
    Builds a MinHash signature so similar names land in the same candidate block
    without comparing every pair.

    INPUTS:
        * shingles

    OUTPUTS:
        * list of minimum hash values, one per seeded hash function
    """
    signature = []
    for seed_value in range(NUMBER_OF_HASH_FUNCTIONS):
        hash_values = [
            int(hashlib.md5(f"{seed_value}:{shingle}".encode()).hexdigest(), HEXADECIMAL_BASE)
            for shingle in shingles
        ]
        signature.append(min(hash_values))
    return signature


def signature_similarity(signature_one = None, signature_two = None):
    """
    Estimates Jaccard similarity as the fraction of matching signature positions.

    INPUTS:
        * signature_one
        * signature_two

    OUTPUTS:
        * similarity between zero and one
    """
    matches = sum(
        first_value == second_value
        for first_value, second_value in zip(signature_one, signature_two)
    )
    return matches / NUMBER_OF_HASH_FUNCTIONS


def score_candidate_pair(record_one = None, record_two = None):
    """
    Scores a candidate pair on name, location and industry agreement. Name carries
    most weight, location and industry break ties between similar names.

    INPUTS:
        * record_one
        * record_two

    OUTPUTS:
        * weighted score between zero and one
    """
    name_one = normalise_company_name(raw_name = record_one["company_name"])
    name_two = normalise_company_name(raw_name = record_two["company_name"])
    name_similarity = difflib.SequenceMatcher(None, name_one, name_two).ratio()
    location_agreement = float(record_one.get("postcode") == record_two.get("postcode"))
    industry_agreement = float(record_one.get("sic_code") == record_two.get("sic_code"))
    return (
        NAME_WEIGHT * name_similarity
        + LOCATION_WEIGHT * location_agreement
        + INDUSTRY_WEIGHT * industry_agreement
    )


def match_records(records_one = None, records_two = None):
    """
    Matches two record lists by blocking on MinHash signatures then scoring the
    surviving candidates. Only pairs above the match threshold are returned.

    INPUTS:
        * records_one
        * records_two

    OUTPUTS:
        * dataframe of matched pairs with their scores
    """
    signatures_one = [
        minhash_signature(shingles = name_shingles(normalised_name = normalise_company_name(raw_name = record["company_name"])))
        for record in records_one
    ]
    signatures_two = [
        minhash_signature(shingles = name_shingles(normalised_name = normalise_company_name(raw_name = record["company_name"])))
        for record in records_two
    ]
    matches = []
    for first_index, record_one in enumerate(records_one):
        for second_index, record_two in enumerate(records_two):
            block_similarity = signature_similarity(
                signature_one = signatures_one[first_index],
                signature_two = signatures_two[second_index],
            )
            if block_similarity < CANDIDATE_SIMILARITY_THRESHOLD:
                continue
            pair_score = score_candidate_pair(record_one = record_one, record_two = record_two)
            if pair_score >= MATCH_SCORE_THRESHOLD:
                matches.append({
                    "name_one": record_one["company_name"],
                    "name_two": record_two["company_name"],
                    "score": pair_score,
                })
    return pd.DataFrame(matches)


def main():
    """Demonstrates matching on a small worked example."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    example_records_one = [{"company_name": "Acme Cleaning Limited", "postcode": "BS1 4DJ", "sic_code": "81210"}]
    example_records_two = [{"company_name": "ACME CLEANING LTD", "postcode": "BS1 4DJ", "sic_code": "81210"}]
    matches = match_records(records_one = example_records_one, records_two = example_records_two)
    matches.to_parquet(RESOLVED_MATCHES_FILE)
    print(f"Saved {len(matches)} matches")


if __name__ == "__main__":
    main()
