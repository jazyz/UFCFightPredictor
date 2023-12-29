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

# Step 1: Read the data
df = pd.read_csv("data\detailed_fights.csv")
# Step 2: Preprocess the data
# Assuming 'Result' is the target variable and the rest are features
label_encoder = LabelEncoder()
df["Result"] = label_encoder.fit_transform(df["Result"])

selected_columns = [
    "Result",
    # "Red Fighter",
    # "Blue Fighter",
    # "Title",
    "Red dob",
    "Blue dob",
    "Red totalfights",
    "Blue totalfights",
    "Red elo",
    "Blue elo",
    "Red losestreak",
    "Blue losestreak",
    "Red winstreak",
    "Blue winstreak",
    "Red titlewins",
    "Blue titlewins",
    "Red oppelo",
    "Blue oppelo",
    "Red wins",
    "Blue wins",
    "Red losses",
    "Blue losses",
    "Red KD",
    "Blue KD",
    "Red KD differential",
    "Blue KD differential",
    "Red Sig. str.",
    "Blue Sig. str.",
    "Red Sig. str. differential",
    "Blue Sig. str. differential",
    "Red Total str.",
    "Blue Total str.",
    "Red Total str. differential",
    "Blue Total str. differential",
    "Red Td",
    "Blue Td",
    "Red Td differential",
    "Blue Td differential",
    "Red Sub. att",
    "Blue Sub. att",
    "Red Sub. att differential",
    "Blue Sub. att differential",
    "Red Rev.",
    "Blue Rev.",
    "Red Rev. differential",
    "Blue Rev. differential",
    "Red Ctrl",
    "Blue Ctrl",
    "Red Ctrl differential",
    "Blue Ctrl differential",
    "Red Head",
    "Blue Head",
    "Red Head differential",
    "Blue Head differential",
    "Red Body",
    "Blue Body",
    "Red Body differential",
    "Blue Body differential",
    "Red Leg",
    "Blue Leg",
    "Red Leg differential",
    "Blue Leg differential",
    "Red Distance",
    "Blue Distance",
    "Red Distance differential",
    "Blue Distance differential",
    "Red Clinch",
    "Blue Clinch",
    "Red Clinch differential",
    "Blue Clinch differential",
    "Red Ground",
    "Blue Ground",
    "Red Ground differential",
    "Blue Ground differential",
    "Red Sig. str.%",
    "Blue Sig. str.%",
    "Red Sig. str.% differential",
    "Blue Sig. str.% differential",
    "Red Sig. str.% defense",
    "Blue Sig. str.% defense",
    "Red Total str.%",
    "Blue Total str.%",
    "Red Total str.% differential",
    "Blue Total str.% differential",
    "Red Total str.% defense",
    "Blue Total str.% defense",
    "Red Td%",
    "Blue Td%",
    "Red Td% differential",
    "Blue Td% differential",
    "Red Td% defense",
    "Blue Td% defense",
    "Red Head%",
    "Blue Head%",
    "Red Head% differential",
    "Blue Head% differential",
    "Red Head% defense",
    "Blue Head% defense",
    "Red Body%",
    "Blue Body%",
    "Red Body% differential",
    "Blue Body% differential",
    "Red Body% defense",
    "Blue Body% defense",
    "Red Leg%",
    "Blue Leg%",
    "Red Leg% differential",
    "Blue Leg% differential",
    "Red Leg% defense",
    "Blue Leg% defense",
    "Red Distance%",
    "Blue Distance%",
    "Red Distance% differential",
    "Blue Distance% differential",
    "Red Distance% defense",
    "Blue Distance% defense",
    "Red Clinch%",
    "Blue Clinch%",
    "Red Clinch% differential",
    "Blue Clinch% differential",
    "Red Clinch% defense",
    "Blue Clinch% defense",
    "Red Ground%",
    "Blue Ground%",
    "Red Ground% differential",
    "Blue Ground% differential",
    "Red Ground% defense",
    "Blue Ground% defense",
    "dob oppdiff",
    "totalfights oppdiff",
    "elo oppdiff",
    "losestreak oppdiff",
    "winstreak oppdiff",
    "titlewins oppdiff",
    "oppelo oppdiff",
    "wins oppdiff",
    "losses oppdiff",
    "KD oppdiff",
    "KD differential oppdiff",
    "Sig. str. oppdiff",
    "Sig. str. differential oppdiff",
    "Total str. oppdiff",
    "Total str. differential oppdiff",
    "Td oppdiff",
    "Td differential oppdiff",
    "Sub. att oppdiff",
    "Sub. att differential oppdiff",
    "Rev. oppdiff",
    "Rev. differential oppdiff",
    "Ctrl oppdiff",
    "Ctrl differential oppdiff",
    "Head oppdiff",
    "Head differential oppdiff",
    "Body oppdiff",
    "Body differential oppdiff",
    "Leg oppdiff",
    "Leg differential oppdiff",
    "Distance oppdiff",
    "Distance differential oppdiff",
    "Clinch oppdiff",
    "Clinch differential oppdiff",
    "Ground oppdiff",
    "Ground differential oppdiff",
    "Sig. str.% oppdiff",
    "Sig. str.% differential oppdiff",
    "Sig. str.% defense oppdiff",
    "Total str.% oppdiff",
    "Total str.% differential oppdiff",
    "Total str.% defense oppdiff",
    "Td% oppdiff",
    "Td% differential oppdiff",
    "Td% defense oppdiff",
    "Head% oppdiff",
    "Head% differential oppdiff",
    "Head% defense oppdiff",
    "Body% oppdiff",
    "Body% differential oppdiff",
    "Body% defense oppdiff",
    "Leg% oppdiff",
    "Leg% differential oppdiff",
    "Leg% defense oppdiff",
    "Distance% oppdiff",
    "Distance% differential oppdiff",
    "Distance% defense oppdiff",
    "Clinch% oppdiff",
    "Clinch% differential oppdiff",
    "Clinch% defense oppdiff",
    "Ground% oppdiff",
    "Ground% differential oppdiff",
    "Ground% defense oppdiff",
]

corr_matrix = df[selected_columns].corr().abs()

# Select upper triangle of correlation matrix
upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))

# Find features with correlation greater than 95%
to_drop = [column for column in upper_tri.columns if any(upper_tri[column] > 0.95)]

# Drop highly correlated features
df.drop(to_drop, axis=1, inplace=True)

# Make sure to update the 'selected_columns' to reflect the dropped columns
selected_columns = [column for column in selected_columns if column not in to_drop]

df = df[selected_columns]
X = df.drop(["Result"], axis=1)
y = df["Result"]

# Convert categorical variables if any
# X = pd.get_dummies(X)  # This line is optional and depends on your data

# Manual split based on percentage
split_index = int(len(df) * 0.9)
last_index = int(len(df) * 1)
X_train, X_test = X[:split_index], X[split_index:last_index]
y_train, y_test = y[:split_index], y[split_index:last_index]

seed = 42

# Determine the new start index for the training data to skip the first 20%
prune_index = int(len(X_train) * 0.1)


X_train = X_train[prune_index:]
y_train = y_train[prune_index:]


# Step 1: Duplicate the training data
X_train_swapped = X_train.copy()
y_train_swapped = y_train.copy()

# Step 2: Rename the columns to swap 'Red' with 'Blue'
swap_columns = {}
for column in X_train.columns:
    if "Red" in column:
        swap_columns[column] = column.replace("Red", "Blue")
    elif "Blue" in column:
        swap_columns[column] = column.replace("Blue", "Red")

# Rename the columns in the copied DataFrame
X_train_swapped.rename(columns=swap_columns, inplace=True)

# Inverse the target variable for the swapped data
# Assuming 'win', 'loss', and 'draw' are the possible values
y_train_swapped = y_train_swapped.apply(lambda x: 2 if x == 1 else (1 if x == 2 else 0))

# Step 3: Concatenate the original and the modified copy to form the extended training set
X_train_extended = pd.concat([X_train, X_train_swapped], ignore_index=True)
y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)


# # for accuracy
def objective(trial):
    # Parameter suggestions by Optuna for tuning
    param = {
        "objective": "multiclass",  # or 'binary' for binary classification
        "verbosity": -1,
        "boosting_type": "gbdt",  # Default boosting type
        "num_leaves": trial.suggest_int(
            "num_leaves", 20, 100
        ),  # more conservative than default
        "learning_rate": trial.suggest_float(
            "learning_rate", 0.02, 0.2, log=True
        ),  # adjusted range for more granular learning rates
        "min_child_samples": trial.suggest_int(
            "min_child_samples", 10, 100
        ),  # adjusted range to prevent overfitting
        "subsample": trial.suggest_float(
            "subsample", 0.5, 1.0
        ),  # subsample ratio of the training instance
        "colsample_bytree": trial.suggest_float(
            "colsample_bytree", 0.5, 1.0
        ),  # subsample ratio of columns when constructing each tree
        "n_estimators": 100,  # Fixed number of estimators for simplicity
        "num_class": 3,  # Replace with the actual number of classes in your dataset
    }

    # Splitting data for validation
    X_train, X_valid, y_train, y_valid = train_test_split(
        X_train_extended, y_train_extended, test_size=0.2, stratify=y_train_extended
    )

    # Creating LightGBM datasets
    dtrain = lgb.Dataset(X_train, label=y_train)
    dvalid = lgb.Dataset(X_valid, label=y_valid)

    # Training model
    model = lgb.train(
        param,
        dtrain,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(stopping_rounds=30)],
    )

    # Making predictions
    preds = model.predict(X_valid, num_iteration=model.best_iteration)
    pred_labels = np.argmax(preds, axis=1)  # For multiclass classification

    # Calculate accuracy
    accuracy = accuracy_score(y_valid, pred_labels)

    # Return negative accuracy for maximization
    return (
        accuracy  # Optuna minimizes the objective, so use negative accuracy to maximize
    )


# def objective(trial):
#     # Parameter suggestions by Optuna for tuning
#     param = {
#         'objective': 'multiclass',  # or 'binary' for binary classification
#         'metric': 'multi_logloss',
#         'verbosity': -1,
#         'boosting_type': 'gbdt',    # Default boosting type
#         'num_leaves': trial.suggest_int('num_leaves', 20, 100),  # more conservative than default
#         'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True),  # adjusted range for more granular learning rates
#         'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),  # adjusted range to prevent overfitting
#         'subsample': trial.suggest_float('subsample', 0.5, 1.0),  # subsample ratio of the training instance
#         'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),  # subsample ratio of columns when constructing each tree
#         'n_estimators': 100,  # Fixed number of estimators for simplicity
#         'num_class': 3  # Replace with the actual number of classes in your dataset
#     }

#         # Splitting data for validation
#     X_train, X_valid, y_train, y_valid = train_test_split(X_train_extended, y_train_extended, test_size=0.2, stratify=y_train_extended)

#     # Creating LightGBM datasets
#     dtrain = lgb.Dataset(X_train, label=y_train)
#     dvalid = lgb.Dataset(X_valid, label=y_valid)

#     # Training model
#     model = lgb.train(
#         param,
#         dtrain,
#         valid_sets=[dvalid],
#         callbacks=[lgb.early_stopping(stopping_rounds=30)]
#     )

#     # Making predictions
#     preds = model.predict(X_valid, num_iteration=model.best_iteration)
#     logloss = log_loss(y_valid, preds)

#     return logloss

#     # data = lgb.Dataset(X_train_extended, label=y_train_extended)
#     # # Training model
#     # cv_results = lgb.cv(
#     #     param,
#     #     data,
#     #     num_boost_round=1000,
#     #     nfold=3,  # Or another number of folds
#     #     stratified=True,
#     #     shuffle=True,
#     #     callbacks=[lgb.early_stopping(stopping_rounds=20)],
#     # )

#     # print(cv_results.keys())

#     # # Extract the best score
#     # best_score = cv_results['valid multi_logloss-mean'][-1]

#     # return best_score

# Create the study object with maximization direction
study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=10)

# Fetching the best parameters
best_params = study.best_params
best_score = study.best_value

# Output the best parameters and score
print(f"Best params: {best_params}")
print(f"Best score: {best_score}")

with open("best_params.json", "w") as file:
    # Creating a dictionary to hold data
    data_to_save = {"best_params": best_params, "best_score": best_score}
    # Writing as a JSON formatted string for readability and ease of use
    json.dump(data_to_save, file, indent=4)
# Now use the best parameters to fit the model on complete training data

with open("best_params.json", "r") as file:
    data_loaded = json.load(file)

# Extracting the best parameters and score from the loaded data
best_params = data_loaded["best_params"]
best_score = data_loaded["best_score"]

model = lgb.LGBMClassifier(**best_params)
model.fit(X_train_extended, y_train_extended)
# Make predictions and evaluate the model
y_pred = model.predict(X_test)
predicted_probabilities = model.predict_proba(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy:.4f}")

# Get the fighter names and actual results for the test set
df_with_details = pd.read_csv("data\detailed_fights.csv")[
    ["Red Fighter", "Blue Fighter", "Result"]
]
df_with_details = df_with_details.iloc[split_index:]  # Align with the test data split
df_with_details.reset_index(drop=True, inplace=True)
df_with_details["Result"] = label_encoder.fit_transform(df_with_details["Result"])

# Convert the predicted and actual results back to the original labels if necessary.
predicted_labels = label_encoder.inverse_transform(y_pred)
actual_labels = label_encoder.inverse_transform(df_with_details["Result"])

with open("data\predicted_results.csv", mode="w", newline="") as file:
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
        max_probability = max(predicted_probabilities[i])

        writer.writerow(
            [
                df_with_details["Red Fighter"].iloc[i],
                df_with_details["Blue Fighter"].iloc[i],
                predicted_labels[i],
                max_probability,  # Formatting as a percentage
                actual_labels[i],
            ]
        )

feature_importances = model.feature_importances_

feature_importance_df = pd.DataFrame(
    {"Feature": X_train.columns, "Importance": feature_importances}
)

feature_importance_df = feature_importance_df.sort_values("Importance", ascending=False)

plt.figure(figsize=(10, 6))
plt.barh(feature_importance_df["Feature"], feature_importance_df["Importance"])
plt.xlabel("Importance")
plt.ylabel("Feature")
plt.title("Feature Importance")
plt.show()

print("Top 10 Important Features:")
print(feature_importance_df.head(10))

# def objective(trial):
#     # Parameter suggestions by Optuna for tuning
#     param = {
#         'objective': 'multiclass',  # or 'binary' for binary classification
#         'verbosity': -1,
#         'boosting_type': 'gbdt',    # Default boosting type
#         'num_leaves': trial.suggest_int('num_leaves', 30, 150),  # more conservative than default
#         'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True),  # adjusted range for more granular learning rates
#         'min_child_samples': trial.suggest_int('min_child_samples', 20, 100),  # adjusted range to prevent overfitting
#         'subsample': trial.suggest_float('subsample', 0.5, 1.0),  # subsample ratio of the training instance
#         'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),  # subsample ratio of columns when constructing each tree
#         'n_estimators': 100,  # Fixed number of estimators for simplicity
#         'num_class': 3  # Replace with the actual number of classes in your dataset
#     }

#     # Splitting data for validation
#     X_train, X_valid, y_train, y_valid = train_test_split(X_train_extended, y_train_extended, test_size=0.2, stratify=y_train_extended)

#     # Creating LightGBM datasets
#     dtrain = lgb.Dataset(X_train, label=y_train)
#     dvalid = lgb.Dataset(X_valid, label=y_valid)

#     # Training model
#     model = lgb.train(
#         param,
#         dtrain,
#         valid_sets=[dvalid],
#         callbacks=[lgb.early_stopping(stopping_rounds=10)]
#     )

#     # Making predictions
#     preds = model.predict(X_valid, num_iteration=model.best_iteration)
#     pred_labels = np.argmax(preds, axis=1)  # For multiclass classification

#     # Calculate accuracy
#     accuracy = accuracy_score(y_valid, pred_labels)

#     # Return negative accuracy for maximization
#     return accuracy  # Optuna minimizes the objective, so use negative accuracy to maximize
