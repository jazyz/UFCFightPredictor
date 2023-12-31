# # for accuracy
# def objective(trial):
#     # Parameter suggestions by Optuna for tuning
#     param = {
#         "objective": "multiclass",  # or 'binary' for binary classification
#         "verbosity": -1,
#         "boosting_type": "gbdt",  # Default boosting type
#         "num_leaves": trial.suggest_int(
#             "num_leaves", 20, 100
#         ),  # more conservative than default
#         "learning_rate": trial.suggest_float(
#             "learning_rate", 0.02, 0.2, log=True
#         ),  # adjusted range for more granular learning rates
#         "min_child_samples": trial.suggest_int(
#             "min_child_samples", 10, 100
#         ),  # adjusted range to prevent overfitting
#         "subsample": trial.suggest_float(
#             "subsample", 0.5, 1.0
#         ),  # subsample ratio of the training instance
#         "colsample_bytree": trial.suggest_float(
#             "colsample_bytree", 0.5, 1.0
#         ),  # subsample ratio of columns when constructing each tree
#         "n_estimators": 100,  # Fixed number of estimators for simplicity
#         "num_class": 3,  # Replace with the actual number of classes in your dataset
#     }

#     # Splitting data for validation
#     X_train, X_valid, y_train, y_valid = train_test_split(
#         X_train_extended, y_train_extended, test_size=0.2, stratify=y_train_extended
#     )

#     # Creating LightGBM datasets
#     dtrain = lgb.Dataset(X_train, label=y_train)
#     dvalid = lgb.Dataset(X_valid, label=y_valid)

#     # Training model
#     model = lgb.train(
#         param,
#         dtrain,
#         valid_sets=[dvalid],
#         callbacks=[lgb.early_stopping(stopping_rounds=10)],
#     )

#     # Making predictions
#     preds = model.predict(X_valid, num_iteration=model.best_iteration)
#     pred_labels = np.argmax(preds, axis=1)  # For multiclass classification

#     # Calculate accuracy
#     accuracy = accuracy_score(y_valid, pred_labels)

#     return accuracy