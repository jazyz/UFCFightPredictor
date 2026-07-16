import pandas as pd
import numpy as np
import joblib
import json
import os

def main():
    # Function to load a model
    def load_model(model_path):
        return joblib.load(model_path)

    # Function to load preprocessing tools
    def load_preprocessing_tools(label_encoder_path, selected_columns_path):
        label_encoder = joblib.load(label_encoder_path)
        with open(selected_columns_path, "r") as file:
            selected_columns = json.load(file)
        return label_encoder, selected_columns

    # Load LabelEncoder and selected columns
    preprocessing_save_dir = "saved_preprocessing"
    label_encoder, selected_columns = load_preprocessing_tools(
        os.path.join(preprocessing_save_dir, "label_encoder.joblib"),
        os.path.join(preprocessing_save_dir, "selected_columns.json")
    )

    # Load models
    model_save_dir = "saved_models"
    models = [load_model(os.path.join(model_save_dir, filename)) for filename in os.listdir(model_save_dir) if filename.endswith('.joblib')]

    # Function to preprocess new data
    def preprocess_data(new_data, selected_columns):
        return new_data[selected_columns]

    new_data = pd.read_csv('data/predict_fights_alpha.csv')

    if len(new_data) == 0:
        raise ValueError(
            "No fights to predict: predict_fights_alpha.csv is empty "
            "(fighter not found in stats, missing DOB, or fewer than 2 recorded fights)"
        )

    X_new = preprocess_data(new_data, selected_columns)
    X_new = X_new.drop(['Result'], axis=1)

    predicted_probabilities = [model.predict_proba(X_new) for model in models]

    ensemble_predicted_probabilities = np.mean(predicted_probabilities, axis=0)
    ensemble_preds = np.argmax(ensemble_predicted_probabilities, axis=1)

    predicted_labels = label_encoder.inverse_transform(ensemble_preds)

    new_data['Predicted Result'] = predicted_labels

    # look up class positions instead of assuming column 1 is "win"
    win_index = list(label_encoder.classes_).index('win')
    loss_index = list(label_encoder.classes_).index('loss')

    fighter_data = new_data[['Red Fighter', 'Blue Fighter']].copy()

    fighter_data['Probability Win'] = ensemble_predicted_probabilities[:, win_index]
    fighter_data['Probability Lose'] = ensemble_predicted_probabilities[:, loss_index]

    fighter_data.to_csv('data/fight_predictions.csv', index=False)

    predict_data = []
    for i in range(len(fighter_data)):
        predict_data.append({
            "Red Fighter": fighter_data.iloc[i]['Red Fighter'],
            "Blue Fighter": fighter_data.iloc[i]['Blue Fighter'],
            "Probability Win": fighter_data.iloc[i]['Probability Win'],
            "Probability Lose": fighter_data.iloc[i]['Probability Lose'],
        })
    class_probabilities = {
        "Win": ensemble_predicted_probabilities[:, win_index].tolist(),
        "Lose": ensemble_predicted_probabilities[:, loss_index].tolist(),
    }
    predicted_data_dict = {
        "predict_data": predict_data,
        "class_probabilities": class_probabilities,
    }
    with open(os.path.join("data", "predicted_data.json"), "w") as json_file:
        json.dump(predicted_data_dict, json_file)
    

if __name__ == "__main__":
    main()


