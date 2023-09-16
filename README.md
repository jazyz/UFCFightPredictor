# UFC Fight Predictor

UFCFightPredictor is a Python-based tool that leverages web scraping techniques to gather data from ufcstats.com and employs machine learning techniques like LightGBM (Light Gradient Boosting Machine) model for fight predictions. With a dataset comprising over 19,000 fights and data points, UFCFightPredictor has achieved a remarkable 64% accuracy, surpassing the community standard of 62%.

## Web Scraping

Using **Python BeautifulSoup** library we webscraped past history of all UFC and UFC related (TUF, DWCS, Pride, etc.) since 1993. From [ufcstats.com](ufcstats.com) going from each fighter's last name we look at their past fight history and gather data from their fights like number of strikes they landed vs number of strikes their opponent landed. Storing these values in an **SQL database** we're able to use these values later for data processing.

## Data Processing and Cleaning

### Feature Engineering

### Hyperparameter Tuning

### Trials

## Training the Model

UFCFightPredictor relies on LightGBM (Light Gradient Boosting Machine) due to its exceptional speed, efficiency in handling large datasets, and its ability to deliver high prediction accuracy, surpassing the community standard at 64%. LightGBM excels in capturing complex, non-linear relationships within UFC fight data, providing valuable insights into feature importance, and offering customization options for fine-tuning.

## Challenges

v1:
75% Accuracy on UFC 292 (9/12 fights predicted correctly) using power rating algorithm

v2:
Achieved 67% accuracy on test set with data leakage using a machine learning RandomForest model

v3:
Achieved 68% accuracy on test set with data leakage using Light Gradient Boosting Machine model

v4:
Achieved 64% accuracy on test set without data leakage using Light Gradient Boosting Machine model

Website at https://github.com/KoreaFriedChips/ufc
