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

def main():
    file_path = os.path.join("data", "detailed_fights.csv")
    # file_path = "predict_fights_alpha.csv"

    # Step 1: Read the data
    df = pd.read_csv(file_path)

    # Step 2: Preprocess the data
    # Assuming 'Result' is the target variable and the rest are features
    label_encoder = LabelEncoder()
    df["Result"] = label_encoder.fit_transform(df["Result"])

    selected_columns = df.columns.tolist()

    columns_to_remove = ["Red Fighter", "Blue Fighter", "Title", "Date", "Red age", "Blue age", "Red avg age", "Blue avg age", "age oppdiff", "avg age oppdiff"]
    selected_columns = [col for col in selected_columns if col not in columns_to_remove]

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
    split_index = int(len(df) * 0.95)
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


    def objective(trial):
        # Parameter suggestions by Optuna for tuning
        param = {
            'objective': 'multiclass',  # or 'binary' for binary classification
            'metric': 'multi_logloss',
            'verbosity': -1,
            'boosting_type': 'gbdt',    # Default boosting type
            'num_leaves': trial.suggest_int('num_leaves', 20, 100),  # more conservative than default
            'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True),  # adjusted range for more granular learning rates
            'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),  # adjusted range to prevent overfitting
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),  # subsample ratio of the training instance
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),  # subsample ratio of columns when constructing each tree
            'n_estimators': 100,  # Fixed number of estimators for simplicity
            'num_class': 3  # Replace with the actual number of classes in your dataset
        }

        #     # Splitting data for validation
        # X_train, X_valid, y_train, y_valid = train_test_split(X_train_extended, y_train_extended, test_size=0.2, stratify=y_train_extended)

        # # Creating LightGBM datasets
        # dtrain = lgb.Dataset(X_train, label=y_train)
        # dvalid = lgb.Dataset(X_valid, label=y_valid)

        # # Training model
        # model = lgb.train(
        #     param,
        #     dtrain,
        #     valid_sets=[dvalid],
        #     callbacks=[lgb.early_stopping(stopping_rounds=30)]
        # )

        # # Making predictions
        # preds = model.predict(X_valid, num_iteration=model.best_iteration)
        # logloss = log_loss(y_valid, preds)

        # return logloss

        # data = lgb.Dataset(X_train_extended, label=y_train_extended)
        data = lgb.Dataset(X_train_extended, label=y_train_extended)
        # Training model
        cv_results = lgb.cv(
            param,
            data,
            num_boost_round=1000,
            nfold=3,  # Or another number of folds
            stratified=True,
            shuffle=True,
            callbacks=[lgb.early_stopping(stopping_rounds=20)],
        )

        print(cv_results.keys())

        # Extract the best score
        best_score = cv_results['valid multi_logloss-mean'][-1]

        return best_score

    # study = optuna.create_study(direction="minimize")
    # study.optimize(objective, n_trials=10)

    # # Fetching the best parameters
    # best_params = study.best_params
    # best_score = study.best_value

    # # Output the best parameters and score
    # print(f"Best params: {best_params}")
    # print(f"Best score: {best_score}")

    # with open("data/best_params.json", "w") as file:
    #     # Creating a dictionary to hold data
    #     data_to_save = {"best_params": best_params, "best_score": best_score}
    #     # Writing as a JSON formatted string for readability and ease of use
    #     json.dump(data_to_save, file, indent=4)


    with open("data/best_params.json", "r") as file:
        data_loaded = json.load(file)

    # Extracting the best parameters and score from the loaded data
    best_params = data_loaded["best_params"]
    best_score = data_loaded["best_score"]

    model = lgb.LGBMClassifier(**best_params)
    # model = lgb.LGBMClassifier(random_state=seed)
    model.fit(X_train_extended, y_train_extended)
    # model.fit(X_train, y_train)
    # Make predictions and evaluate the model
    y_pred = model.predict(X_test)
    predicted_probabilities = model.predict_proba(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logloss = log_loss(y_test, predicted_probabilities)

    print(f"Accuracy: {accuracy:.4f}")
    print(f"Log Loss: {logloss:.4f}")

    # Get the fighter names and actual results for the test set
    df_with_details = pd.read_csv(file_path)[
        ["Red Fighter", "Blue Fighter", "Result"]
    ]
    df_with_details = df_with_details.iloc[split_index:]  # Align with the test data split
    df_with_details.reset_index(drop=True, inplace=True)
    df_with_details["Result"] = label_encoder.fit_transform(df_with_details["Result"])

    # Convert the predicted and actual results back to the original labels if necessary.
    predicted_labels = label_encoder.inverse_transform(y_pred)
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

    # plt.figure(figsize=(10, 6))
    # plt.barh(feature_importance_df["Feature"], feature_importance_df["Importance"])
    # plt.xlabel("Importance")
    # plt.ylabel("Feature")
    # plt.title("Feature Importance")
    # plt.show()

    print("Top 10 Important Features:")
    print(feature_importance_df.head(10))

    # ***** writing all detailed stats to predicted_fights_alpha_results.txt *****
    output_file = open(os.path.join("data", "predicted_fights_alpha_results.txt"), "w")
    original_stdout = sys.stdout
    sys.stdout = output_file
    pd.set_option("display.max_columns", None)  # Display all columns
    pd.set_option("display.max_rows", None)     # Display all rows

    predict_data = pd.read_csv(os.path.join("data", "predict_fights_alpha.csv"))
    predict_data.replace("--", pd.NA, inplace=True)
    fighter_name_label = "fighter_names"

    print(f"{fighter_name_label}", file=output_file)
    print(predict_data["Red Fighter"] + "*" + predict_data["Blue Fighter"], file=output_file)

    predict_data.dropna(subset=selected_columns, inplace=True)
    predict_data = predict_data[selected_columns]

    X_predict = predict_data.drop(["Result"], axis=1)

    y_pred = model.predict(X_predict)

    class_probabilities = model.predict_proba(X_predict)

    predicted_results = label_encoder.inverse_transform(y_pred)

    predict_data["predicted_result"] = predicted_results
    for i, label in enumerate(label_encoder.classes_):
        predict_data[f"probability_{label}"] = class_probabilities[:, i]

    print(predict_data)

    sys.stdout = original_stdout
    output_file.close()

    # Create a dictionary to store the predicted data and probabilities
    predicted_data_dict = {
        "predict_data": predict_data.to_dict(orient="records"),
        "class_probabilities": class_probabilities.tolist(),
    }

    # Save the dictionary as a JSON file
    with open(os.path.join("data", "predicted_data.json"), "w") as json_file:
        json.dump(predicted_data_dict, json_file)

    # ***** writing a clean version with just win and lose probabilities predicted_fights_alpha_results_clean.txt *****
    # easier to use for betting
    predict_data = pd.read_csv(os.path.join("data", "predict_fights_alpha.csv"))
    with open(os.path.join("data", "predicted_fights_alpha_results_clean.csv"), mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "Red Fighter",
                "Blue Fighter",
                "Probability Win",
                "Probability Lose",
            ]
        )
        for i in range(len(predicted_results)):
            writer.writerow(
                [
                    predict_data["Red Fighter"].iloc[i],
                    predict_data["Blue Fighter"].iloc[i],
                    class_probabilities[i][2],
                    class_probabilities[i][1],
                ]
            )

if __name__ == "__main__":
    main()