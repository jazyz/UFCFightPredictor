# The Pipeline

## Data

### Web Scraping

All of the data was scraped from ufcstats.com. Previously, we had scraped data for each fighter as well as their fight histories and statistics, stored in an SQL database. However, in order to get more detailed fight statistics, we had to revamp the scraper entirely. We have now collected stats such as strike accuracy, control time, and submissions attempts for every fight from 1994 to 2023.

### Data Processing and Cleaning

First, we need to clean the data, removing incomplete values, outdated fights, and duplicated data that was scraped. We also need to process all the data in a way which our machine learning model can understand, and retrieve all the raw numbers.

### Feature Engineering

With around 15 base stats for each fight, we now process the statistics in order to create expressive and predictive features. In order to predict a fight, we need the past fight histories of both fighters. The data scraped tells us which fighter is in the red corner and which fighter is in the blue corner. For simplicity in code, we call them Red and Blue.

By looping through all fights from past to present, we can dynamically compute stats from their past fights and then use those stats to predict a current fight. By doing this, we make sure that only data accessible before a fight has happened is used to predict a fight. Without doing this, our model accuracy would be up to 80+%, a mistake that some predictors with absurdly high accuracy may have.

Over 180+ features are engineering from these 15 base stats. For each base stat, such as significant strikes landed, we compute the number landed per minute, the accuracy of strikes, the difference between how many strikes you landed and how many strikes you took, the percentages of strikes you dodged, etc. Then, these stats are accumulated and processed into a weighted average which weighs recent fights much heavier than past, in order to get an accurate picture of each fighter's skills at different points in time. These in-depth statistics are then fed into the LightGBM ML model to be used to predict fights.

## Model

### LightGBM

We chose LightGBM (Light Gradient Boosting Machine), a tree-based learning algorithm, due to its exceptional speed, efficiency, and predicting power. LightGBM excels in capturing complex, non-linear relationships within UFC fight data, providing valuable insights into feature importance and tuning. With the new Alpha model, our accuracies were much more consistent than before. With much less features in our previous model, changing a few features could

### Feature Selection

With so many features, it's important to select those which actually help the model. We prune out features which have high correlation with each other, as well as features which have low impact on the model. This reduces noise and helps the model pick out the correct percentages.

### Hyperparameter Tuning and Trials

LightGBM allows you to fine-tune your model, setting parameters such as learning rate, number of leaves in a tree, etc. These can all have great impacts on the predictions that the model makes. We utilized the optuna library to run trails in order to select the best hyperparameters for the model. Our current model accuracy is 64%.

## Results

Testing on the fight cards in 2023, we ran 10 separate trials with different tuned hyperparameters, and averaged an $1100 final bankroll starting from $1000. We used a conservative 0.05 Kelly Criterion betting strategy, which helps us determine what fraction of our bankroll to wager on each bet. Testing on the fight cards from both 2022 and 2023 with a more risky 0.1 Kelly Criterion, we average a final bankroll of $1600, while maxing out at around $3000. We found that our model is consistently gaining money and can sometimes go up to $2000 or $3000 over a longer period of time, while only going down to around $750. Starting with $1000, for 73/86 or 85% of the trials, the model goes above $1000, going down only 13/86 or 15% of the trials.
