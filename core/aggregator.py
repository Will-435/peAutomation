"""
Collapses the raw records into one row per company per decision date. Point in time
correctness is enforced here in SQL rather than in pandas, using a window function
to take the most recent fact dated on or before the decision date. A fact dated
after its decision date is a leak, and once written it looks like ordinary data,
so the guard runs before anything is saved.
"""

from pathlib import Path

import duckdb
import pandas as pd

MOST_RECENT_ROW = 1
FACT_TABLE_NAMES = ["filings", "tenders", "charges", "ownership"]

DATA_RAW_DIRECTORY = Path("data/raw")
DATA_PROCESSED_DIRECTORY = Path("data/processed")
AGGREGATED_FILE = DATA_PROCESSED_DIRECTORY / "company_decision_rows.parquet"


def open_connection():
    """Opens an in memory DuckDB connection for the aggregation run."""
    return duckdb.connect()


def register_fact_table(connection = None, table_name = None, fact_frame = None):
    """
    Registers one fact table on the connection so SQL can reach it.

    INPUTS:
        * connection
        * table_name
        * fact_frame

    OUTPUTS:
        * none, the table is registered on the connection
    """
    connection.register(table_name, fact_frame)


def as_of_query(table_name = None):
    """
    Builds the as of query for one fact table. Facts later than the decision date
    are filtered out first, then the window function ranks what remains by date so
    only the most recent surviving row per company is kept.

    INPUTS:
        * table_name

    OUTPUTS:
        * SQL query string
    """
    return f"""
        SELECT company_number, decision_date, fact_date, *
        FROM (
            SELECT
                facts.*,
                decisions.decision_date,
                ROW_NUMBER() OVER (
                    PARTITION BY facts.company_number, decisions.decision_date
                    ORDER BY facts.fact_date DESC
                ) AS row_rank
            FROM {table_name} AS facts
            JOIN decisions
              ON facts.company_number = decisions.company_number
            WHERE facts.fact_date <= decisions.decision_date
        )
        WHERE row_rank = {MOST_RECENT_ROW}
    """


def assert_no_future_facts(aggregated_frame = None):
    """
    Checks that no retained fact is dated after its decision date. This is the one
    guard that has to run every time, since a leaked future fact produces a model
    that scores well and cannot be trusted.

    INPUTS:
        * aggregated_frame

    OUTPUTS:
        * none, raises when a leak is found
    """
    leaked_rows = aggregated_frame[aggregated_frame["fact_date"] > aggregated_frame["decision_date"]]
    if len(leaked_rows) > 0:
        raise ValueError(f"Point in time leak, {len(leaked_rows)} facts dated after their decision date")


def aggregate_as_of(connection = None, decisions_frame = None, fact_frames = None):
    """
    Runs the as of join for every registered fact table and joins the results into
    one row per company per decision date.

    INPUTS:
        * connection
        * decisions_frame
        * fact_frames

    OUTPUTS:
        * aggregated dataframe, one row per company per decision date
    """
    register_fact_table(connection = connection, table_name = "decisions", fact_frame = decisions_frame)
    aggregated_frame = decisions_frame
    for table_name in FACT_TABLE_NAMES:
        if table_name not in fact_frames:
            continue
        register_fact_table(
            connection = connection,
            table_name = table_name,
            fact_frame = fact_frames[table_name],
        )
        as_of_frame = connection.execute(as_of_query(table_name = table_name)).fetch_df()
        assert_no_future_facts(aggregated_frame = as_of_frame)
        aggregated_frame = aggregated_frame.merge(
            as_of_frame,
            on = ["company_number", "decision_date"],
            how = "left",
            suffixes = ("", f"_{table_name}"),
        )
    return aggregated_frame


def main():
    """Aggregates the registered fact tables into the decision row table."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not DATA_RAW_DIRECTORY.exists():
        print("No raw data found, run surfer first")
        return
    print("Raw data found, pass the decision dates and fact tables to aggregate_as_of")


if __name__ == "__main__":
    main()
