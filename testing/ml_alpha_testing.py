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
import optuna
from sklearn.metrics import log_loss

split_date = pd.to_datetime("2021-01-01") 
def main():
    file_path = os.path.join("data", "detailed_fights.csv")

def main(split_date = ""):    # Step 1: Read the data
    df = pd.read_csv(file_path)
    # df = df[(df['Red totalfights'] > 4) & (df['Blue totalfights'] > 4)]
    # Step 2: Preprocess the data
    # Assuming 'Result' is the target variable and the rest are features
    label_encoder = LabelEncoder()
    df["Result"] = label_encoder.fit_transform(df["Result"])
    selected_columns = df.columns.tolist()

    columns_to_remove = ["Red Fighter", "Blue Fighter", "Title", "Date"]
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

    selected_columns.append("Date")
            
    df = df[selected_columns]

    df["Date"] = pd.to_datetime(df["Date"])
    df.sort_values(by="Date", inplace=True)

    df = df[df["Date"] >= pd.to_datetime("2009-01-01")] 
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

    # Inverse the target variable for the swapped training data
    y_train_swapped = y_train_swapped.apply(lambda x: 2 if x == 1 else (1 if x == 2 else 0))

    # Concatenate the original and the modified copy to form the extended training set
    X_train_extended = pd.concat([X_train, X_train_swapped], ignore_index=True)
    y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)

    # Repeat the process for the test data
    X_test_swapped = X_test.copy()
    y_test_swapped = y_test.copy()
    X_test_swapped.rename(columns=swap_red_blue, inplace=True)
    y_test_swapped = y_test_swapped.apply(lambda x: 2 if x == 1 else (1 if x == 2 else 0))
    X_test_extended = pd.concat([X_test, X_test_swapped], ignore_index=True)
    y_test_extended = pd.concat([y_test, y_test_swapped], ignore_index=True)

    with open('data/best_params.json', 'r') as file:
        data_loaded = json.load(file)

    # Extracting the best parameters and score from the loaded data
    best_params = data_loaded['best_params']
    best_score = data_loaded['best_score']

    # with open(os.path.join("test_results", "results.txt"), "a") as f:
    #     f.write(f"Best params: {best_params}\n")

    model = lgb.LGBMClassifier(**best_params)
    # model = lgb.LGBMClassifier(random_state=seed)
    model.fit(X_train_extended, y_train_extended)

    # Make predictions and evaluate the model
    y_pred = model.predict(X_test_extended)
    predicted_probabilities = model.predict_proba(X_test_extended)
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
    df_with_details_swapped[["Red Fighter", "Blue Fighter"]] = df_with_details_swapped[["Blue Fighter", "Red Fighter"]]
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