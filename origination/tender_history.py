"""
Builds tender participation history per company. A company with no award history in
a sector with public spend is a prospect, so the screen stores award count, most
recent award date and buying authorities. The data is factual, all error sits in
name matching, so searches run on resolved identities from entity_resolution.
"""

import json
from pathlib import Path

import pandas as pd
import requests

# Find a Tender, Sell2Wales, Public Contracts Scotland and eTendersNI follow later,
# each portal uses the same search then summarise shape.
CONTRACTS_FINDER_SEARCH_URL = "https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json"
REQUEST_TIMEOUT_SECONDS = 30
RESULTS_PER_PAGE = 100

DATA_RAW_DIRECTORY = Path("data/raw/tender_notices")
DATA_PROCESSED_DIRECTORY = Path("data/processed")
COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
TENDER_HISTORY_FILE = DATA_PROCESSED_DIRECTORY / "tender_history.parquet"


def ensure_directories():
    """Creates the raw and processed data directories if they are missing."""
    DATA_RAW_DIRECTORY.mkdir(parents = True, exist_ok = True)
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)


def search_contracts_finder(company_name = None):
    """
    Searches Contracts Finder for notices that name the supplied company.

    INPUTS:
        * company_name

    OUTPUTS:
        * list of notice dictionaries
    """
    search_payload = {"searchCriteria": {"keyword": company_name}, "size": RESULTS_PER_PAGE}
    response = requests.post(CONTRACTS_FINDER_SEARCH_URL, json = search_payload, timeout = REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get("noticeList", [])


def save_raw_notices(company_name = None, notices = None):
    """
    Keeps the portal response exactly as given so parsing changes can be rerun.

    INPUTS:
        * company_name
        * notices

    OUTPUTS:
        * path of the saved raw file
    """
    safe_name = company_name.lower().replace(" ", "_")
    raw_file = DATA_RAW_DIRECTORY / f"{safe_name}.json"
    raw_file.write_text(json.dumps(notices))
    return raw_file


def summarise_awards(company_name = None, notices = None):
    """
    Reduces raw notices to the award facts the screen stores per company.

    INPUTS:
        * company_name
        * notices

    OUTPUTS:
        * dictionary with award count, most recent award date and buying authorities
    """
    items = [notice.get("item", notice) for notice in notices]
    awarded = [item for item in items if item.get("awardedDate")]
    award_dates = sorted(item["awardedDate"] for item in awarded)
    buying_authorities = sorted({item.get("organisationName", "") for item in awarded})
    most_recent_award = award_dates[-1] if award_dates else None
    return {
        "company_name": company_name,
        "award_count": len(awarded),
        "most_recent_award_date": most_recent_award,
        "buying_authorities": buying_authorities,
    }


def build_tender_history(company_names = None):
    """
    Runs the portal search for every company and collects one summary row each.

    INPUTS:
        * company_names

    OUTPUTS:
        * dataframe with one row per company
    """
    summaries = []
    for company_name in company_names:
        notices = search_contracts_finder(company_name = company_name)
        save_raw_notices(company_name = company_name, notices = notices)
        summaries.append(summarise_awards(company_name = company_name, notices = notices))
    return pd.DataFrame(summaries)


def main():
    """Builds the tender history table for the resolved company list."""
    ensure_directories()
    if not COMPANIES_FILE.exists():
        print("No resolved company list found, run entity_resolution first")
        return
    company_names = pd.read_parquet(COMPANIES_FILE)["company_name"].tolist()
    tender_history = build_tender_history(company_names = company_names)
    tender_history.to_parquet(TENDER_HISTORY_FILE)
    print(f"Saved tender history for {len(tender_history)} companies")


if __name__ == "__main__":
    main()
