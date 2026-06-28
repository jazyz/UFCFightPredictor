import pandas as pd
import numpy as np
import joblib
import json
import os

from utils.feature_sanitization import sanitize_age_features

# Load the single trained model
def load_model(model_path):
    return joblib.load(model_path)

# Load preprocessing tools
def load_preprocessing_tools(label_encoder_path, selected_columns_path):
    label_encoder = joblib.load(label_encoder_path)
    with open(selected_columns_path, "r") as file:
        selected_columns = json.load(file)
    return label_encoder, selected_columns

# Load LabelEncoder and selected columns for single model
preprocessing_save_dir = "saved_preprocessing"
label_encoder, selected_columns = load_preprocessing_tools(
    os.path.join(preprocessing_save_dir, "label_encoder_single.joblib"),
    os.path.join(preprocessing_save_dir, "selected_columns_single.json")
)

# Load the single model
model_save_dir = "saved_models"
model = load_model(os.path.join(model_save_dir, "lgbm_single_model.joblib"))

print("Model loaded successfully!")

# Function to preprocess new data
def preprocess_data(new_data, selected_columns):
    return new_data[selected_columns]

# Load the prepared fight data
new_data = sanitize_age_features(pd.read_csv('data/predict_fights_alpha.csv'))

# Preprocess
X_new = preprocess_data(new_data, selected_columns)
# Drop both Result and Date to match training features
X_new = X_new.drop(['Result', 'Date'], axis=1, errors='ignore')

# Make predictions
predicted_probabilities = model.predict_proba(X_new)
predicted_classes = np.argmax(predicted_probabilities, axis=1)

# Convert predictions back to original labels
predicted_labels = label_encoder.inverse_transform(predicted_classes)

# Add predictions to the DataFrame
new_data['Predicted Result'] = predicted_labels

# Extract relevant columns
fighter_data = new_data[['Red Fighter', 'Blue Fighter']].copy()

# Add probabilities
fighter_data['Red Fighter Win Probability'] = predicted_probabilities[:, 1]  # Win (Red)
fighter_data['Blue Fighter Win Probability'] = predicted_probabilities[:, 0]  # Loss (Blue wins)
fighter_data['Predicted Result'] = predicted_labels
fighter_data['Predicted Winner'] = np.where(
    predicted_labels == 'win',
    fighter_data['Red Fighter'],
    fighter_data['Blue Fighter'],
)

# Save to CSV
output_file = 'data/single_model_predictions.csv'
fighter_data.to_csv(output_file, index=False)

print(f"\n{'='*70}")
print("PREDICTIONS FOR UPCOMING FIGHTS")
print(f"{'='*70}\n")

for idx, row in fighter_data.iterrows():
    red = row['Red Fighter']
    blue = row['Blue Fighter']
    red_prob = row['Red Fighter Win Probability']
    blue_prob = row['Blue Fighter Win Probability']
    winner = row['Predicted Winner']
    result = row['Predicted Result']
    
    print(f"Fight {idx + 1}: {red} vs {blue}")
    print(f"  → {red}: {red_prob:.2%} win probability")
    print(f"  → {blue}: {blue_prob:.2%} win probability")
    print(f"  → Predicted Result: {result}")
    print(f"  → Predicted Winner: {winner}")
    print()

print(f"{'='*70}")
print(f"Results saved to: {output_file}")
print(f"{'='*70}")
