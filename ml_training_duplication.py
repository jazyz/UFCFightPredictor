import pandas as pd
import sys
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt

data = pd.read_csv("elofightstats.csv")
data['date'] = pd.to_datetime(data['date'], format='%b. %d, %Y')
# data = data.sort_values(by='date')
data.replace("--", pd.NA, inplace=True)
data = data[(data['fighter_totalfights'] > 2) & (data['opponent_totalfights'] > 2)]
data = data[pd.to_datetime(data["date"]).dt.year>=2010]
# data["fighter_dob"] = pd.to_datetime(data["fighter_dob"]).dt.year
# data["opponent_dob"] = pd.to_datetime(data["opponent_dob"]).dt.year
selected_columns = [
    "date",
    "fighter_kd_differential",
    "fighter_str_differential",
    "fighter_td_differential",
    "fighter_sub_differential",
    # "fighter_winrate",
    "fighter_winstreak",
    "fighter_losestreak",
    # "fighter_totalfights",
    # "fighter_totalwins",
    "fighter_age_deviation",
    "fighter_titlefights",
    "fighter_titlewins",
    "fighter_opp_avg_elo",
    "fighter_elo",
    "opponent_kd_differential",
    "opponent_str_differential",
    "opponent_td_differential",
    "opponent_sub_differential",
    # "opponent_winrate",
    "opponent_winstreak",
    "opponent_losestreak",
    # "opponent_totalfights",
    # "opponent_totalwins",
    "opponent_age_deviation",   
    "opponent_titlefights",
    "opponent_titlewins",
    "opponent_elo",
    "opponent_opp_avg_elo",
    # "fighter_dob",
    # "opponent_dob",
    "result",
]

# if predicting past event
# event_to_drop = "UFC 292: Sterling vs. O'Malley"
# data = data[data['event'] != event_to_drop]

data.dropna(subset=selected_columns, inplace=True)
data = data[selected_columns]

columns_to_difference = [
    "kd_differential",
    "str_differential",
    "td_differential",
    "sub_differential",
    "age_deviation",
    "titlefights",
    "titlewins",
    "elo",
    "opp_avg_elo",
    "winstreak",
    "losestreak",
]

# for column in columns_to_difference:
#     fighter_column = f"fighter_{column}"
#     opponent_column = f"opponent_{column}"
#     data[f"{column}_differential"] = data[fighter_column] - data[opponent_column]


label_encoder = LabelEncoder()
data["result"] = label_encoder.fit_transform(data["result"])

X = data.drop("result", axis=1)
y = data["result"]

seed=42

# print(len(X))
# split_index = int(len(X) * 0.98)
# print(len(X)-split_index)
# X_train, X_test = X[:split_index], X[split_index:]
# y_train, y_test = y[:split_index], y[split_index:]

# X_train, X_test, y_train, y_test = train_test_split(
#     X, y, test_size=0.2, random_state=42
# )

train_data = data[data['date'] < '2023-06-01']
test_data = data[(data['date'] >= '2023-06-01')]

X_train = train_data.drop(["result","date"], axis=1)
y_train = train_data["result"]

X_test = test_data.drop(["result","date"], axis=1)
y_test = test_data["result"]

print(len(X_train))
print(len(X_test))
fighter_train = X_train.copy()

for col in fighter_train.columns:
    fighter_train.rename(columns={col: col.replace("fighter_", "tmp_")}, inplace=True)

for col in fighter_train.columns:
    fighter_train.rename(columns={col: col.replace("opponent_", "fighter_")}, inplace=True)

for col in fighter_train.columns:
    fighter_train.rename(columns={col: col.replace("tmp_", "opponent_")}, inplace=True)

fighter_train.reset_index(drop=True, inplace=True)

combined_X_train = pd.DataFrame()

for col in fighter_train.columns:
    combined_X_train[col] = pd.concat([fighter_train[col], X_train[col]], ignore_index=True)

combined_y_train = y_train._append(y_train, ignore_index=True)

num_original_rows = len(y_train)
num_duplicated_rows = len(combined_y_train) - num_original_rows

for i in range(num_original_rows, len(combined_y_train)):
    if combined_y_train[i] == 1:
        combined_y_train[i] = 3
    elif combined_y_train[i] == 3:
        combined_y_train[i] = 1
    
print(len(combined_X_train))
print(len(combined_y_train))
model = lgb.LGBMClassifier(random_state=seed)
model.fit(combined_X_train, combined_y_train)

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy:.4f}")

output_file = open("ml_elo.txt", "w")
original_stdout = sys.stdout
sys.stdout = output_file
pd.set_option("display.max_columns", None)

predict_data = pd.read_csv("predict_fights_elo.csv")
predict_data.replace("--", pd.NA, inplace=True)

# predict_data["fighter_dob"] = pd.to_datetime(predict_data["fighter_dob"]).dt.year
# predict_data["opponent_dob"] = pd.to_datetime(predict_data["opponent_dob"]).dt.year

predict_data.dropna(subset=selected_columns, inplace=True)
predict_data = predict_data[selected_columns]

# for column in columns_to_difference:
#     fighter_column = f"fighter_{column}"
#     opponent_column = f"opponent_{column}"
#     predict_data[f"{column}_differential"] = predict_data[fighter_column] - predict_data[opponent_column]

X_predict = predict_data.drop(["result","date"], axis=1)

y_pred = model.predict(X_predict)

class_probabilities = model.predict_proba(X_predict)

predicted_results = label_encoder.inverse_transform(y_pred)

predict_data["predicted_result"] = predicted_results
for i, label in enumerate(label_encoder.classes_):
    predict_data[f"probability_{label}"] = class_probabilities[:, i]

print(predict_data)

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