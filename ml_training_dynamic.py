import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt

data = pd.read_csv("dynamicfightstats.csv")

selected_columns = [
    "fighter_kd_differential",
    "fighter_str_differential",
    "fighter_td_differential",
    "fighter_sub_differential",
    "fighter_winrate",
    "fighter_winstreak",
    "fighter_totalfights",
    "fighter_totalwins",
    "fighter_titlefights",
    "opponent_kd_differential",
    "opponent_str_differential",
    "opponent_td_differential",
    "opponent_sub_differential",
    "opponent_winrate",
    "opponent_winstreak",
    "opponent_totalfights",
    "opponent_totalwins",
    "opponent_titlefights",
    "result",
]

data.dropna(subset=selected_columns, inplace=True)
data = data[selected_columns]

label_encoder = LabelEncoder()
data["result"] = label_encoder.fit_transform(data["result"])

X = data.drop("result", axis=1)
y = data["result"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestClassifier(random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy:.2f}")

feature_importances = model.feature_importances_

feature_importance_df = pd.DataFrame(
    {"Feature": X.columns, "Importance": feature_importances}
)

feature_importance_df = feature_importance_df.sort_values("Importance", ascending=False)


plt.figure(figsize=(10, 6))
plt.barh(feature_importance_df["Feature"], feature_importance_df["Importance"])
plt.xlabel("Importance")
plt.ylabel("Feature")
plt.title("Feature Importance")
plt.show()


predict_data = pd.read_csv("predictFights.csv")
print(predict_data)

predict_data.dropna(subset=selected_columns, inplace=True)
predict_data = predict_data[selected_columns]

X_predict = predict_data.drop("result", axis=1)

y_pred = model.predict(X_predict)

class_probabilities = model.predict_proba(X_predict)

predicted_results = label_encoder.inverse_transform(y_pred)

predict_data["predicted_result"] = predicted_results
for i, label in enumerate(label_encoder.classes_):
    predict_data[f"probability_{label}"] = class_probabilities[:, i]

print(predict_data)






