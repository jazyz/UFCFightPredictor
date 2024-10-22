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
import gym
from gym import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

class HyperparameterOptimizationEnv(gym.Env):
    """
    Custom Environment for Hyperparameter Optimization using RL
    """
    def __init__(self, X_train, y_train, X_val, y_val, n_actions=4):
        super(HyperparameterOptimizationEnv, self).__init__()
        
        # Define action and observation space
        # Actions: Adjust num_leaves, learning_rate, min_child_samples, subsample
        self.action_space = spaces.Discrete(n_actions)
        
        # Observation space: current hyperparameters
        # We'll represent hyperparameters as normalized values between 0 and 1
        self.observation_space = spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32)
        
        # Initialize hyperparameters
        self.hyperparams = {
            'num_leaves': 50,
            'learning_rate': 0.1,
            'min_child_samples': 30,
            'subsample': 0.8
        }
        
        # Training and validation data
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        
        # Episode limit
        self.max_steps = 20
        self.current_step = 0
        
    def reset(self):
        # Reset hyperparameters to initial values
        self.hyperparams = {
            'num_leaves': 50,
            'learning_rate': 0.1,
            'min_child_samples': 30,
            'subsample': 0.8
        }
        self.current_step = 0
        return self._get_obs()
    
    def _get_obs(self):
        # Normalize hyperparameters
        obs = np.array([
            (self.hyperparams['num_leaves'] - 20) / (100 - 20),
            np.log(self.hyperparams['learning_rate'] / 0.02) / np.log(0.2 / 0.02),
            (self.hyperparams['min_child_samples'] - 10) / (100 - 10),
            (self.hyperparams['subsample'] - 0.5) / (1.0 - 0.5)
        ], dtype=np.float32)
        return obs
    
    def step(self, action):
        # Define how each action modifies the hyperparameters
        if action == 0:
            self.hyperparams['num_leaves'] = min(self.hyperparams['num_leaves'] + 5, 100)
        elif action == 1:
            self.hyperparams['learning_rate'] = min(self.hyperparams['learning_rate'] * 1.1, 0.2)
        elif action == 2:
            self.hyperparams['min_child_samples'] = min(self.hyperparams['min_child_samples'] + 5, 100)
        elif action == 3:
            self.hyperparams['subsample'] = min(self.hyperparams['subsample'] + 0.05, 1.0)
        
        # Train and evaluate the model with current hyperparameters
        model = lgb.LGBMClassifier(
            num_leaves=int(self.hyperparams['num_leaves']),
            learning_rate=self.hyperparams['learning_rate'],
            min_child_samples=int(self.hyperparams['min_child_samples']),
            subsample=self.hyperparams['subsample'],
            objective='multiclass',
            num_class=2,
            verbosity=-1,
            random_state=42
        )
        
        model.fit(self.X_train, self.y_train)
        y_pred_proba = model.predict_proba(self.X_val)
        current_log_loss = log_loss(self.y_val, y_pred_proba)
        
        # Reward: inverse of log loss (since we want to minimize log loss)
        reward = -current_log_loss
        
        self.current_step += 1
        
        # Check if episode is done
        done = self.current_step >= self.max_steps
        
        # Optionally, you can add additional info
        info = {}
        
        return self._get_obs(), reward, done, info
    
    def render(self, mode='human'):
        print(f"Step: {self.current_step}")
        print(f"Current Hyperparameters: {self.hyperparams}")

def rl_hyperparameter_optimization(X_train, y_train, X_val, y_val, n_trials=20):
    env = HyperparameterOptimizationEnv(X_train, y_train, X_val, y_val)
    env = DummyVecEnv([lambda: env])
    
    # Initialize the PPO agent
    model = PPO('MlpPolicy', env, verbose=1)
    
    # Train the agent
    model.learn(total_timesteps=10000)
    
    # Collect the best hyperparameters based on rewards
    best_log_loss = float('inf')
    best_hyperparams = None
    
    for trial in range(n_trials):
        obs = env.reset()
        done = False
        total_reward = 0
        
        while not done:
            action, _states = model.predict(obs)
            obs, reward, done, info = env.step(action)
            total_reward += reward
        
        current_log_loss = -total_reward
        if current_log_loss < best_log_loss:
            best_log_loss = current_log_loss
            best_hyperparams = env.envs[0].hyperparams.copy()
    
    print(f"Best Hyperparameters from RL: {best_hyperparams}")
    print(f"Best Log Loss from RL: {best_log_loss}")
    
    return best_hyperparams, best_log_loss

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
        study.optimize(objective, n_trials=1)

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

    best_params_optuna = data_loaded["best_params"]
    best_score_optuna = data_loaded["best_score"]

    # Train model with Optuna best params
    model_optuna = lgb.LGBMClassifier(**best_params_optuna)
    model_optuna.fit(X_train_extended, y_train_extended)

    y_pred_optuna = model_optuna.predict(X_test)
    predicted_probabilities_optuna = model_optuna.predict_proba(X_test)
    accuracy_optuna = accuracy_score(y_test, y_pred_optuna)
    logloss_optuna = log_loss(y_test, predicted_probabilities_optuna)

    print(f"Optuna - Accuracy: {accuracy_optuna:.4f}")
    print(f"Optuna - Log Loss: {logloss_optuna:.4f}")

    # RL-Based Hyperparameter Optimization
    # Split a validation set from the training data
    X_train_rl, X_val_rl, y_train_rl, y_val_rl = train_test_split(
        X_train_extended, y_train_extended, test_size=0.2, random_state=42, shuffle=False
    )

    best_hyperparams_rl, best_log_loss_rl = rl_hyperparameter_optimization(
        X_train_rl, y_train_rl, X_val_rl, y_val_rl, n_trials=20
    )

    # Train model with RL best params
    model_rl = lgb.LGBMClassifier(**best_hyperparams_rl)
    model_rl.fit(X_train_extended, y_train_extended)

    y_pred_rl = model_rl.predict(X_test)
    predicted_probabilities_rl = model_rl.predict_proba(X_test)
    accuracy_rl = accuracy_score(y_test, y_pred_rl)
    logloss_rl = log_loss(y_test, predicted_probabilities_rl)

    print(f"RL - Accuracy: {accuracy_rl:.4f}")
    print(f"RL - Log Loss: {logloss_rl:.4f}")

    # Compare Optuna and RL results
    print("\nComparison of Optimization Methods:")
    print(f"Optuna - Log Loss: {logloss_optuna:.4f}")
    print(f"RL - Log Loss: {best_log_loss_rl:.4f}")

    # Proceed with your existing evaluation and visualization
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
        predicted_labels = label_encoder.inverse_transform(y_pred_optuna)
        actual_labels = label_encoder.inverse_transform(df_with_details["Result"])

        with open(
            os.path.join("data", "predicted_results_optuna.csv"), mode="w", newline=""
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
                max_probability = max(predicted_probabilities_optuna[i])

                writer.writerow(
                    [
                        df_with_details["Red Fighter"].iloc[i],
                        df_with_details["Blue Fighter"].iloc[i],
                        predicted_labels[i],
                        max_probability,  # Formatting as a percentage
                        actual_labels[i],
                    ]
                )
        
        # Similarly for RL predictions
        predicted_labels_rl = label_encoder.inverse_transform(y_pred_rl)
        with open(
            os.path.join("data", "predicted_results_rl.csv"), mode="w", newline=""
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
            for i in range(len(predicted_labels_rl)):
                max_probability = max(predicted_probabilities_rl[i])

                writer.writerow(
                    [
                        df_with_details["Red Fighter"].iloc[i],
                        df_with_details["Blue Fighter"].iloc[i],
                        predicted_labels_rl[i],
                        max_probability,  # Formatting as a percentage
                        actual_labels[i],
                    ]
                )

    print_results()

    # Feature Importance for Optuna Model
    feature_importances_optuna = model_optuna.feature_importances_

    feature_importance_df_optuna = pd.DataFrame(
        {"Feature": X_train.columns, "Importance": feature_importances_optuna}
    )

    feature_importance_df_optuna = feature_importance_df_optuna.sort_values(
        "Importance", ascending=False
    )

    plt.figure(figsize=(10, 6))
    plt.barh(feature_importance_df_optuna["Feature"], feature_importance_df_optuna["Importance"])
    plt.xlabel("Importance")
    plt.ylabel("Feature")
    plt.title("Feature Importance - Optuna Model")
    plt.show()

    print("Top 10 Important Features - Optuna Model:")
    print(feature_importance_df_optuna.head(10))

    # Feature Importance for RL Model
    feature_importances_rl = model_rl.feature_importances_

    feature_importance_df_rl = pd.DataFrame(
        {"Feature": X_train.columns, "Importance": feature_importances_rl}
    )

    feature_importance_df_rl = feature_importance_df_rl.sort_values(
        "Importance", ascending=False
    )

    plt.figure(figsize=(10, 6))
    plt.barh(feature_importance_df_rl["Feature"], feature_importance_df_rl["Importance"])
    plt.xlabel("Importance")
    plt.ylabel("Feature")
    plt.title("Feature Importance - RL Model")
    plt.show()

    print("Top 10 Important Features - RL Model:")
    print(feature_importance_df_rl.head(10))

if __name__ == "__main__":
    main()
