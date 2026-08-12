"""
Scores default risk with logistic regression on financial ratios, with company text
features as optional extra inputs. Text goes in as features feeding the same model,
never as a standalone credit opinion. A bought bureau score is the benchmark any
in house model has to beat.
"""

from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

RATIO_FEATURE_COLUMNS = ["current_ratio", "gearing", "retained_earnings_to_assets"]
TEXT_FEATURE_COLUMNS = ["report_negative_language_flag", "going_concern_flag"]
LABEL_COLUMN = "defaulted_within_year"
TEST_SET_FRACTION = 0.25
RANDOM_SEED = 42
MAXIMUM_ITERATIONS = 1000

DATA_PROCESSED_DIRECTORY = Path("data/processed")
TRAINING_DATA_FILE = DATA_PROCESSED_DIRECTORY / "credit_training_data.parquet"


def train_and_evaluate(training_data = None, feature_columns = None):
    """
    Trains a logistic model on the given features and returns held out AUC.

    INPUTS:
        * training_data
        * feature_columns

    OUTPUTS:
        * held out area under curve
    """
    features = training_data[feature_columns]
    labels = training_data[LABEL_COLUMN]
    features_train, features_test, labels_train, labels_test = train_test_split(
        features, labels, test_size = TEST_SET_FRACTION, random_state = RANDOM_SEED,
    )
    model = LogisticRegression(max_iter = MAXIMUM_ITERATIONS)
    model.fit(features_train, labels_train)
    predicted_probabilities = model.predict_proba(features_test)[:, 1]
    return roc_auc_score(labels_test, predicted_probabilities)


def compare_text_feature_lift(training_data = None):
    """
    Measures AUC with and without the text features on identical data. If the text
    features do not move the score they get dropped, the literature says text can
    help, not that these particular features do.

    INPUTS:
        * training_data

    OUTPUTS:
        * dictionary with both AUC values and the lift
    """
    ratio_only_auc = train_and_evaluate(
        training_data = training_data,
        feature_columns = RATIO_FEATURE_COLUMNS,
    )
    with_text_auc = train_and_evaluate(
        training_data = training_data,
        feature_columns = RATIO_FEATURE_COLUMNS + TEXT_FEATURE_COLUMNS,
    )
    return {
        "ratio_only_auc": ratio_only_auc,
        "with_text_auc": with_text_auc,
        "text_feature_lift": with_text_auc - ratio_only_auc,
    }


def main():
    """Runs the text feature comparison on the labelled training set."""
    if not TRAINING_DATA_FILE.exists():
        print("No labelled training data found, assemble it before modelling")
        return
    training_data = pd.read_parquet(TRAINING_DATA_FILE)
    comparison = compare_text_feature_lift(training_data = training_data)
    print(f"Ratio only AUC {comparison['ratio_only_auc']:.3f}")
    print(f"With text AUC {comparison['with_text_auc']:.3f}")
    print(f"Text feature lift {comparison['text_feature_lift']:.3f}")


if __name__ == "__main__":
    main()
