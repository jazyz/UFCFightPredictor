import pandas as pd
import numpy as np
import joblib
import json
import os

from utils.feature_sanitization import sanitize_age_features, validate_feature_ranges

def main():
    def load_model(model_path):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Missing model artifact: {model_path}")
        return joblib.load(model_path)

    def load_preprocessing_tools(label_encoder_path, selected_columns_path):
        if not os.path.exists(label_encoder_path):
            raise FileNotFoundError(f"Missing label encoder artifact: {label_encoder_path}")
        if not os.path.exists(selected_columns_path):
            raise FileNotFoundError(f"Missing selected-columns artifact: {selected_columns_path}")
        label_encoder = joblib.load(label_encoder_path)
        with open(selected_columns_path, "r") as file:
            selected_columns = json.load(file)
        return label_encoder, selected_columns

    preprocessing_save_dir = "saved_preprocessing"
    label_encoder, selected_columns = load_preprocessing_tools(
        os.path.join(preprocessing_save_dir, "label_encoder_single.joblib"),
        os.path.join(preprocessing_save_dir, "selected_columns_single.json"),
    )

    model_save_dir = "saved_models"
    model = load_model(os.path.join(model_save_dir, "lgbm_single_model.joblib"))

    def preprocess_data(new_data, selected_columns):
        return new_data[selected_columns]

    new_data = sanitize_age_features(pd.read_csv('data/predict_fights_alpha.csv'))
    reference_data = sanitize_age_features(pd.read_csv('data/detailed_fights.csv'))
    validate_feature_ranges(
        new_data,
        reference_data,
        selected_columns,
        context='data/predict_fights_alpha.csv',
    )

    X_new = preprocess_data(new_data, selected_columns)
    X_new = X_new.drop(["Result", "Date"], axis=1, errors="ignore")

    predicted_probabilities = model.predict_proba(X_new)
    predicted_classes = np.argmax(predicted_probabilities, axis=1)

    predicted_labels = label_encoder.inverse_transform(predicted_classes)

    new_data['Predicted Result'] = predicted_labels

    fighter_data = new_data[['Red Fighter', 'Blue Fighter']].copy()

    fighter_data['Probability Win'] = predicted_probabilities[:, 1]
    fighter_data['Probability Lose'] = predicted_probabilities[:, 0]

    fighter_data.to_csv('data/fight_predictions.csv', index=False)
    fighter_data.to_csv('data/betting_predictions.csv', index=False)

    predict_data = []
    for i in range(len(fighter_data)):
        predict_data.append({
            "Red Fighter": fighter_data.iloc[i]['Red Fighter'],
            "Blue Fighter": fighter_data.iloc[i]['Blue Fighter'],
            "Probability Win": fighter_data.iloc[i]['Probability Win'],
            "Probability Lose": fighter_data.iloc[i]['Probability Lose'],
        })
    class_probabilities = {
        "Win": predicted_probabilities[:, 1].tolist(),
        "Lose": predicted_probabilities[:, 0].tolist(),
    }
    predicted_data_dict = {
        "predict_data": predict_data,
        "class_probabilities": class_probabilities,
    }
    with open(os.path.join("data", "predicted_data.json"), "w") as json_file:
        json.dump(predicted_data_dict, json_file)
    

if __name__ == "__main__":
    main()
