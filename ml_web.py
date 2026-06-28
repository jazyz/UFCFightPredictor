from utils.production_predictions import (
    generate_single_model_predictions,
    write_prediction_outputs,
)


def main():
    result = generate_single_model_predictions()
    write_prediction_outputs(result)


if __name__ == "__main__":
    main()
