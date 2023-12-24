import pandas as pd
import sys
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt

# Step 1: Read the data
df = pd.read_csv("detailed_fights.csv")
#df = df[(df['Red totalfights'] > 4) & (df['Blue totalfights'] > 4)]
# Step 2: Preprocess the data
# Assuming 'Result' is the target variable and the rest are features
label_encoder = LabelEncoder()
df["Result"] = label_encoder.fit_transform(df["Result"])
selected_columns=[
    "Result",
    # "Red totalfights",
    # "Blue totalfights",
    "Red elo",
    "Blue elo",
    "Red KD",
    "Blue KD",
    "Red Sig. str.",
    "Blue Sig. str.",
    "Red Total str.",
    "Blue Total str.",
    "Red Td",
    "Blue Td",
    "Red Sub. att",
    "Blue Sub. att",
    "Red Rev.",
    "Blue Rev.",
    "Red Ctrl",
    "Blue Ctrl",
    "Red Head",
    "Blue Head",
    "Red Body",
    "Blue Body",
    "Red Leg",
    "Blue Leg",
    "Red Distance",
    "Blue Distance",
    "Red Clinch",
    "Blue Clinch",
    "Red Ground",
    "Blue Ground",
    "Red Sig. str.%",
    "Blue Sig. str.%",
    "Red Total str.%",
    "Blue Total str.%",
    "Red Td%",
    "Blue Td%",
    "Red Head%",
    "Blue Head%",
    "Red Body%",
    "Blue Body%",
    "Red Leg%",
    "Blue Leg%",
    "Red Distance%",
    "Blue Distance%",
    "Red Clinch%",
    "Blue Clinch%",
    "Red Ground%",
    "Blue Ground%",
    #"Red Fighter",
    #"Blue Fighter",
    # "Red Sig. str",
    # "Blue Sig. str",
    # "Red Sig. str%",
    # "Blue Sig. str%",
    #"Title",
]
df = df[selected_columns]
X = df.drop(["Result"], axis=1)
y = df["Result"]

# Convert categorical variables if any
# X = pd.get_dummies(X)  # This line is optional and depends on your data

# Manual split based on percentage
split_index = int(len(df) * 0.9)
X_train, X_test = X[:split_index], X[split_index:]
y_train, y_test = y[:split_index], y[split_index:]

seed = 31

# Determine the new start index for the training data to skip the first 20%
prune_index = int(len(X_train) * 0.2)

# Update the training set to exclude the first 20%
X_train = X_train[prune_index:]
y_train = y_train[prune_index:]

# ... [Your previous code for reading the data and preprocessing] ...

# Step 1: Duplicate the training data
X_train_swapped = X_train.copy()
y_train_swapped = y_train.copy()

# Step 2: Rename the columns to swap 'Red' with 'Blue'
swap_columns = {}
for column in X_train.columns:
    if 'Red' in column:
        swap_columns[column] = column.replace('Red', 'Blue')
    elif 'Blue' in column:
        swap_columns[column] = column.replace('Blue', 'Red')

# Rename the columns in the copied DataFrame
X_train_swapped.rename(columns=swap_columns, inplace=True)

# Inverse the target variable for the swapped data
# Assuming 'win', 'loss', and 'draw' are the possible values
y_train_swapped = y_train_swapped.apply(lambda x: 2 if x == 1 else (1 if x == 2 else 0))

# Step 3: Concatenate the original and the modified copy to form the extended training set
X_train_extended = pd.concat([X_train, X_train_swapped], ignore_index=True)
y_train_extended = pd.concat([y_train, y_train_swapped], ignore_index=True)

# Now, X_train_extended and y_train_extended contain the original training data
# plus a copy with 'Red' and 'Blue' stats swapped and the target variable inversed.
# Invert the target variable for the swapped data
# Continue with model training using the extended training set
model = lgb.LGBMClassifier(random_state=seed)
model.fit(X_train_extended, y_train_extended)


y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy:.4f}")

df_with_names = pd.read_csv("detailed_fights.csv")[['Red Fighter', 'Blue Fighter']]
df_with_names = df_with_names.iloc[split_index:]

# Now you have the names aligned with your test data, make sure the indices match after the split.
df_with_names.reset_index(drop=True, inplace=True)

# Convert the predicted results back to the original labels if necessary.
predicted_labels = label_encoder.inverse_transform(y_pred)

# Output the predicted results with fighter names to a text file.
with open('predicted_results_with_names.txt', 'w') as f:
    f.write('Red Fighter,Blue Fighter,Predicted Result\n')
    for i in range(len(predicted_labels)):
        f.write(f"{df_with_names['Red Fighter'][i]} {predicted_labels[i]} against {df_with_names['Blue Fighter'][i]}\n")
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
