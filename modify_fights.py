import argparse
import unicodedata
from pathlib import Path

import pandas as pd


DATA_DIR = Path("data")


def parse_args():
    parser = argparse.ArgumentParser(description="Clean raw UFC fight details for feature generation.")
    parser.add_argument("--input-fights", default=DATA_DIR / "fight_details_date.csv", type=Path)
    parser.add_argument("--output-fights", default=DATA_DIR / "modified_fight_details.csv", type=Path)
    parser.add_argument(
        "--include-womens-fights",
        action="store_true",
        help=(
            "keep women's bouts instead of matching the men-only preprocessing "
            "default, including women-vs-women catchweight rows whose titles do "
            "not contain Women"
        ),
    )
    parser.add_argument(
        "--include-openweight-fights",
        action="store_true",
        help="keep openweight bouts instead of matching the historical preprocessing default",
    )
    return parser.parse_args()


ARGS = parse_args()

# Reading the data from data\fight_details.csv file
df = pd.read_csv(ARGS.input_fights)


def canonical_name(value):
    ascii_name = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_name.strip().lower().split())


def known_women_fighter_names(source_df):
    women_title = source_df["Title"].fillna("").str.contains("Women", case=False, regex=False)
    women_rows = source_df[women_title]
    return set(women_rows["Red Fighter"].map(canonical_name)) | set(
        women_rows["Blue Fighter"].map(canonical_name)
    )


def known_women_pair_mask(source_df, known_women):
    red = source_df["Red Fighter"].map(canonical_name)
    blue = source_df["Blue Fighter"].map(canonical_name)
    return red.isin(known_women) & blue.isin(known_women)

# Function to convert "x of y" strings to a tuple of (x, x/y)
def convert_ratio(value):
    if isinstance(value, str) and ' of ' in value:
        x, y = value.split(' of ')
        x, y = int(x), int(y)
        return x, x/y if y != 0 else 0
    else:
        return value, value

# Function to convert "m:ss" time strings to total seconds
def time_to_seconds(time_str):
    if isinstance(time_str, str) and ':' in time_str:
        minutes, seconds = time_str.split(':')
        return (int(minutes) * 60 + int(seconds))/60
    else:
        return time_str

# Iterating through each column in the DataFrame
for col in df.columns:
    # Convert columns with "x of y" pattern
    if df[col].apply(lambda x: isinstance(x, str) and ' of ' in x).any():
        df[col], new_col = zip(*df[col].apply(convert_ratio))
        df[f'{col}%'] = new_col

    # Convert columns with "m:ss" time format
    if df[col].apply(lambda x: isinstance(x, str) and ':' in x).any():
        df[col] = df[col].apply(time_to_seconds)


# Identify rows to delete based on 'Draw' being True
rows_to_delete = set()
i = 0
while i < len(df) - 1:
    if pd.isna(df.loc[i, 'Winner']) or df.loc[i, 'Winner'] == '':
        rows_to_delete.add(i + 1)
        i += 2  
    else:
        i += 1 

# Delete the identified rows
df = df.drop(list(rows_to_delete))

# Deleting the old percentage columns as specified
columns_to_delete = ["Red Sig. str. %", "Red Td %", "Blue Sig. str. %", "Blue Td %", "Red Sig. str", "Blue Sig. str", "Red Sig. str%", "Blue Sig. str%"]
df = df.drop(columns=columns_to_delete)
if not ARGS.include_womens_fights:
    known_women = known_women_fighter_names(df)
    women_title = df["Title"].str.contains("Women", na=False)
    df = df[~(women_title | known_women_pair_mask(df, known_women))]
if not ARGS.include_openweight_fights:
    df = df[~df['Title'].str.contains("Open", na=False)]
#df = df[~df['Title'].str.contains("Title")]
# Saving the modified DataFrame back to CSV or you can use it as is in your Python environment
ARGS.output_fights.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(ARGS.output_fights, index=False)
