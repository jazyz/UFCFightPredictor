#!/usr/bin/env python3
"""Generate upcoming-fight predictions with the production single model."""

from __future__ import annotations

from utils.production_predictions import (
    generate_single_model_predictions,
    write_prediction_outputs,
)


def main():
    result = generate_single_model_predictions()
    paths = write_prediction_outputs(result)
    predictions = result.predictions

    print("Model loaded successfully!")
    print(f"\n{'=' * 70}")
    print("PREDICTIONS FOR UPCOMING FIGHTS")
    print(f"{'=' * 70}\n")

    for index, row in predictions.iterrows():
        red = row["Red Fighter"]
        blue = row["Blue Fighter"]
        red_prob = row["Probability Win"]
        blue_prob = row["Probability Lose"]
        winner = row["Predicted Winner"]
        result_label = row["Predicted Result"]

        print(f"Fight {index + 1}: {red} vs {blue}")
        print(f"  {red}: {red_prob:.2%} win probability")
        print(f"  {blue}: {blue_prob:.2%} win probability")
        print(f"  Predicted Result: {result_label}")
        print(f"  Predicted Winner: {winner}")
        print()

    print(f"{'=' * 70}")
    print(f"Betting predictions saved to: {paths['betting_predictions']}")
    print(f"Single-model report saved to: {paths['single_model_predictions']}")
    print(f"Metadata saved to: {paths['betting_predictions_metadata']}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
