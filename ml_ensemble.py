import csv
import os
import json
import pandas as pd
import sys
import lightgbm as lgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
from sklearn.model_selection import cross_val_score
import numpy as np
from sklearn.metrics import log_loss
import optuna
import os

file_path = os.path.join("data", "detailed_fights.csv")
# file_path = "predict_fights_alpha.csv"

df = pd.read_csv(file_path)

label_encoder = LabelEncoder()
df["Result"] = label_encoder.fit_transform(df["Result"])

selected_columns = df.columns.tolist()

columns_to_remove = ["Red Fighter", "Blue Fighter", "Title", "Date"]
selected_columns = [col for col in selected_columns if col not in columns_to_remove]
# selected_columns = [col for col in selected_columns if 'red' not in col.lower() and 'blue' not in col.lower()]
corr_matrix = df[selected_columns].corr().abs()

upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))

to_drop = [column for column in upper_tri.columns if any(upper_tri[column] > 0.95)]

# Drop highly correlated features
df.drop(to_drop, axis=1, inplace=True)

selected_columns = [column for column in selected_columns if column not in to_drop]

df = df[selected_columns]

X = df.drop(["Result"], axis=1)
y = df["Result"]

split_index = int(len(df) * 0.95)
last_index = int(len(df) * 1)
X_train, X_test = X[:split_index], X[split_index:last_index]
y_train, y_test = y[:split_index], y[split_index:last_index]

seed = 42
prune_index = int(len(X_train) * 0.3)


X_train = X_train[prune_index:]
y_train = y_train[prune_index:]

# win_count = y_train.value_counts()[1]  # Assuming 'win' is encoded as 1
# loss_count = y_train.value_counts()[0]  # Assuming 'loss' is encoded as 0

# print(f"Number of wins in train: {win_count}")
# print(f"Number of losses in train: {loss_count}")

# win_count2 = y_test.value_counts()[1]  # Assuming 'win' is encoded as 1
# loss_count2 = y_test.value_counts()[0]  # Assuming 'loss' is encoded as 0

# print(f"Number of wins in test: {win_count2}")
# print(f"Number of losses in test: {loss_count2}")
X_train_swapped = X_train.copy()
y_train_swapped = y_train.copy()

swap_columns = {}
for column in X_train.columns:
    if "Red" in column:
        swap_columns[column] = column.replace("Red", "Blue")
    elif "Blue" in column:
        swap_columns[column] = column.replace("Blue", "Red")

X_train_swapped.rename(columns=swap_columns, inplace=True)
y_train_swapped = y_train_swapped.apply(lambda x: 0 if x == 1 else 1)

X_train_extended = pd.concat([X_train, X_train_swapped], ignore_index=True)
y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)

from sklearn.model_selection import TimeSeriesSplit

def objective(trial):
    param = {
        'objective': 'multiclass',
        'metric': 'multi_logloss',
        'verbosity': -1,
        'boosting_type': 'gbdt', 
        'lambda_l1': trial.suggest_float('lambda_l1', 1e-8, 10.0, log=True),
        'lambda_l2': trial.suggest_float('lambda_l2', 1e-8, 10.0, log=True),
        'num_leaves': trial.suggest_int('num_leaves', 20, 100),
        'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True),
        'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),  
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),  
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),  
        'num_class': 2  
    }
    # data = lgb.Dataset(X_train, label=y_train)
    data = lgb.Dataset(X_train_extended, label=y_train_extended)

    # Initialize TimeSeriesSplit
    tscv = TimeSeriesSplit(n_splits=5)  # Adjust the number of splits as needed

    # Training model with time series cross-validation
    cv_results = lgb.cv(
        param,
        data,
        num_boost_round=1000,
        folds=tscv,  
        stratified=False, 
        shuffle=False, 
        callbacks=[lgb.early_stopping(stopping_rounds=30)],
    )
    
    print(cv_results.keys())

    best_score = cv_results['valid multi_logloss-mean'][-1]

    return best_score

n_models = 5

studies = []
models = []


for _ in range(n_models):
    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=10)

    best_params = study.best_params

    model = lgb.LGBMClassifier(**best_params)
    # model.fit(X_train, y_train)
    model.fit(X_train_extended, y_train_extended)

    studies.append(study)
    models.append(model)

predicted_probabilities = [model.predict_proba(X_test) for model in models]
ensemble_predicted_probabilities = np.mean(predicted_probabilities, axis=0)

ensemble_preds = np.argmax(ensemble_predicted_probabilities, axis=1)

# Evaluate the ensemble model
accuracy = accuracy_score(y_test, ensemble_preds)
logloss = log_loss(y_test, ensemble_predicted_probabilities)
print(accuracy)
print(logloss)
# Get the fighter names and actual results for the test set
df_with_details = pd.read_csv(file_path)[
    ["Red Fighter", "Blue Fighter", "Result"]
]
df_with_details = df_with_details.iloc[split_index:]  # Align with the test data split
df_with_details.reset_index(drop=True, inplace=True)
df_with_details["Result"] = label_encoder.fit_transform(df_with_details["Result"])

# Convert the predicted and actual results back to the original labels if necessary.
predicted_labels = label_encoder.inverse_transform(ensemble_preds)
actual_labels = label_encoder.inverse_transform(df_with_details["Result"])

with open(os.path.join("data", "predicted_results.csv"), mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(
        [
            "Red Fighter",
            "Blue Fighter",
            "Predicted Result",
            "Probability",
            "Actual Result",
        ]
    )
    for i in range(len(predicted_labels)):
        max_probability = max(ensemble_predicted_probabilities[i])

        writer.writerow(
            [
                df_with_details["Red Fighter"].iloc[i],
                df_with_details["Blue Fighter"].iloc[i],
                predicted_labels[i],
                max_probability,  # Formatting as a percentage
                actual_labels[i],
            ]
        )

import joblib

model_save_dir = "saved_models"
os.makedirs(model_save_dir, exist_ok=True)

for idx, model in enumerate(models):
    model_filename = os.path.join(model_save_dir, f"lgbm_model_{idx}.joblib")
    joblib.dump(model, model_filename)

preprocessing_save_dir = "saved_preprocessing"
os.makedirs(preprocessing_save_dir, exist_ok=True)

label_encoder_filename = os.path.join(preprocessing_save_dir, "label_encoder.joblib")
joblib.dump(label_encoder, label_encoder_filename)

selected_columns_filename = os.path.join(preprocessing_save_dir, "selected_columns.json")
with open(selected_columns_filename, "w") as file:
    json.dump(selected_columns, file)
