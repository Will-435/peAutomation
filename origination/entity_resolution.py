"""
Matches company records across data sources on name, location and industry. Every
downstream method fails silently on a wrong match, so nothing scales until recall
clears the target on a hand labelled sample. Blocking uses MinHash signatures to
keep candidate generation linear, scoring then adjudicates only the candidates.
"""

import difflib
import hashlib
import math
from pathlib import Path

import pandas as pd
import requests

from config import COMPANIES_HOUSE_API_KEY

COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"
COMPANY_SEARCH_PATH = "/search/companies"
REQUEST_TIMEOUT_SECONDS = 30
REFERENCE_RESULTS_PER_NAME = 20

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

RESOLVED_COMPANY_COLUMNS = ["company_number", "company_name", "postcode", "sic_code", "website_url"]

DATA_RAW_DIRECTORY = Path("data/raw")
DATA_PROCESSED_DIRECTORY = Path("data/processed")
CANDIDATE_LIST_FILE = DATA_RAW_DIRECTORY / "candidate_list.parquet"
RESOLVED_COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
RESOLVED_MATCHES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_matches.parquet"
UNMATCHED_CANDIDATES_FILE = DATA_PROCESSED_DIRECTORY / "unmatched_candidates.parquet"


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


def has_value(field_value = None):
    """
    Returns whether a field carries something worth comparing. Blanks and nulls
    read as absent rather than as a value that disagrees.

    INPUTS:
        * field_value

    OUTPUTS:
        * true when the field can be compared
    """
    if field_value is None:
        return False
    if isinstance(field_value, float) and math.isnan(field_value):
        return False
    return str(field_value).strip() != ""


def score_candidate_pair(record_one = None, record_two = None):
    """
    Scores a candidate pair on name, location and industry agreement. Name carries
    most weight, location and industry break ties between similar names.

    Weights are renormalised over the fields both records actually carry. A field
    only one side holds is skipped rather than counted as disagreement, otherwise
    a candidate known by name alone could never reach the threshold no matter how
    exactly the name matched.

    INPUTS:
        * record_one
        * record_two

    OUTPUTS:
        * weighted score between zero and one
    """
    name_one = normalise_company_name(raw_name = record_one["company_name"])
    name_two = normalise_company_name(raw_name = record_two["company_name"])
    weighted_score = NAME_WEIGHT * difflib.SequenceMatcher(None, name_one, name_two).ratio()
    total_weight = NAME_WEIGHT

    if has_value(record_one.get("postcode")) and has_value(record_two.get("postcode")):
        weighted_score = weighted_score + LOCATION_WEIGHT * float(record_one["postcode"] == record_two["postcode"])
        total_weight = total_weight + LOCATION_WEIGHT

    if has_value(record_one.get("sic_code")) and has_value(record_two.get("sic_code")):
        weighted_score = weighted_score + INDUSTRY_WEIGHT * float(record_one["sic_code"] == record_two["sic_code"])
        total_weight = total_weight + INDUSTRY_WEIGHT

    return weighted_score / total_weight


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


def fetch_reference_records(company_name = None):
    """
    Searches Companies House for registered companies matching a candidate name.
    These are the reference records a supplied name is matched against, since a
    target list gives a name and the pipeline needs a company number.

    INPUTS:
        * company_name

    OUTPUTS:
        * list of reference record dictionaries
    """
    response = requests.get(
        f"{COMPANIES_HOUSE_BASE_URL}{COMPANY_SEARCH_PATH}",
        params = {"q": company_name, "items_per_page": REFERENCE_RESULTS_PER_NAME},
        auth = (COMPANIES_HOUSE_API_KEY, ""),
        timeout = REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    reference_records = []
    for item in response.json().get("items", []):
        registered_address = item.get("address", {})
        reference_records.append({
            "company_number": item.get("company_number"),
            "company_name": item.get("title"),
            "postcode": registered_address.get("postal_code"),
            "sic_code": None,
            "website_url": None,
        })
    return reference_records


def resolve_candidate(candidate_record = None):
    """
    Resolves one candidate to a registered company. A candidate that already
    carries a company number came from the register and needs no matching, the
    rest are searched by name and scored, and the best scoring reference record
    above the threshold wins.

    INPUTS:
        * candidate_record

    OUTPUTS:
        * resolved record dictionary, or None when nothing cleared the threshold
        * match audit dictionary, or None when no matching was needed
    """
    if candidate_record.get("company_number"):
        return candidate_record, None
    reference_records = fetch_reference_records(company_name = candidate_record.get("company_name"))
    best_record = None
    best_score = 0.0
    for reference_record in reference_records:
        pair_score = score_candidate_pair(record_one = candidate_record, record_two = reference_record)
        if pair_score > best_score:
            best_score = pair_score
            best_record = reference_record
    if best_record is None or best_score < MATCH_SCORE_THRESHOLD:
        return None, {
            "candidate_name": candidate_record.get("company_name"),
            "matched_name": best_record.get("company_name") if best_record else None,
            "score": best_score,
            "accepted": False,
        }
    return best_record, {
        "candidate_name": candidate_record.get("company_name"),
        "matched_name": best_record.get("company_name"),
        "score": best_score,
        "accepted": True,
    }


def resolve_candidate_list(candidate_records = None):
    """
    Resolves every candidate, keeping the ones that matched and the ones that did
    not as separate outputs. An unmatched candidate is recorded rather than
    dropped, because a company missing from the resolved list is silently absent
    from every later stage of the pipeline.

    INPUTS:
        * candidate_records

    OUTPUTS:
        * dataframe of resolved companies
        * dataframe of match audit rows
        * dataframe of unmatched candidates
    """
    resolved_records = []
    audit_rows = []
    unmatched_records = []
    for candidate_record in candidate_records:
        resolved_record, audit_row = resolve_candidate(candidate_record = candidate_record)
        if audit_row is not None:
            audit_rows.append(audit_row)
        if resolved_record is None:
            unmatched_records.append(candidate_record)
            continue
        resolved_records.append({
            column: resolved_record.get(column, candidate_record.get(column))
            for column in RESOLVED_COMPANY_COLUMNS
        })
    return pd.DataFrame(resolved_records), pd.DataFrame(audit_rows), pd.DataFrame(unmatched_records)


def main():
    """Resolves the candidate list into the company list every later module reads."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not CANDIDATE_LIST_FILE.exists():
        print("No candidate list found, run candidate_list first")
        return
    candidate_records = pd.read_parquet(CANDIDATE_LIST_FILE).to_dict("records")
    resolved, audit, unmatched = resolve_candidate_list(candidate_records = candidate_records)
    resolved.to_parquet(RESOLVED_COMPANIES_FILE)
    if len(audit) > 0:
        audit.to_parquet(RESOLVED_MATCHES_FILE)
    if len(unmatched) > 0:
        unmatched.to_parquet(UNMATCHED_CANDIDATES_FILE)
    print(f"Resolved {len(resolved)} companies, {len(unmatched)} candidates unmatched")


if __name__ == "__main__":
    main()
