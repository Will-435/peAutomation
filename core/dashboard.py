"""
Shows every signal the pipeline holds on one company, on one screen. The dashboard
reads the processed outputs only, it calls no API and recomputes nothing, so what
is displayed is exactly what the pipeline produced.

Signals are grouped by tier, because a retrieved fact and an estimate carry very
different weight and a reader has to be able to tell them apart at a glance.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

DATA_PROCESSED_DIRECTORY = Path("data/processed")
VISUALS_DIRECTORY = Path("visuals")

COMPANIES_FILE = DATA_PROCESSED_DIRECTORY / "resolved_companies.parquet"
TENDER_HISTORY_FILE = DATA_PROCESSED_DIRECTORY / "tender_history.parquet"
STATUTORY_FILINGS_FILE = DATA_PROCESSED_DIRECTORY / "statutory_filings.parquet"
SECURED_CHARGES_FILE = DATA_PROCESSED_DIRECTORY / "secured_charges.parquet"
OWNERSHIP_FILE = DATA_PROCESSED_DIRECTORY / "ownership_structure.parquet"
ACCREDITATIONS_FILE = DATA_PROCESSED_DIRECTORY / "accreditation_status.parquet"
DISTRESS_SCORES_FILE = DATA_PROCESSED_DIRECTORY / "distress_scores.parquet"
CLASSIFICATIONS_FILE = DATA_PROCESSED_DIRECTORY / "industry_classifications.parquet"
VALUATION_DISTRIBUTIONS_FILE = DATA_PROCESSED_DIRECTORY / "valuation_distributions.parquet"
REVENUE_CROSS_CHECK_FILE = DATA_PROCESSED_DIRECTORY / "revenue_cross_checks.parquet"

PLOT_RED = "#c0392b"
PLOT_GREEN = "#27ae60"
PLOT_BLUE = "#2471a3"
FIGURE_WIDTH_INCHES = 7
FIGURE_HEIGHT_INCHES = 3
QUANTILE_COLUMNS = [
    "value_quantile_10",
    "value_quantile_25",
    "value_quantile_50",
    "value_quantile_75",
    "value_quantile_90",
]
QUANTILE_LABELS = ["10th", "25th", "median", "75th", "90th"]
NOT_FOUND_LABEL = "not found on site"
MODULE_NOT_RUN_MESSAGE = "Module has not run yet, no output file"


def load_table(table_file = None):
    """
    Reads one processed output, returning None when the module has not run. A
    missing file is a normal state here, not an error, since modules are run
    independently.

    INPUTS:
        * table_file

    OUTPUTS:
        * dataframe, or None when the file is absent
    """
    if not table_file.exists():
        return None
    return pd.read_parquet(table_file)


def select_company_rows(table = None, company_number = None, company_name = None):
    """
    Pulls the rows for one company from a table, matching on whichever identifier
    that table carries.

    INPUTS:
        * table
        * company_number
        * company_name

    OUTPUTS:
        * dataframe of matching rows, empty when the company is absent
    """
    if table is None:
        return None
    if "company_number" in table.columns:
        return table[table["company_number"] == company_number]
    if "company_name" in table.columns:
        return table[table["company_name"] == company_name]
    return None


def show_table_section(section_title = None, rows = None):
    """
    Renders one section, saying plainly when the module behind it has not run.

    INPUTS:
        * section_title
        * rows

    OUTPUTS:
        * none, the section is written to the page
    """
    st.subheader(section_title)
    if rows is None:
        st.info(MODULE_NOT_RUN_MESSAGE)
        return
    if len(rows) == 0:
        st.warning("Module has run but holds no record for this company")
        return
    st.dataframe(rows, use_container_width = True)


def plot_valuation_range(quantile_values = None, company_name = None):
    """
    Plots the valuation quantile range. The whole range is drawn rather than the
    median alone, because a single bar would imply a precision the method does
    not have.

    INPUTS:
        * quantile_values
        * company_name

    OUTPUTS:
        * matplotlib figure
    """
    figure, axes = plt.subplots(figsize = (FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES))
    axes.plot(QUANTILE_LABELS, quantile_values, color = PLOT_BLUE, marker = "o")
    axes.fill_between(QUANTILE_LABELS, quantile_values, color = PLOT_BLUE, alpha = 0.15)
    axes.set_title(f"Valuation range for {company_name}")
    axes.set_ylabel("Estimated value")
    axes.grid(True, alpha = 0.3)
    return figure


def plot_revenue_cross_check(multiples_estimate = None, headcount_estimate = None, revenue_usable = None):
    """
    Plots the two revenue estimates side by side. The bars are coloured by whether
    the two agree closely enough to be used, so disagreement is visible without
    reading the ratio.

    INPUTS:
        * multiples_estimate
        * headcount_estimate
        * revenue_usable

    OUTPUTS:
        * matplotlib figure
    """
    bar_colour = PLOT_GREEN if revenue_usable else PLOT_RED
    figure, axes = plt.subplots(figsize = (FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES))
    axes.bar(["multiples", "headcount"], [multiples_estimate, headcount_estimate], color = bar_colour)
    axes.set_title("Revenue estimates, cross checked")
    axes.set_ylabel("Estimated revenue")
    axes.grid(True, axis = "y", alpha = 0.3)
    return figure


def show_accreditation_section(accreditation_rows = None):
    """
    Renders accreditations, keeping absence and presence distinct. A not found
    result means the site did not say so, not that the company lacks the
    accreditation, and the two must not read the same.

    INPUTS:
        * accreditation_rows

    OUTPUTS:
        * none, the section is written to the page
    """
    st.subheader("Accreditation status")
    if accreditation_rows is None:
        st.info(MODULE_NOT_RUN_MESSAGE)
        return
    if len(accreditation_rows) == 0:
        st.warning("Module has run but holds no record for this company")
        return
    accreditation_row = accreditation_rows.iloc[0]
    status_columns = [column for column in accreditation_rows.columns if column.endswith("_status")]
    for status_column in status_columns:
        accreditation_name = status_column.replace("_status", "").replace("_", " ")
        status_value = accreditation_row[status_column]
        citation_value = accreditation_row.get(status_column.replace("_status", "_citation"))
        if status_value == NOT_FOUND_LABEL:
            st.write(f"{accreditation_name}: not found on the site, which is not proof it is not held")
        else:
            st.write(f"{accreditation_name}: {status_value}")
            if citation_value:
                st.caption(f"Cited text: {citation_value}")


def main():
    """Renders the dashboard for one selected company."""
    st.set_page_config(page_title = "PE screening dashboard", layout = "wide")
    st.title("Company screening dashboard")
    VISUALS_DIRECTORY.mkdir(parents = True, exist_ok = True)

    companies = load_table(table_file = COMPANIES_FILE)
    if companies is None:
        st.error("No resolved company list found, run entity resolution first")
        return

    company_names = companies["company_name"].tolist()
    selected_name = st.sidebar.selectbox("Company", company_names)
    selected_row = companies[companies["company_name"] == selected_name].iloc[0]
    selected_number = selected_row.get("company_number")
    st.caption(f"Company number {selected_number}")

    st.header("Tier 1, retrieved facts")
    st.caption("Read directly from public registers and company websites, no estimation involved")
    show_table_section(
        section_title = "Statutory filings",
        rows = select_company_rows(
            table = load_table(table_file = STATUTORY_FILINGS_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )
    show_table_section(
        section_title = "Tender history",
        rows = select_company_rows(
            table = load_table(table_file = TENDER_HISTORY_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )
    show_table_section(
        section_title = "Secured charges",
        rows = select_company_rows(
            table = load_table(table_file = SECURED_CHARGES_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )
    show_table_section(
        section_title = "Ownership structure",
        rows = select_company_rows(
            table = load_table(table_file = OWNERSHIP_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )
    show_accreditation_section(
        accreditation_rows = select_company_rows(
            table = load_table(table_file = ACCREDITATIONS_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )

    st.header("Tier 2, modelled with a measured error band")
    st.caption("Derived from retrieved facts, each carries its own error rate")
    show_table_section(
        section_title = "Distress score",
        rows = select_company_rows(
            table = load_table(table_file = DISTRESS_SCORES_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )
    show_table_section(
        section_title = "Industry classification",
        rows = select_company_rows(
            table = load_table(table_file = CLASSIFICATIONS_FILE),
            company_number = selected_number,
            company_name = selected_name,
        ),
    )

    st.header("Tier 3, ranges only")
    st.caption("Wide and unvalidated on small private companies, read as a range and never as a figure")

    # Valuation range, drawn as the full quantile spread.
    valuation_rows = select_company_rows(
        table = load_table(table_file = VALUATION_DISTRIBUTIONS_FILE),
        company_number = selected_number,
        company_name = selected_name,
    )
    st.subheader("Valuation range")
    if valuation_rows is None:
        st.info(MODULE_NOT_RUN_MESSAGE)
    elif len(valuation_rows) == 0:
        st.warning("Module has run but holds no record for this company")
    else:
        valuation_row = valuation_rows.iloc[0]
        quantile_values = [valuation_row[column] for column in QUANTILE_COLUMNS]
        st.pyplot(plot_valuation_range(quantile_values = quantile_values, company_name = selected_name))
        st.caption(f"Based on {valuation_row['peer_count']} peers at code length {valuation_row['code_length_used']}")

    # Revenue cross check, drawn as the two estimates against each other.
    revenue_rows = select_company_rows(
        table = load_table(table_file = REVENUE_CROSS_CHECK_FILE),
        company_number = selected_number,
        company_name = selected_name,
    )
    st.subheader("Revenue cross check")
    if revenue_rows is None:
        st.info(MODULE_NOT_RUN_MESSAGE)
    elif len(revenue_rows) == 0:
        st.warning("Module has run but holds no record for this company")
    else:
        revenue_row = revenue_rows.iloc[0]
        st.pyplot(plot_revenue_cross_check(
            multiples_estimate = revenue_row["multiples_revenue_estimate"],
            headcount_estimate = revenue_row["headcount_revenue_estimate"],
            revenue_usable = revenue_row["revenue_usable"],
        ))
        if not revenue_row["revenue_usable"]:
            st.error(
                f"The two estimates disagree by {revenue_row['disagreement_ratio']:.1f} times. "
                "Revenue is unusable for this company, do not pick one of the two."
            )


if __name__ == "__main__":
    main()
