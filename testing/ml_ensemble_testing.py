import pandas as pd
import numpy as np
import joblib
import json
import os

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

new_data = pd.read_csv('data/detailed_fights.csv')
split_index = int(len(new_data) * 0.9)
new_data = new_data[split_index:]

X_new = preprocess_data(new_data, selected_columns)
X_new = X_new.drop(['Result'], axis=1)

X_swapped = X_new.copy()
for column in X_new.columns:
    X_swapped[column] = X_new[column] * -1

X_new = pd.concat([X_new, X_swapped], ignore_index=True)
swapped_data = new_data.copy()
swapped_data['Red Fighter'], swapped_data['Blue Fighter'] = new_data['Blue Fighter'], new_data['Red Fighter']
new_data = pd.concat([new_data, swapped_data])

predicted_probabilities = [model.predict_proba(X_new) for model in models]

ensemble_predicted_probabilities = np.mean(predicted_probabilities, axis=0)
ensemble_preds = np.argmax(ensemble_predicted_probabilities, axis=1)

# Convert predictions back to original labels
predicted_labels = label_encoder.inverse_transform(ensemble_preds)

# Add predictions to the new data DataFrame
new_data['Predicted Result'] = predicted_labels

# new_data.to_csv('predictions.csv', index=False)

fighter_data = new_data[['Red Fighter', 'Blue Fighter']]

fighter_data['Probability Win'] = ensemble_predicted_probabilities[:, 1]
fighter_data['Probability Lose'] = ensemble_predicted_probabilities[:, 0]

fighter_data.to_csv('data/predicted_results.csv', index=False)


