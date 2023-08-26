import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt


data = pd.read_csv("fightstats.csv")

data.dropna(
    subset=[
        "fighter_height",
        "fighter_weight",
        "fighter_reach",
        "fighter_dob",
        "opponent_height",
        "opponent_weight",
        "opponent_reach",
        "opponent_dob",
    ],
    inplace=True,
)

selected_columns = [
    "fighter_height",
    "fighter_weight",
    "fighter_reach",
    "fighter_dob",
    "opponent_height",
    "opponent_weight",
    "opponent_reach",
    "opponent_dob",
    "result",
]
data = data[selected_columns]

data["fighter_dob"] = pd.to_datetime(data["fighter_dob"]).dt.year
data["opponent_dob"] = pd.to_datetime(data["opponent_dob"]).dt.year

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
