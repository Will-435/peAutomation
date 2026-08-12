"""
Checks a company website for the accreditations that gate public tendering. Presence
must cite the page text asserting it. Absence is recorded as not found on site,
never as does not hold, because plenty of accredited companies do not advertise it.
"""

import re
from pathlib import Path

import pandas as pd
import requests

ACCREDITATION_TERMS = {
    "iso_9001": ["iso 9001", "iso9001"],
    "iso_14001": ["iso 14001", "iso14001"],
    "constructionline": ["constructionline"],
    "cyber_essentials": ["cyber essentials"],
}
NOT_FOUND_LABEL = "not found on site"
CLAIMED_LABEL = "claimed on site"
SNIPPET_CONTEXT_CHARACTERS = 120
HTML_TAG_PATTERN = r"<[^>]+>"
REQUEST_TIMEOUT_SECONDS = 30
# Precision and recall must be measured on a hand checked sample of this size
# before the extractor is trusted at scale. A false positive kills the pitch angle.
HAND_CHECK_SAMPLE_SIZE = 100

DATA_PROCESSED_DIRECTORY = Path("data/processed")
COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
ACCREDITATIONS_FILE = DATA_PROCESSED_DIRECTORY / "accreditation_status.parquet"


def fetch_page_text(website_url = None):
    """
    Downloads a page and reduces it to plain lowercase text.

    INPUTS:
        * website_url

    OUTPUTS:
        * plain text of the page
    """
    response = requests.get(website_url, timeout = REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    stripped_text = re.sub(HTML_TAG_PATTERN, " ", response.text)
    collapsed_text = re.sub(r"\s+", " ", stripped_text)
    return collapsed_text.lower()


def find_citation_snippet(page_text = None, search_term = None):
    """
    Returns the page text surrounding a matched term, as the citation for a claim.

    INPUTS:
        * page_text
        * search_term

    OUTPUTS:
        * snippet string, or None when the term is absent
    """
    match_position = page_text.find(search_term)
    if match_position < 0:
        return None
    snippet_start = max(0, match_position - SNIPPET_CONTEXT_CHARACTERS)
    snippet_end = match_position + len(search_term) + SNIPPET_CONTEXT_CHARACTERS
    return page_text[snippet_start:snippet_end]


def check_accreditations(page_text = None):
    """
    Checks the page text for each accreditation, recording presence and absence
    asymmetrically. A claim carries its citation, an absence stays open.

    INPUTS:
        * page_text

    OUTPUTS:
        * dictionary per accreditation with status and citation
    """
    results = {}
    for accreditation_name, term_variants in ACCREDITATION_TERMS.items():
        citation = None
        for term_variant in term_variants:
            citation = find_citation_snippet(page_text = page_text, search_term = term_variant)
            if citation:
                break
        status = CLAIMED_LABEL if citation else NOT_FOUND_LABEL
        results[accreditation_name] = {"status": status, "citation": citation}
    return results


def build_accreditation_record(company_name = None, website_url = None):
    """
    Runs the accreditation check for one company website.

    INPUTS:
        * company_name
        * website_url

    OUTPUTS:
        * flat dictionary with one status and citation column per accreditation
    """
    page_text = fetch_page_text(website_url = website_url)
    checks = check_accreditations(page_text = page_text)
    record = {"company_name": company_name, "website_url": website_url}
    for accreditation_name, check in checks.items():
        record[f"{accreditation_name}_status"] = check["status"]
        record[f"{accreditation_name}_citation"] = check["citation"]
    return record


def main():
    """Builds the accreditation table for companies with a known website."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not COMPANIES_FILE.exists():
        print("No resolved company list found, run entity_resolution first")
        return
    companies = pd.read_parquet(COMPANIES_FILE)
    companies = companies.dropna(subset = ["website_url"])
    records = []
    for company_row in companies.itertuples():
        records.append(build_accreditation_record(
            company_name = company_row.company_name,
            website_url = company_row.website_url,
        ))
    accreditations = pd.DataFrame(records)
    accreditations.to_parquet(ACCREDITATIONS_FILE)
    print(f"Saved accreditation status for {len(accreditations)} companies")


if __name__ == "__main__":
    main()
