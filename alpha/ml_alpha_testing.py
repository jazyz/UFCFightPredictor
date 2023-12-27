import csv
import pandas as pd
import sys
import lightgbm as lgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
from bayes_opt import BayesianOptimization
from sklearn.model_selection import cross_val_score

# Step 1: Read the data
df = pd.read_csv("detailed_fights.csv")
# df = df[(df['Red totalfights'] > 4) & (df['Blue totalfights'] > 4)]
# Step 2: Preprocess the data
# Assuming 'Result' is the target variable and the rest are features
label_encoder = LabelEncoder()
df["Result"] = label_encoder.fit_transform(df["Result"])
selected_columns = [
    "Result",
    "Red oppelo",
    "Blue oppelo",
    "Red wins",
    "Blue wins",
    "Red elo",
    "Blue elo",
    "Red losestreak",
    "Blue losestreak",
    "Red titlewins",
    "Blue titlewins",
    "Red KD",
    "Blue KD",
    "Red Sig. str.",
    "Blue Sig. str.",
    "Red Td",
    "Blue Td",
    "Red Sub. att",
    "Blue Sub. att",
    "Red Ctrl",
    "Blue Ctrl",
    "Red Sig. str.%",
    "Blue Sig. str.%",
    "Red Td%",
    "Blue Td%",
    
]
df = df[selected_columns]
X = df.drop(["Result"], axis=1)
y = df["Result"]

# Convert categorical variables if any
# X = pd.get_dummies(X)  # This line is optional and depends on your data

# Manual split based on percentage
split_index = int(len(df) * 0.8)
last_index = int(len(df) * 1)
X_train, X_test = X[:split_index], X[split_index:last_index]
y_train, y_test = y[:split_index], y[split_index:last_index]

seed = 42

# Determine the new start index for the training data to skip the first 20%
prune_index = int(len(X_train) * 0.1)


X_train = X_train[prune_index:]
y_train = y_train[prune_index:]

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

# Fit the model
model = lgb.LGBMClassifier(random_state=42)
model.fit(X_train_extended, y_train_extended)

# Make predictions and evaluate the model
y_pred = model.predict(X_test_extended)
predicted_probabilities = model.predict_proba(X_test_extended)
accuracy = accuracy_score(y_test_extended, y_pred)
print(f"Extended Test Set Accuracy: {accuracy:.4f}")

# Get the fighter names and actual results for the test set
df_with_details = pd.read_csv("detailed_fights.csv")[["Red Fighter", "Blue Fighter", "Result"]]
df_with_details = df_with_details.iloc[split_index:].reset_index(drop=True)

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
with open("predicted_results.csv", mode='w', newline='') as file:
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