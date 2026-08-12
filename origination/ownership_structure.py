"""
Resolves group structure from the Persons with Significant Control register. A
subsidiary of a large group is usually a poor prospect because procurement is
handled centrally, so each company gets a group membership flag before scoring.
"""

from pathlib import Path

import pandas as pd
import requests

COMPANIES_HOUSE_API_KEY = "companies house api key goes here"
COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"
REQUEST_TIMEOUT_SECONDS = 30
CORPORATE_CONTROLLER_KIND = "corporate-entity-person-with-significant-control"

DATA_PROCESSED_DIRECTORY = Path("data/processed")
COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
OWNERSHIP_FILE = DATA_PROCESSED_DIRECTORY / "ownership_structure.parquet"


def fetch_persons_with_significant_control(company_number = None):
    """
    Fetches the PSC register entries for one company.

    INPUTS:
        * company_number

    OUTPUTS:
        * list of controller dictionaries
    """
    url = f"{COMPANIES_HOUSE_BASE_URL}/company/{company_number}/persons-with-significant-control"
    response = requests.get(url, auth = (COMPANIES_HOUSE_API_KEY, ""), timeout = REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get("items", [])


def build_ownership_record(company_number = None):
    """
    Flags whether a company sits inside a larger group.

    INPUTS:
        * company_number

    OUTPUTS:
        * dictionary with corporate controllers and a group membership flag
    """
    controllers = fetch_persons_with_significant_control(company_number = company_number)
    corporate_controllers = [
        controller.get("name") for controller in controllers
        if controller.get("kind") == CORPORATE_CONTROLLER_KIND
    ]
    # Where the register is silent or stale, inference from shared addresses or
    # common directors is a later pass, and always a flag for human confirmation
    # rather than a stored fact.
    return {
        "company_number": company_number,
        "corporate_controllers": corporate_controllers,
        "part_of_group": len(corporate_controllers) > 0,
    }


def main():
    """Builds the ownership table for the resolved company list."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not COMPANIES_FILE.exists():
        print("No resolved company list found, run entity_resolution first")
        return
    company_numbers = pd.read_parquet(COMPANIES_FILE)["company_number"].tolist()
    records = [build_ownership_record(company_number = company_number) for company_number in company_numbers]
    ownership = pd.DataFrame(records)
    ownership.to_parquet(OWNERSHIP_FILE)
    print(f"Saved ownership structure for {len(ownership)} companies")


if __name__ == "__main__":
    main()
