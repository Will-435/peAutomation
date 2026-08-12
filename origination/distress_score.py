"""
Ranks companies by financial distress with the Altman Z double prime formula, the
variant validated on private companies. The EBIT term needs a filed profit and loss
account, which most small UK companies withhold. Where EBIT is missing the reduced
three term score is used, a guessed EBIT is never substituted.
"""

from pathlib import Path

import pandas as pd

WORKING_CAPITAL_COEFFICIENT = 6.56
RETAINED_EARNINGS_COEFFICIENT = 3.26
EBIT_COEFFICIENT = 6.72
EQUITY_COEFFICIENT = 1.05

FULL_SCORE_LABEL = "full"
REDUCED_SCORE_LABEL = "reduced_no_ebit"

DATA_PROCESSED_DIRECTORY = Path("data/processed")
BALANCE_SHEETS_FILE = DATA_PROCESSED_DIRECTORY / "balance_sheets.parquet"
DISTRESS_SCORES_FILE = DATA_PROCESSED_DIRECTORY / "distress_scores.parquet"


def full_distress_score(working_capital = None, retained_earnings = None, ebit = None,
                        book_value_of_equity = None, total_liabilities = None, total_assets = None):
    """
    Computes the full four term Z double prime score from filed figures.

    INPUTS:
        * working_capital
        * retained_earnings
        * ebit
        * book_value_of_equity
        * total_liabilities
        * total_assets

    OUTPUTS:
        * score, or None when a denominator is missing or zero
    """
    if not total_assets or not total_liabilities:
        return None
    return (
        WORKING_CAPITAL_COEFFICIENT * (working_capital / total_assets)
        + RETAINED_EARNINGS_COEFFICIENT * (retained_earnings / total_assets)
        + EBIT_COEFFICIENT * (ebit / total_assets)
        + EQUITY_COEFFICIENT * (book_value_of_equity / total_liabilities)
    )


def reduced_distress_score(working_capital = None, retained_earnings = None,
                           book_value_of_equity = None, total_liabilities = None, total_assets = None):
    """
    Computes the three term score for companies with no filed profit and loss.
    Validated separately from the full score, the two are not comparable.

    INPUTS:
        * working_capital
        * retained_earnings
        * book_value_of_equity
        * total_liabilities
        * total_assets

    OUTPUTS:
        * score, or None when a denominator is missing or zero
    """
    if not total_assets or not total_liabilities:
        return None
    return (
        WORKING_CAPITAL_COEFFICIENT * (working_capital / total_assets)
        + RETAINED_EARNINGS_COEFFICIENT * (retained_earnings / total_assets)
        + EQUITY_COEFFICIENT * (book_value_of_equity / total_liabilities)
    )


def score_company(balance_sheet_row = None):
    """
    Scores one company, choosing the full or reduced form by EBIT availability.
    Cut off thresholds need recalibration on UK data before they can be trusted,
    so the output is the raw score and its form, not a distress category.

    INPUTS:
        * balance_sheet_row

    OUTPUTS:
        * dictionary with company number, score and score form
    """
    ebit = balance_sheet_row.get("ebit")
    if ebit is not None:
        score = full_distress_score(
            working_capital = balance_sheet_row.get("working_capital"),
            retained_earnings = balance_sheet_row.get("retained_earnings"),
            ebit = ebit,
            book_value_of_equity = balance_sheet_row.get("book_value_of_equity"),
            total_liabilities = balance_sheet_row.get("total_liabilities"),
            total_assets = balance_sheet_row.get("total_assets"),
        )
        score_form = FULL_SCORE_LABEL
    else:
        score = reduced_distress_score(
            working_capital = balance_sheet_row.get("working_capital"),
            retained_earnings = balance_sheet_row.get("retained_earnings"),
            book_value_of_equity = balance_sheet_row.get("book_value_of_equity"),
            total_liabilities = balance_sheet_row.get("total_liabilities"),
            total_assets = balance_sheet_row.get("total_assets"),
        )
        score_form = REDUCED_SCORE_LABEL
    return {
        "company_number": balance_sheet_row.get("company_number"),
        "distress_score": score,
        "score_form": score_form,
    }


def main():
    """Scores every company with a filed balance sheet."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not BALANCE_SHEETS_FILE.exists():
        print("No balance sheet data found, run statutory_filings first")
        return
    balance_sheets = pd.read_parquet(BALANCE_SHEETS_FILE)
    scores = [score_company(balance_sheet_row = row) for row in balance_sheets.to_dict("records")]
    scores_table = pd.DataFrame(scores)
    scores_table.to_parquet(DISTRESS_SCORES_FILE)
    print(f"Saved distress scores for {len(scores_table)} companies")


if __name__ == "__main__":
    main()
