"""
Cross checks revenue as headcount times an industry revenue per employee benchmark.
Productivity dispersion within an industry alone gives roughly two times errors, so
this is a sanity check on the multiples estimate, never a standalone estimator.
Headcount comes from filed accounts, the most reliable source available.
"""

from pathlib import Path

import pandas as pd

# Estimates disagreeing by more than this ratio mark revenue unusable for that
# company, picking one of the two would hide the disagreement.
DISAGREEMENT_RATIO_LIMIT = 2.0

DATA_PROCESSED_DIRECTORY = Path("data/processed")
HEADCOUNT_FILE = DATA_PROCESSED_DIRECTORY / "filed_headcounts.parquet"
BENCHMARKS_FILE = DATA_PROCESSED_DIRECTORY / "revenue_per_employee_benchmarks.parquet"
REVENUE_CROSS_CHECK_FILE = DATA_PROCESSED_DIRECTORY / "revenue_cross_checks.parquet"


def estimate_revenue(headcount = None, revenue_per_employee = None):
    """
    Multiplies filed headcount by the sector benchmark.

    INPUTS:
        * headcount
        * revenue_per_employee

    OUTPUTS:
        * revenue estimate, or None when either input is missing
    """
    if headcount is None or revenue_per_employee is None:
        return None
    return headcount * revenue_per_employee


def cross_check_estimates(multiples_estimate = None, headcount_estimate = None):
    """
    Compares the two revenue estimates and flags whether revenue is usable.

    INPUTS:
        * multiples_estimate
        * headcount_estimate

    OUTPUTS:
        * dictionary with the disagreement ratio and a usable flag
    """
    if not multiples_estimate or not headcount_estimate:
        return {"disagreement_ratio": None, "revenue_usable": False}
    larger_estimate = max(multiples_estimate, headcount_estimate)
    smaller_estimate = min(multiples_estimate, headcount_estimate)
    disagreement_ratio = larger_estimate / smaller_estimate
    return {
        "disagreement_ratio": disagreement_ratio,
        "revenue_usable": disagreement_ratio <= DISAGREEMENT_RATIO_LIMIT,
    }


def build_cross_check_record(company_row = None, benchmarks = None):
    """
    Runs the headcount estimate and cross check for one company.

    INPUTS:
        * company_row
        * benchmarks

    OUTPUTS:
        * dictionary with both estimates and the usable flag
    """
    sector_benchmarks = benchmarks[benchmarks["industry_code"] == company_row["industry_code"]]
    revenue_per_employee = None
    if len(sector_benchmarks) > 0:
        revenue_per_employee = sector_benchmarks["revenue_per_employee"].iloc[0]
    headcount_estimate = estimate_revenue(
        headcount = company_row.get("filed_headcount"),
        revenue_per_employee = revenue_per_employee,
    )
    check = cross_check_estimates(
        multiples_estimate = company_row.get("multiples_revenue_estimate"),
        headcount_estimate = headcount_estimate,
    )
    return {
        "company_number": company_row.get("company_number"),
        "headcount_revenue_estimate": headcount_estimate,
        "multiples_revenue_estimate": company_row.get("multiples_revenue_estimate"),
        "disagreement_ratio": check["disagreement_ratio"],
        "revenue_usable": check["revenue_usable"],
    }


def main():
    """Cross checks revenue estimates for every company with a filed headcount."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not HEADCOUNT_FILE.exists() or not BENCHMARKS_FILE.exists():
        print("Headcount or benchmark data missing, assemble both before cross checking")
        return
    headcounts = pd.read_parquet(HEADCOUNT_FILE)
    benchmarks = pd.read_parquet(BENCHMARKS_FILE)
    records = [
        build_cross_check_record(company_row = company_row, benchmarks = benchmarks)
        for company_row in headcounts.to_dict("records")
    ]
    cross_checks = pd.DataFrame(records)
    cross_checks.to_parquet(REVENUE_CROSS_CHECK_FILE)
    print(f"Saved revenue cross checks for {len(cross_checks)} companies")


if __name__ == "__main__":
    main()
