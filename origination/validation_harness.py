"""
Measures real error rates for every estimation method against companies that file
full accounts including the profit and loss. Ground truth comes from filed accounts
only, never from a model. Full filers run larger than the small company targets, so
results are closer than published figures but still indicative, and reported as such.
"""

from pathlib import Path

import pandas as pd

ERROR_QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]
INTERVAL_COVERAGE_TARGET = 0.80

DATA_PROCESSED_DIRECTORY = Path("data/processed")
GROUND_TRUTH_FILE = DATA_PROCESSED_DIRECTORY / "ground_truth_accounts.parquet"
VALIDATION_RESULTS_FILE = DATA_PROCESSED_DIRECTORY / "validation_results.parquet"

SAMPLE_LIMITATION_NOTE = (
    "Full filers are larger than the small company targets, "
    "treat this calibration as indicative rather than exact"
)


def error_statistics(estimated_values = None, filed_values = None):
    """
    Computes the error distribution of one method against filed truth. Dispersion
    matters as much as the mean, a method can be right on average and useless.

    INPUTS:
        * estimated_values
        * filed_values

    OUTPUTS:
        * dictionary of mean error, dispersion, worst case and bias direction
    """
    errors = estimated_values - filed_values
    statistics = {
        "mean_error": errors.mean(),
        "error_standard_deviation": errors.std(),
        "worst_case_error": errors.abs().max(),
        "bias_direction": "overestimates" if errors.mean() > 0 else "underestimates",
    }
    for quantile in ERROR_QUANTILES:
        statistics[f"error_quantile_{int(quantile * 100)}"] = errors.quantile(quantile)
    return statistics


def interval_calibration(lower_bounds = None, upper_bounds = None, filed_values = None):
    """
    Checks whether stated prediction intervals achieve their stated coverage. An
    eighty percent interval should contain the filed truth about eighty percent
    of the time, otherwise the stated uncertainty is fiction.

    INPUTS:
        * lower_bounds
        * upper_bounds
        * filed_values

    OUTPUTS:
        * dictionary with observed coverage and a calibrated flag
    """
    contained = (filed_values >= lower_bounds) & (filed_values <= upper_bounds)
    observed_coverage = contained.mean()
    return {
        "observed_coverage": observed_coverage,
        "target_coverage": INTERVAL_COVERAGE_TARGET,
        "calibrated": observed_coverage >= INTERVAL_COVERAGE_TARGET,
    }


def validate_method(method_name = None, estimates_table = None):
    """
    Runs the full validation for one estimation method. The estimates table must
    have been produced blind, using only externally available inputs.

    INPUTS:
        * method_name
        * estimates_table

    OUTPUTS:
        * dictionary of error statistics and calibration for the method
    """
    statistics = error_statistics(
        estimated_values = estimates_table["estimated_value"],
        filed_values = estimates_table["filed_value"],
    )
    calibration = interval_calibration(
        lower_bounds = estimates_table["interval_lower"],
        upper_bounds = estimates_table["interval_upper"],
        filed_values = estimates_table["filed_value"],
    )
    result = {"method_name": method_name, "sample_size": len(estimates_table)}
    result.update(statistics)
    result.update(calibration)
    return result


def main():
    """Validates every method with a blind estimates table against filed truth."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not GROUND_TRUTH_FILE.exists():
        print("No ground truth sample found, pull full filing companies first")
        return
    print(SAMPLE_LIMITATION_NOTE)


if __name__ == "__main__":
    main()
