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

    df = pd.read_csv(file_path)

    label_encoder = LabelEncoder()
    df["Result"] = label_encoder.fit_transform(df["Result"])

    selected_columns = df.columns.tolist()
    
    def prune_features(selected_columns):
        columns_to_remove = ["Red Fighter", "Blue Fighter", "Title", "Date"]
        selected_columns = [col for col in selected_columns if col not in columns_to_remove]
        corr_matrix = df[selected_columns].corr().abs()
        upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        to_drop = [column for column in upper_tri.columns if any(upper_tri[column] > 0.95)]
        df.drop(to_drop, axis=1, inplace=True)
        selected_columns = [column for column in selected_columns if column not in to_drop]
        selected_columns.append("Date")
        return selected_columns

    selected_columns = prune_features(selected_columns)
    df = df[selected_columns]
    df["Date"] = pd.to_datetime(df["Date"])
    df.sort_values(by="Date", inplace=True)

    df = df[df["Date"] >= pd.to_datetime("2009-01-01")]
    
    split_date = pd.to_datetime("2021-01-01")  
    # print(df.head())
    # Split based on the date
    train_df = df[df["Date"] < split_date]
    test_df = df[df["Date"] >= split_date]

    X_train = train_df.drop(["Result", "Date"], axis=1)
    y_train = train_df["Result"]
    X_test = test_df.drop(["Result", "Date"], axis=1)
    y_test = test_df["Result"]

    seed = 42

    X_train_swapped = X_train.copy()
    y_train_swapped = y_train.copy()

    swap_columns = {}
    for column in X_train.columns:
        if "Red" in column:
            swap_columns[column] = column.replace("Red", "Blue")
        elif "Blue" in column:
            swap_columns[column] = column.replace("Blue", "Red")

    X_train_swapped.rename(columns=swap_columns, inplace=True)

    y_train_swapped = y_train_swapped.apply(
        lambda x: 0 if x == 1 else 1
    )

    # Step 3: Concatenate the original and the modified copy to form the extended training set
    X_train_extended = pd.concat([X_train, X_train_swapped], ignore_index=True)
    y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)
    
    from sklearn.model_selection import TimeSeriesSplit
    def objective(trial):
        param = {
            'objective': 'multiclass',
            'metric': 'multi_logloss',
            'verbosity': -1,
            'boosting_type': 'gbdt', 
            'num_leaves': trial.suggest_int('num_leaves', 20, 100),
            'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True),
            'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),  
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),  
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),  
            'num_class': 2  
        }
        data = lgb.Dataset(X_train_extended, label=y_train_extended)
        # data = lgb.Dataset(X_train_extended, label=y_train_extended)

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
            callbacks=[lgb.early_stopping(stopping_rounds=50)],
        )
        
        print(cv_results.keys())

        best_score = cv_results['valid multi_logloss-mean'][-1]

        return best_score

    def run_study():
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=30)

        best_params = study.best_params
        best_score = study.best_value

        print(f"Best params: {best_params}")
        print(f"Best score: {best_score}")

        with open("data/best_params.json", "w") as file:
            data_to_save = {"best_params": best_params, "best_score": best_score}
            json.dump(data_to_save, file, indent=4)

    run_study()
    with open("data/best_params.json", "r") as file:
        data_loaded = json.load(file)

    best_params = data_loaded["best_params"]
    best_score = data_loaded["best_score"]

    model = lgb.LGBMClassifier(**best_params)
    # model = lgb.LGBMClassifier(random_state=seed)
    X_train_extended = X_train_extended.drop("Red losses",axis=1)
    model.fit(X_train_extended, y_train_extended)
    # model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    predicted_probabilities = model.predict_proba(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logloss = log_loss(y_test, predicted_probabilities)

    print(f"Accuracy: {accuracy:.4f}")
    print(f"Log Loss: {logloss:.4f}")

    def print_results():
        df_with_details = pd.read_csv(file_path)[
            ["Red Fighter", "Blue Fighter", "Result", "Date"]
        ]
        df_with_details["Date"] = pd.to_datetime(df_with_details["Date"])
        df_with_details.sort_values(by="Date", inplace=True)
        df_with_details = df_with_details[df_with_details["Date"] >= split_date]
        df_with_details.reset_index(drop=True, inplace=True)
        df_with_details["Result"] = label_encoder.fit_transform(df_with_details["Result"])

        # Convert the predicted and actual results back to the original labels if necessary.
        predicted_labels = label_encoder.inverse_transform(y_pred)
        actual_labels = label_encoder.inverse_transform(df_with_details["Result"])

        with open(
            os.path.join("data", "predicted_results.csv"), mode="w", newline=""
        ) as file:
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
    print_results()

    feature_importances = model.feature_importances_

    feature_importance_df = pd.DataFrame(
        {"Feature": X_train.columns, "Importance": feature_importances}
    )

    feature_importance_df = feature_importance_df.sort_values(
        "Importance", ascending=False
    )

    plt.figure(figsize=(10, 6))
    plt.barh(feature_importance_df["Feature"], feature_importance_df["Importance"])
    plt.xlabel("Importance")
    plt.ylabel("Feature")
    plt.title("Feature Importance")
    plt.show()

    print("Top 10 Important Features:")
    print(feature_importance_df.head(10))


if __name__ == "__main__":
    main()
