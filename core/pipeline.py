"""
Runs the pipeline modules in dependency order. A module whose input is missing is
skipped and recorded rather than called, so one absent input does not stop the
modules that do not depend on it from being attempted.

Order follows the input dependencies rather than the tier numbering alone. Entity
resolution runs first because every later module keys off the resolved company
list, and the candidate list runs before that because resolution has nothing to
resolve without it.

The required inputs live here rather than inside each module. Modules return early
with a message when run by hand, which reads fine on its own but cannot be told
apart from real work by a caller, so the orchestrator checks the inputs itself.
"""

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

DATA_RAW_DIRECTORY = Path("data/raw")
DATA_PROCESSED_DIRECTORY = Path("data/processed")

CANDIDATE_LIST_FILE = DATA_RAW_DIRECTORY / "candidate_list.parquet"
RESOLVED_COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
BALANCE_SHEETS_FILE = DATA_PROCESSED_DIRECTORY / "balance_sheets.parquet"
LABELLED_INDUSTRY_FILE = DATA_PROCESSED_DIRECTORY / "labelled_industry_data.parquet"
CREDIT_TRAINING_FILE = DATA_PROCESSED_DIRECTORY / "credit_training_data.parquet"
PEER_MULTIPLES_FILE = DATA_PROCESSED_DIRECTORY / "peer_multiples.parquet"
FILED_HEADCOUNTS_FILE = DATA_PROCESSED_DIRECTORY / "filed_headcounts.parquet"
REVENUE_BENCHMARKS_FILE = DATA_PROCESSED_DIRECTORY / "revenue_per_employee_benchmarks.parquet"
GROUND_TRUTH_FILE = DATA_PROCESSED_DIRECTORY / "ground_truth_accounts.parquet"

# Module name to the inputs it cannot run without, in dependency order. An empty
# list means the module is an entry point and fetches its own data.
MODULE_REQUIRED_INPUTS = [
    ("origination.candidate_list", []),
    ("origination.entity_resolution", [CANDIDATE_LIST_FILE]),
    ("origination.tender_history", [RESOLVED_COMPANIES_FILE]),
    ("origination.statutory_filings", [RESOLVED_COMPANIES_FILE]),
    ("origination.secured_debt", [RESOLVED_COMPANIES_FILE]),
    ("origination.ownership_structure", [RESOLVED_COMPANIES_FILE]),
    ("origination.accreditation_status", [RESOLVED_COMPANIES_FILE]),
    ("origination.distress_score", [BALANCE_SHEETS_FILE]),
    ("origination.industry_classification", [LABELLED_INDUSTRY_FILE]),
    ("origination.sme_credit_scoring", [CREDIT_TRAINING_FILE]),
    ("origination.valuation_multiples", [PEER_MULTIPLES_FILE]),
    ("origination.revenue_from_headcount", [FILED_HEADCOUNTS_FILE, REVENUE_BENCHMARKS_FILE]),
    ("origination.validation_harness", [GROUND_TRUTH_FILE]),
]

RAN_OUTCOME = "ran"
SKIPPED_OUTCOME = "skipped"
FAILED_OUTCOME = "failed"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

RUN_SUMMARY_FILE = DATA_PROCESSED_DIRECTORY / "pipeline_run_summary.json"


def missing_inputs(required_inputs = None):
    """
    Returns the required inputs that are not on disk.

    INPUTS:
        * required_inputs

    OUTPUTS:
        * list of missing input paths as strings
    """
    return [str(input_file) for input_file in required_inputs if not input_file.exists()]


def run_module(module_name = None, required_inputs = None):
    """
    Runs one module once its inputs are present. A missing input is a skip and is
    reported with the file that was absent, a genuine error is a failure. The two
    are kept apart because a skip is expected while the pipeline is part built,
    whereas a failure needs looking at.

    INPUTS:
        * module_name
        * required_inputs

    OUTPUTS:
        * dictionary with the module name, outcome and any reason
    """
    absent_inputs = missing_inputs(required_inputs = required_inputs)
    if absent_inputs:
        return {
            "module": module_name,
            "outcome": SKIPPED_OUTCOME,
            "reason": f"missing input {', '.join(absent_inputs)}",
        }
    try:
        module = importlib.import_module(module_name)
    except ImportError as import_error:
        return {"module": module_name, "outcome": FAILED_OUTCOME, "reason": str(import_error)}
    try:
        module.main()
        return {"module": module_name, "outcome": RAN_OUTCOME, "reason": None}
    except NotImplementedError as not_built:
        return {"module": module_name, "outcome": SKIPPED_OUTCOME, "reason": f"not built, {not_built}"}
    except Exception as run_error:
        return {"module": module_name, "outcome": FAILED_OUTCOME, "reason": str(run_error)}


def write_run_summary(module_results = None):
    """
    Writes what ran, what was skipped and why. Without this a thin set of outputs
    looks the same whether a module was skipped or ran and produced nothing.

    INPUTS:
        * module_results

    OUTPUTS:
        * path of the written summary
    """
    summary = {
        "run_at": datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT),
        "ran": [result["module"] for result in module_results if result["outcome"] == RAN_OUTCOME],
        "skipped": [result for result in module_results if result["outcome"] == SKIPPED_OUTCOME],
        "failed": [result for result in module_results if result["outcome"] == FAILED_OUTCOME],
    }
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    RUN_SUMMARY_FILE.write_text(json.dumps(summary, indent = 2))
    return RUN_SUMMARY_FILE


def run_pipeline(module_plan = MODULE_REQUIRED_INPUTS):
    """
    Runs every module in dependency order and collects the outcomes. Each module
    is checked against the inputs present at the time it is reached, so a module
    earlier in the run can unblock a later one within the same run.

    INPUTS:
        * module_plan

    OUTPUTS:
        * list of outcome dictionaries
    """
    module_results = []
    for module_name, required_inputs in module_plan:
        print(f"Running {module_name}")
        result = run_module(module_name = module_name, required_inputs = required_inputs)
        print(f"  {result['outcome']}" + (f", {result['reason']}" if result["reason"] else ""))
        module_results.append(result)
    return module_results


def main():
    """Runs the full pipeline and writes the run summary."""
    module_results = run_pipeline()
    write_run_summary(module_results = module_results)
    ran_count = sum(1 for result in module_results if result["outcome"] == RAN_OUTCOME)
    skipped_count = sum(1 for result in module_results if result["outcome"] == SKIPPED_OUTCOME)
    failed_count = sum(1 for result in module_results if result["outcome"] == FAILED_OUTCOME)
    print(f"Ran {ran_count}, skipped {skipped_count}, failed {failed_count}")
    print(f"Summary written to {RUN_SUMMARY_FILE}")


if __name__ == "__main__":
    main()
