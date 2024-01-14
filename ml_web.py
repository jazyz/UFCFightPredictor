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

    # Load new data (example: 'new_data.csv')
    new_data = pd.read_csv('data/predict_fights_alpha.csv')

    # Preprocess new data
    # Assuming new_data is your dataframe for prediction
    X_new = preprocess_data(new_data, selected_columns)
    X_new = X_new.drop(['Result'], axis=1)  # Exclude 'Result' from the new data for predictions
    # Make predictions with all models
    predicted_probabilities = [model.predict_proba(X_new) for model in models]

    # Average the predictions if using an ensemble approach
    ensemble_predicted_probabilities = np.mean(predicted_probabilities, axis=0)
    ensemble_preds = np.argmax(ensemble_predicted_probabilities, axis=1)

    # Convert predictions back to original labels
    predicted_labels = label_encoder.inverse_transform(ensemble_preds)

    # Add predictions to the new data DataFrame
    new_data['Predicted Result'] = predicted_labels

    # # Save or display the predictions
    # new_data.to_csv('predictions.csv', index=False)

    fighter_data = new_data[['Red Fighter', 'Blue Fighter']]

    # Add the predicted probabilities to the fighter data
    # Assuming the order of probabilities is [Win, Lose, Draw]
    fighter_data['Probability Win'] = ensemble_predicted_probabilities[:, 2]
    fighter_data['Probability Lose'] = ensemble_predicted_probabilities[:, 1]
    fighter_data['Probability Draw'] = ensemble_predicted_probabilities[:, 0]

    # Save or display the results1
    fighter_data.to_csv('data/fight_predictions.csv', index=False)

    # Save the results as a JSON file
    # Assuming the order of probabilities is [Win, Lose, Draw]
    predict_data = []
    for i in range(len(fighter_data)):
        predict_data.append({
            "Red Fighter": fighter_data.iloc[i]['Red Fighter'],
            "Blue Fighter": fighter_data.iloc[i]['Blue Fighter'],
            "Probability Win": fighter_data.iloc[i]['Probability Win'],
            "Probability Lose": fighter_data.iloc[i]['Probability Lose'],
            "Probability Draw": fighter_data.iloc[i]['Probability Draw'],
        })
    class_probabilities = {
        "Win": ensemble_predicted_probabilities[:, 2].tolist(),
        "Lose": ensemble_predicted_probabilities[:, 1].tolist(),
        "Draw": ensemble_predicted_probabilities[:, 0].tolist(),
    }
    predicted_data_dict = {
        "predict_data": predict_data,
        "class_probabilities": class_probabilities,
    }
    with open(os.path.join("data", "predicted_data.json"), "w") as json_file:
        json.dump(predicted_data_dict, json_file)
    

if __name__ == "__main__":
    main()


