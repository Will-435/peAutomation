"""
Pulls registered company data from the Companies House API. The balance sheet is
filed, never estimated. Revenue, margin and EBIT stay missing when a small company
withholds its profit and loss account, and nothing here tries to fill that gap.
"""

from pathlib import Path
from config import COMPANIES_HOUSE_API_KEY

import pandas as pd
import requests

COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"
REQUEST_TIMEOUT_SECONDS = 30

DATA_PROCESSED_DIRECTORY = Path("data/processed")
COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
STATUTORY_FILINGS_FILE = DATA_PROCESSED_DIRECTORY / "statutory_filings.parquet"


def fetch_endpoint(path = None):
    """
    Calls one Companies House endpoint with basic authentication.

    INPUTS:
        * path

    OUTPUTS:
        * decoded json dictionary
    """
    url = f"{COMPANIES_HOUSE_BASE_URL}{path}"
    response = requests.get(url, auth = (COMPANIES_HOUSE_API_KEY, ""), timeout = REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_company_profile(company_number = None):
    """Fetches the registered profile for one company."""
    return fetch_endpoint(path = f"/company/{company_number}")


def fetch_officers(company_number = None):
    """Fetches the officer list for one company."""
    return fetch_endpoint(path = f"/company/{company_number}/officers")


def fetch_filing_history(company_number = None):
    """Fetches the filing history for one company."""
    return fetch_endpoint(path = f"/company/{company_number}/filing-history")


def fetch_balance_sheet_items(company_number = None):
    """
    Placeholder for filed balance sheet retrieval from tagged accounts data.

    INPUTS:
        * company_number

    OUTPUTS:
        * dictionary of filed balance sheet line items
    """
    # Total assets, net assets, share capital, retained earnings and creditors are
    # filed figures. Parse them from the tagged accounts, never proxy them.
    raise NotImplementedError("Tagged accounts parsing is not built yet")


def build_filing_record(company_number = None):
    """
    Collects the registered facts for one company into a single flat row.

    INPUTS:
        * company_number

    OUTPUTS:
        * dictionary of registered facts
    """
    profile = fetch_company_profile(company_number = company_number)
    officers = fetch_officers(company_number = company_number)
    filing_history = fetch_filing_history(company_number = company_number)
    officer_names = [officer.get("name") for officer in officers.get("items", [])]
    registered_address = profile.get("registered_office_address", {})
    return {
        "company_number": company_number,
        "company_name": profile.get("company_name"),
        "registered_address": registered_address.get("address_line_1"),
        "registered_postcode": registered_address.get("postal_code"),
        "incorporation_date": profile.get("date_of_creation"),
        "sic_codes": profile.get("sic_codes", []),
        "officer_names": officer_names,
        "filing_count": filing_history.get("total_count", 0),
    }


def main():
    """Builds the statutory filings table for the resolved company list."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not COMPANIES_FILE.exists():
        print("No resolved company list found, run entity_resolution first")
        return
    company_numbers = pd.read_parquet(COMPANIES_FILE)["company_number"].tolist()
    records = [build_filing_record(company_number = company_number) for company_number in company_numbers]
    filings = pd.DataFrame(records)
    filings.to_parquet(STATUTORY_FILINGS_FILE)
    print(f"Saved statutory filings for {len(filings)} companies")


if __name__ == "__main__":
    main()
