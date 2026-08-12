"""
Estimates value as the target scaling variable times peer multiples. The peer set
gives a distribution, not a number, so the full distribution is carried forward and
only summarised at the final output. Peers come from three digit classification,
widening only when the peer count is too low.
"""

from pathlib import Path

import pandas as pd

FINEST_CODE_LENGTH = 3
MINIMUM_PEER_COUNT = 8
DISTRIBUTION_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]

DATA_PROCESSED_DIRECTORY = Path("data/processed")
PEER_MULTIPLES_FILE = DATA_PROCESSED_DIRECTORY / "peer_multiples.parquet"
VALUATION_DISTRIBUTIONS_FILE = DATA_PROCESSED_DIRECTORY / "valuation_distributions.parquet"


def select_peer_multiples(target_industry_code = None, peer_table = None):
    """
    Selects peer multiples at the finest classification granularity that still
    gives enough peers, widening one digit at a time.

    INPUTS:
        * target_industry_code
        * peer_table

    OUTPUTS:
        * series of peer multiples
        * code length actually used
    """
    for code_length in range(FINEST_CODE_LENGTH, 0, -1):
        code_prefix = target_industry_code[:code_length]
        matching_peers = peer_table[peer_table["industry_code"].str.startswith(code_prefix)]
        if len(matching_peers) >= MINIMUM_PEER_COUNT:
            return matching_peers["multiple"], code_length
    return peer_table["multiple"], 0


def estimate_value_distribution(scaling_value = None, peer_multiples = None):
    """
    Applies every peer multiple to the scaling variable. The result is the whole
    distribution, collapsing to a median here would throw the error band away.

    INPUTS:
        * scaling_value
        * peer_multiples

    OUTPUTS:
        * series of estimated values, one per peer
    """
    return scaling_value * peer_multiples


def summarise_distribution(company_number = None, value_distribution = None, code_length_used = None):
    """
    Summarises a value distribution into quantiles for the final output only.

    INPUTS:
        * company_number
        * value_distribution
        * code_length_used

    OUTPUTS:
        * dictionary of quantile values and peer count
    """
    summary = {
        "company_number": company_number,
        "peer_count": len(value_distribution),
        "code_length_used": code_length_used,
    }
    for quantile in DISTRIBUTION_QUANTILES:
        summary[f"value_quantile_{int(quantile * 100)}"] = value_distribution.quantile(quantile)
    return summary


def main():
    """Builds valuation distributions for every company with a peer table."""
    DATA_PROCESSED_DIRECTORY.mkdir(parents = True, exist_ok = True)
    if not PEER_MULTIPLES_FILE.exists():
        print("No peer multiples table found, assemble it before estimating")
        return
    print("Peer table found, wire targets in once scaling variables are available")


if __name__ == "__main__":
    main()
