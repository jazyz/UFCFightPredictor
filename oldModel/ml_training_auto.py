import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
import featuretools as ft

# Load the dataset
data = pd.read_csv("elofightstats.csv")

# Convert the date column to datetime format
data['date'] = pd.to_datetime(data['date'], format='%b. %d, %Y')
data.replace("--", pd.NA, inplace=True)

# Filter the dataset
data = data[(data['fighter_totalfights'] > 2) & (data['opponent_totalfights'] > 2)]
data = data[pd.to_datetime(data["date"]).dt.year >= 2010]

# Select columns of interest
selected_columns = [
    "date",
    "fighter_kd_differential",
    "fighter_str_differential",
    "fighter_td_differential",
    "fighter_sub_differential",
    "fighter_winstreak",
    "fighter_losestreak",
    "fighter_age_deviation",
    "fighter_titlefights",
    "fighter_titlewins",
    "fighter_elo",
    "fighter_opp_avg_elo",
    "opponent_kd_differential",
    "opponent_str_differential",
    "opponent_td_differential",
    "opponent_sub_differential",
    "opponent_winstreak",
    "opponent_losestreak",
    "opponent_age_deviation",
    "opponent_titlefights",
    "opponent_titlewins",
    "opponent_elo",
    "opponent_opp_avg_elo",
    "result",
]

# Drop rows with missing values in selected columns
data.dropna(subset=selected_columns, inplace=True)
data = data[selected_columns]

# Encode the target variable
label_encoder = LabelEncoder()
data["result"] = label_encoder.fit_transform(data["result"])

# Split the data into training and test sets
train_data = data[data['date'] < '2023-06-01']
test_data = data[(data['date'] >= '2023-06-01')]

X_train = train_data.drop(["result", "date"], axis=1)
y_train = train_data["result"]

X_test = test_data.drop(["result", "date"], axis=1)
y_test = test_data["result"]

# Create Featuretools EntitySet
es = ft.EntitySet(id="fighters_data")

# Define Fighters Entity
es = es.entity_from_dataframe(
    entity_id="fighters",
    dataframe=train_data,
    index="fighter_name",  # Assuming fighter_name is a unique identifier
)

# Define Opponents Entity
es = es.entity_from_dataframe(
    entity_id="opponents",
    dataframe=train_data,
    index="opponent_name",  # Assuming opponent_name is a unique identifier
)

# Define the main data Entity
es = es.entity_from_dataframe(
    entity_id="data",
    dataframe=train_data,  # Use the main dataset
    index="id",  # Assuming "id" is a unique identifier for each row
    time_index="date",  # Assuming "date" is the time index
)

# Define relationships
relationship_fighters = ft.Relationship(
    es["fighters"]["fighter_name"],
    es["data"]["fighter_name"],
)

relationship_opponents = ft.Relationship(
    es["opponents"]["opponent_name"],
    es["data"]["opponent_name"],
)

# Use Featuretools for automated feature generation with selected columns
feature_defs_fighters, features_fighters = ft.dfs(
    entityset=es,
    target_entity="fighters",
    agg_primitives=["mean", "sum", "std"],  # Choose appropriate aggregation functions
    max_depth=2,  # Adjust the max_depth as needed
    trans_primitives=["subtract_numeric"],  # Add more if necessary
    verbose=True,  # Print feature generation progress
    features_only=True,  # Get features only, not the full dataframe
)

feature_defs_opponents, features_opponents = ft.dfs(
    entityset=es,
    target_entity="opponents",
    agg_primitives=["mean", "sum", "std"],  # Choose appropriate aggregation functions
    max_depth=2,  # Adjust the max_depth as needed
    trans_primitives=["subtract_numeric"],  # Add more if necessary
    verbose=True,  # Print feature generation progress
    features_only=True,  # Get features only, not the full dataframe
)

# Merge the generated features back into your main dataset
X_train = X_train.merge(features_fighters, left_on="fighter_name", right_index=True)
X_train = X_train.merge(features_opponents, left_on="opponent_name", right_index=True)

# Train the LightGBM model
seed = 42
model = lgb.LGBMClassifier(random_state=seed)
model.fit(X_train, y_train)

# Evaluate the model
X_test = test_data.drop(["result", "date"], axis=1)
y_test = test_data["result"]

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy:.4f}")

# Rest of your code for predictions, feature importance, and plotting
# ...
