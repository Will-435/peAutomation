"""
Reads leverage and lender relationships from the Companies House charges register,
the UK equivalent of a US UCC-1 filing. The register is factual, so any error sits
in company matching rather than in the data itself.
"""

from pathlib import Path

import pandas as pd
import requests

COMPANIES_HOUSE_API_KEY = "companies house api key goes here"
COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"
REQUEST_TIMEOUT_SECONDS = 30

DATA_PROCESSED_DIRECTORY = Path("data/processed")
COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
SECURED_CHARGES_FILE = DATA_PROCESSED_DIRECTORY / "secured_charges.parquet"


def fetch_charges(company_number = None):
    """
    Fetches the charges register entries for one company.

    INPUTS:
        * company_number

    OUTPUTS:
        * list of charge dictionaries
    """
    url = f"{COMPANIES_HOUSE_BASE_URL}/company/{company_number}/charges"
    response = requests.get(url, auth = (COMPANIES_HOUSE_API_KEY, ""), timeout = REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get("items", [])


def tabulate_charges(company_number = None, charges = None):
    """
    Flattens raw charge entries into one row per charge.

    INPUTS:
        * company_number
        * charges

    OUTPUTS:
        * list of flat charge dictionaries
    """
    rows = []
    for charge in charges:
        persons_entitled = [person.get("name", "") for person in charge.get("persons_entitled", [])]
        rows.append({
            "company_number": company_number,
            "created_on": charge.get("created_on"),
            "status": charge.get("status"),
            "classification": charge.get("classification", {}).get("description"),
            "persons_entitled": persons_entitled,
            # Free text, classification into asset backed, floating charge, invoice
            # financed or property secured categories is a later pass.
            "description": charge.get("particulars", {}).get("description"),
        })
    return rows


def main():
    """Builds the secured charges table for the resolved company list."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not COMPANIES_FILE.exists():
        print("No resolved company list found, run entity_resolution first")
        return
    company_numbers = pd.read_parquet(COMPANIES_FILE)["company_number"].tolist()
    all_rows = []
    for company_number in company_numbers:
        charges = fetch_charges(company_number = company_number)
        all_rows.extend(tabulate_charges(company_number = company_number, charges = charges))
    charges_table = pd.DataFrame(all_rows)
    charges_table.to_parquet(SECURED_CHARGES_FILE)
    print(f"Saved {len(charges_table)} charges")


if __name__ == "__main__":
    main()
