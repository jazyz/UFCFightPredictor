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
from sklearn.metrics import log_loss, brier_score_loss

file_path = os.path.join("data", "detailed_fights.csv")

def main(split_date = "2021-01-01", calibration=None):    # Step 1: Read the data
    split_date = pd.to_datetime(split_date)
    df = pd.read_csv(file_path)
    # df = df[(df['Red totalfights'] > 4) & (df['Blue totalfights'] > 4)]
    # Step 2: Preprocess the data
    # Assuming 'Result' is the target variable and the rest are features
    label_encoder = LabelEncoder()
    df["Result"] = label_encoder.fit_transform(df["Result"])

    df["Date"] = pd.to_datetime(df["Date"])
    df.sort_values(by="Date", inplace=True)

    df = df[df["Date"] >= pd.to_datetime("2009-01-01")]

    selected_columns = df.columns.tolist()

    columns_to_remove = ["Red Fighter", "Blue Fighter", "Title", "Date"]
    selected_columns = [col for col in selected_columns if col not in columns_to_remove]

    # correlations computed on training rows only, so feature selection can't see the test set
    corr_matrix = df[df["Date"] < split_date][selected_columns].corr().abs()

    # Select upper triangle of correlation matrix
    upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))

    # Find features with correlation greater than 95%
    to_drop = [column for column in upper_tri.columns if any(upper_tri[column] > 0.95)]

    # keep the feature set Red/Blue-symmetric for the swap augmentation:
    # drop a correlated column together with its mirror, never one side alone
    def mirror(col):
        if col.startswith("Red "):
            return "Blue " + col[len("Red "):]
        if col.startswith("Blue "):
            return "Red " + col[len("Blue "):]
        return col
    to_drop = sorted({c for col in to_drop for c in (col, mirror(col)) if c in df.columns})

    # Drop highly correlated features
    df.drop(to_drop, axis=1, inplace=True)

    # Make sure to update the 'selected_columns' to reflect the dropped columns
    # oppdiff columns re-admitted 2026-08-31 to match ml_ensemble.py; their sign
    # is flipped in the swapped copies below (they carry Red-minus-Blue values)
    selected_columns = [column for column in selected_columns if column not in to_drop]

    selected_columns.append("Date")

    df = df[selected_columns]
    # print(df.head())
    # Split based on the date
    train_df = df[df["Date"] < split_date]
    test_df = df[df["Date"] >= split_date]

    X_train = train_df.drop(["Result", "Date"], axis=1)
    y_train = train_df["Result"]
    X_test = test_df.drop(["Result", "Date"], axis=1)
    y_test = test_df["Result"]

    # Prepare the train and test data for duplication and swapping
    X_train_swapped = X_train.copy()
    y_train_swapped = y_train.copy()

    # Define a function to swap 'Red' and 'Blue' in column names
    def swap_red_blue(column_name):
        return column_name.replace("Red", "temp").replace("Blue", "Red").replace("temp", "Blue")

    # Swap the column names for the training data
    X_train_swapped.rename(columns=swap_red_blue, inplace=True)
    # oppdiff columns are Red-minus-Blue: renaming can't touch them, so negate
    for column in X_train.columns:
        if "oppdiff" in column:
            X_train_swapped[column] = X_train[column] * -1

    # Inverse the target variable for the swapped training data
    y_train_swapped = y_train_swapped.apply(lambda x: 0 if x == 1 else 1)

    # Concatenate the original and the modified copy to form the extended training set
    X_train_extended = pd.concat([X_train, X_train_swapped], ignore_index=True)
    y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)

    # Repeat the process for the test data
    X_test_swapped = X_test.copy()
    y_test_swapped = y_test.copy()
    X_test_swapped.rename(columns=swap_red_blue, inplace=True)
    for column in X_test.columns:
        if "oppdiff" in column:
            X_test_swapped[column] = X_test[column] * -1
    y_test_swapped = y_test_swapped.apply(lambda x: 0 if x == 1 else 1)
    X_test_extended = pd.concat([X_test, X_test_swapped], ignore_index=True)
    y_test_extended = pd.concat([y_test, y_test_swapped], ignore_index=True)

    with open('data/best_params.json', 'r') as file:
        data_loaded = json.load(file)

    # Extracting the best parameters and score from the loaded data
    best_params = data_loaded['best_params']
    best_score = data_loaded['best_score']
    # top trials saved by ml_alpha_date.py; averaged as a small ensemble to avoid
    # betting on a single winner-of-the-search (older files only have best_params)
    best_params_list = data_loaded.get('best_params_list', [best_params])

    def fit_members(X, y):
        members = []
        for i, member_params in enumerate(best_params_list):
            # distinct seed per member, matching ml_ensemble.py's deployed ensemble
            m = lgb.LGBMClassifier(**member_params, random_state=42 + i)
            m.fit(X, y)
            members.append(m)
        return members

    def ensemble_proba(members, X):
        return np.mean([m.predict_proba(X) for m in members], axis=0)

    def fit_temperature(oof_p, oof_y):
        # mirrors ml_ensemble.py: logit(q) = a * logit(p), symmetric (no intercept)
        from scipy.optimize import minimize_scalar
        p = np.clip(oof_p, 1e-6, 1 - 1e-6)
        logits = np.log(p / (1 - p))
        def nll(a):
            q = np.clip(1.0 / (1.0 + np.exp(-a * logits)), 1e-9, 1 - 1e-9)
            return -np.mean(oof_y * np.log(q) + (1 - oof_y) * np.log(1 - q))
        return float(minimize_scalar(nll, bounds=(0.25, 4.0), method='bounded').x)

    def oof_temperature():
        # each walk-forward split fits its own calibrator on its own train window
        # (out-of-fold), so backtest probabilities match deployed serving without
        # leaking the deployed calibrator's future data into past predictions
        from sklearn.model_selection import TimeSeriesSplit
        oof_p, oof_y = [], []
        for tr_idx, va_idx in TimeSeriesSplit(n_splits=5).split(X_train):
            X_fold, y_fold = X_train.iloc[tr_idx], y_train.iloc[tr_idx]
            X_sw = X_fold.rename(columns=swap_red_blue)
            for column in X_fold.columns:
                if "oppdiff" in column:
                    X_sw[column] = X_fold[column] * -1
            members = fit_members(
                pd.concat([X_fold, X_sw], ignore_index=True),
                pd.concat([y_fold, y_fold.apply(lambda v: 0 if v == 1 else 1)],
                          ignore_index=True))
            oof_p.append(ensemble_proba(members, X_train.iloc[va_idx])[:, 1])
            oof_y.append(y_train.iloc[va_idx].to_numpy())
        return fit_temperature(np.concatenate(oof_p), np.concatenate(oof_y))

    # with open(os.path.join("test_results", "results.txt"), "a") as f:
    #     f.write(f"Best params: {best_params}\n")

    if calibration:
        # hold out the most recent 15% of the (time-ordered) training fights to fit
        # a probability calibrator; the model trains on the remaining 85%
        calib_start = int(len(X_train) * 0.85)
        X_fit, X_cal = X_train.iloc[:calib_start], X_train.iloc[calib_start:]
        y_fit, y_cal = y_train.iloc[:calib_start], y_train.iloc[calib_start:]

        def extend(X, y):
            X_sw = X.copy()
            X_sw.rename(columns=swap_red_blue, inplace=True)
            for column in X.columns:
                if "oppdiff" in column:
                    X_sw[column] = X[column] * -1
            y_sw = y.apply(lambda x: 0 if x == 1 else 1)
            return pd.concat([X, X_sw], ignore_index=True), pd.concat([y, y_sw], ignore_index=True)

        X_fit_ext, y_fit_ext = extend(X_fit, y_fit)
        X_cal_ext, y_cal_ext = extend(X_cal, y_cal)

        members = fit_members(X_fit_ext, y_fit_ext)

        p_cal = ensemble_proba(members, X_cal_ext)[:, 1]
        if calibration == "isotonic":
            from sklearn.isotonic import IsotonicRegression
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_cal, y_cal_ext)
            calibrate = lambda p: np.clip(iso.predict(p), 1e-6, 1 - 1e-6)
        elif calibration == "platt":
            from sklearn.linear_model import LogisticRegression
            def logit(p):
                p = np.clip(p, 1e-6, 1 - 1e-6)
                return np.log(p / (1 - p))
            lr = LogisticRegression()
            lr.fit(logit(p_cal).reshape(-1, 1), y_cal_ext)
            calibrate = lambda p: lr.predict_proba(logit(p).reshape(-1, 1))[:, 1]
        else:
            raise ValueError(f"unknown calibration method: {calibration}")

        raw_probs = ensemble_proba(members, X_test_extended)
        p_win = calibrate(raw_probs[:, 1])
        predicted_probabilities = np.column_stack([1 - p_win, p_win])
        y_pred = np.argmax(predicted_probabilities, axis=1)
        print(f"raw   logloss {log_loss(y_test_extended, raw_probs):.4f}  brier {brier_score_loss(y_test_extended, raw_probs[:, 1]):.4f}")
        print(f"calib logloss {log_loss(y_test_extended, predicted_probabilities):.4f}  brier {brier_score_loss(y_test_extended, p_win):.4f}")
    else:
        members = fit_members(X_train_extended, y_train_extended)

        # Make predictions and evaluate the model
        predicted_probabilities = ensemble_proba(members, X_test_extended)
        # apply this split's own OOF temperature, matching deployed serving
        a = oof_temperature()
        print(f"temperature calibrator for split {split_date.date()}: a={a:.3f}")
        p_win = np.clip(predicted_probabilities[:, 1], 1e-6, 1 - 1e-6)
        p_win = 1.0 / (1.0 + np.exp(-a * np.log(p_win / (1 - p_win))))
        predicted_probabilities = np.column_stack([1 - p_win, p_win])
        y_pred = np.argmax(predicted_probabilities, axis=1)

    accuracy = accuracy_score(y_test_extended, y_pred)
    print(f"Extended Test Set Accuracy: {accuracy:.4f}")

    # Get the fighter names and actual results for the test set
    df_with_details = pd.read_csv(file_path)[
        ["Red Fighter", "Blue Fighter", "Result", "Date"]
    ]
    df_with_details["Date"] = pd.to_datetime(df_with_details["Date"])
    df_with_details.sort_values(by="Date", inplace=True)
    df_with_details = df_with_details[df_with_details["Date"] >= split_date]
    df_with_details.reset_index(drop=True, inplace=True)

    # Duplicate and swap 'Red' and 'Blue' in the second half of df_with_details
    df_with_details_swapped = df_with_details.copy()
    df_with_details_swapped[["Red Fighter", "Blue Fighter"]] = df_with_details_swapped[["Blue Fighter", "Red Fighter"]].values
    # with the corners swapped, the actual result flips too
    df_with_details_swapped["Result"] = df_with_details_swapped["Result"].replace({"win": "loss", "loss": "win"})
    df_with_details_extended = pd.concat([df_with_details, df_with_details_swapped], ignore_index=True)

    # Encode the Result in the extended details
    df_with_details_extended["Result"] = label_encoder.transform(df_with_details_extended["Result"])

    # Convert the predicted and actual results back to the original labels if necessary
    predicted_labels = label_encoder.inverse_transform(y_pred)
    actual_labels = label_encoder.inverse_transform(df_with_details_extended["Result"])

    # Write predictions to a CSV file
    with open(os.path.join("data", "predicted_results.csv"), mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Red Fighter", "Blue Fighter", "Predicted Result", "Probability"])
        for i in range(len(predicted_labels)):
            max_probability = max(predicted_probabilities[i])
            writer.writerow([
                df_with_details_extended['Red Fighter'].iloc[i], 
                df_with_details_extended['Blue Fighter'].iloc[i], 
                predicted_labels[i], 
                max_probability,  # Formatting as a percentage
            ])

    # Print completion message
    print("done")

    # feature_importances = model.feature_importances_

    # feature_importance_df = pd.DataFrame(
    #     {"Feature": X_train.columns, "Importance": feature_importances}
    # )

    # feature_importance_df = feature_importance_df.sort_values("Importance", ascending=False)

    # plt.figure(figsize=(10, 6))
    # plt.barh(feature_importance_df["Feature"], feature_importance_df["Importance"])
    # plt.xlabel("Importance")
    # plt.ylabel("Feature")
    # plt.title("Feature Importance")
    # plt.show()

if __name__ == "__main__":
    main()