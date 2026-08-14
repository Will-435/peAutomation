"""
Runs the outbound API calls that feed the pipeline. Every response is written to
data/raw exactly as returned, so parsing can be rerun later without calling the
source again. Failed requests are recorded rather than dropped, because a silent
gap in the raw data is invisible once aggregation has run over it.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from config import COMPANIES_HOUSE_API_KEY

COMPANIES_HOUSE_BASE_URL = "https://api.company-information.service.gov.uk"
CONTRACTS_FINDER_SEARCH_URL = "https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json"

REQUEST_TIMEOUT_SECONDS = 30
SECONDS_BETWEEN_REQUESTS = 0.5
MAXIMUM_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2
RESULTS_PER_PAGE = 100
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

DATA_RAW_DIRECTORY = Path("data/raw")
FAILED_REQUESTS_FILE = DATA_RAW_DIRECTORY / "failed_requests.log"


def current_timestamp():
    """Returns a UTC timestamp string used to name raw response files."""
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)


def save_raw_response(source_name = None, record_key = None, payload = None):
    """
    Writes one response to data/raw under its source and a timestamp. Keeping the
    response as given means a parsing change can be rerun against old pulls, and
    two pulls of the same company can be compared.

    INPUTS:
        * source_name
        * record_key
        * payload

    OUTPUTS:
        * path of the written file
    """
    source_directory = DATA_RAW_DIRECTORY / source_name
    source_directory.mkdir(parents = True, exist_ok = True)
    safe_key = str(record_key).lower().replace(" ", "_").replace("/", "_")
    raw_file = source_directory / f"{safe_key}_{current_timestamp()}.json"
    raw_file.write_text(json.dumps(payload))
    return raw_file


def record_failure(source_name = None, record_key = None, reason = None):
    """
    Appends a failed request to the failure log. A dropped request leaves no trace
    in data/raw, so the gap has to be written down at the point it happens.

    INPUTS:
        * source_name
        * record_key
        * reason

    OUTPUTS:
        * none, the failure log is appended to
    """
    DATA_RAW_DIRECTORY.mkdir(parents = True, exist_ok = True)
    with open(FAILED_REQUESTS_FILE, "a") as failure_log:
        failure_log.write(f"{current_timestamp()} {source_name} {record_key} {reason}\n")


def fetch_with_retry(url = None, auth = None, json_payload = None):
    """
    Calls one endpoint, retrying on failure with a widening pause. Returns None
    once the attempts are used up, so the caller can log the gap and carry on
    rather than losing the whole run to one bad response.

    INPUTS:
        * url
        * auth
        * json_payload

    OUTPUTS:
        * decoded json dictionary, or None when every attempt failed
        * reason string when every attempt failed, otherwise None
    """
    last_reason = None
    for attempt_number in range(MAXIMUM_ATTEMPTS):
        try:
            if json_payload is None:
                response = requests.get(url, auth = auth, timeout = REQUEST_TIMEOUT_SECONDS)
            else:
                response = requests.post(url, json = json_payload, timeout = REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json(), None
        except requests.RequestException as request_error:
            last_reason = str(request_error)
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt_number + 1))
    return None, last_reason


def surf_companies_house(company_number = None, endpoint_path = ""):
    """
    Pulls one Companies House endpoint for one company and saves the response.

    INPUTS:
        * company_number
        * endpoint_path

    OUTPUTS:
        * decoded json dictionary, or None when the request failed
    """
    url = f"{COMPANIES_HOUSE_BASE_URL}/company/{company_number}{endpoint_path}"
    payload, reason = fetch_with_retry(url = url, auth = (COMPANIES_HOUSE_API_KEY, ""))
    source_name = "companies_house" + endpoint_path.replace("/", "_")
    if payload is None:
        record_failure(source_name = source_name, record_key = company_number, reason = reason)
        return None
    save_raw_response(source_name = source_name, record_key = company_number, payload = payload)
    return payload


def surf_contracts_finder(company_name = None):
    """
    Searches Contracts Finder for one company and saves the notice list.

    INPUTS:
        * company_name

    OUTPUTS:
        * list of notice dictionaries, or None when the request failed
    """
    search_payload = {"searchCriteria": {"keyword": company_name}, "size": RESULTS_PER_PAGE}
    payload, reason = fetch_with_retry(url = CONTRACTS_FINDER_SEARCH_URL, json_payload = search_payload)
    if payload is None:
        record_failure(source_name = "contracts_finder", record_key = company_name, reason = reason)
        return None
    save_raw_response(source_name = "contracts_finder", record_key = company_name, payload = payload)
    return payload.get("noticeList", [])


def surf_all_sources(company_number = None, company_name = None):
    """
    Runs every configured source for one company, pausing between calls so a large
    run is not blocked partway through.

    INPUTS:
        * company_number
        * company_name

    OUTPUTS:
        * dictionary of source name to response
    """
    collected = {}
    collected["profile"] = surf_companies_house(company_number = company_number)
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    collected["officers"] = surf_companies_house(company_number = company_number, endpoint_path = "/officers")
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    collected["charges"] = surf_companies_house(company_number = company_number, endpoint_path = "/charges")
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    collected["tenders"] = surf_contracts_finder(company_name = company_name)
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    return collected


def main():
    """Runs every source for a small worked example."""
    DATA_RAW_DIRECTORY.mkdir(parents = True, exist_ok = True)
    print("Pass a company number and name to surf_all_sources to start a pull")


if __name__ == "__main__":
    main()
