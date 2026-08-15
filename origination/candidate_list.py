"""
Builds the candidate list that enters the pipeline. Candidates come either from a
target file supplied by hand or from a Companies House search by SIC code and
region. The criteria that produced the list are written alongside it, because a
screen is only interpretable against the population it was drawn from.

The list is kept separate from the resolved output, so a change to matching
cannot silently change which companies were considered in the first place.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from config import COMPANIES_HOUSE_API_KEY

COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"
ADVANCED_SEARCH_PATH = "/advanced-search/companies"
REQUEST_TIMEOUT_SECONDS = 30
RESULTS_PER_PAGE = 100
MAXIMUM_SEARCH_RESULTS = 500
ACTIVE_COMPANY_STATUS = "active"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

DATA_RAW_DIRECTORY = Path("data/raw")
SUPPLIED_TARGETS_FILE = DATA_RAW_DIRECTORY / "target_companies.csv"
CANDIDATE_LIST_FILE = DATA_RAW_DIRECTORY / "candidate_list.parquet"
SELECTION_CRITERIA_FILE = DATA_RAW_DIRECTORY / "candidate_selection_criteria.json"

SUPPLIED_FILE_ROUTE = "supplied_target_file"
COMPANIES_HOUSE_ROUTE = "companies_house_advanced_search"


def load_supplied_targets(targets_file = SUPPLIED_TARGETS_FILE):
    """
    Reads a hand supplied target list. The file only has to carry company_name,
    any other columns it holds are kept and passed through to resolution.

    INPUTS:
        * targets_file

    OUTPUTS:
        * dataframe of candidates, or None when no file was supplied
    """
    if not targets_file.exists():
        return None
    return pd.read_csv(targets_file)


def search_companies_house(sic_codes = None, location = None, maximum_results = MAXIMUM_SEARCH_RESULTS):
    """
    Searches Companies House for active companies matching the given SIC codes and
    location. Paging stops at the result cap rather than pulling the whole
    register, so a broad search cannot run away.

    INPUTS:
        * sic_codes
        * location
        * maximum_results

    OUTPUTS:
        * dataframe of candidates with company_number, company_name, postcode and sic_code
    """
    collected_records = []
    start_index = 0
    while len(collected_records) < maximum_results:
        search_parameters = {
            "company_status": ACTIVE_COMPANY_STATUS,
            "size": RESULTS_PER_PAGE,
            "start_index": start_index,
        }
        if sic_codes:
            search_parameters["sic_codes"] = ",".join(sic_codes)
        if location:
            search_parameters["location"] = location
        response = requests.get(
            f"{COMPANIES_HOUSE_BASE_URL}{ADVANCED_SEARCH_PATH}",
            params = search_parameters,
            auth = (COMPANIES_HOUSE_API_KEY, ""),
            timeout = REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        returned_items = response.json().get("items", [])
        if not returned_items:
            break
        for item in returned_items:
            registered_address = item.get("registered_office_address", {})
            item_sic_codes = item.get("sic_codes", [])
            collected_records.append({
                "company_number": item.get("company_number"),
                "company_name": item.get("company_name"),
                "postcode": registered_address.get("postal_code"),
                "sic_code": item_sic_codes[0] if item_sic_codes else None,
                "website_url": None,
            })
        start_index = start_index + RESULTS_PER_PAGE
    return pd.DataFrame(collected_records[:maximum_results])


def record_selection_criteria(route = None, sic_codes = None, location = None, candidate_count = None):
    """
    Writes down how the candidate list was drawn. Without this a later reader
    cannot tell whether a thin result means a thin population or a narrow search.

    INPUTS:
        * route
        * sic_codes
        * location
        * candidate_count

    OUTPUTS:
        * path of the written criteria file
    """
    criteria = {
        "route": route,
        "sic_codes": sic_codes,
        "location": location,
        "candidate_count": candidate_count,
        "drawn_at": datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT),
    }
    DATA_RAW_DIRECTORY.mkdir(parents = True, exist_ok = True)
    SELECTION_CRITERIA_FILE.write_text(json.dumps(criteria, indent = 2))
    return SELECTION_CRITERIA_FILE


def build_candidate_list(sic_codes = None, location = None):
    """
    Builds the candidate list, preferring a supplied target file when one exists
    and falling back to a Companies House search. A supplied file wins because an
    explicit target list is a deliberate choice and should not be overridden.

    INPUTS:
        * sic_codes
        * location

    OUTPUTS:
        * dataframe of candidates
        * route used
    """
    supplied_targets = load_supplied_targets()
    if supplied_targets is not None:
        return supplied_targets, SUPPLIED_FILE_ROUTE
    return search_companies_house(sic_codes = sic_codes, location = location), COMPANIES_HOUSE_ROUTE


def main():
    """Builds and saves the candidate list with the criteria that produced it."""
    DATA_RAW_DIRECTORY.mkdir(parents = True, exist_ok = True)
    candidates, route = build_candidate_list()
    if candidates is None or len(candidates) == 0:
        print(f"No candidates found, supply {SUPPLIED_TARGETS_FILE} or pass search criteria")
        return
    candidates.to_parquet(CANDIDATE_LIST_FILE)
    record_selection_criteria(route = route, candidate_count = len(candidates))
    print(f"Saved {len(candidates)} candidates via {route}")


if __name__ == "__main__":
    main()
