"""
Incremental data processing utilities
Process only new fights instead of reprocessing entire dataset
"""
import pandas as pd
import os
from datetime import datetime


def get_last_processed_date(csv_path='data/modified_fight_details.csv'):
    """
    Get the most recent date from the processed fight data.
    Returns: datetime or None
    """
    if not os.path.exists(csv_path):
        print(f"No processed data found at {csv_path}")
        return None
    
    try:
        df = pd.read_csv(csv_path)
        if df.empty or 'Date' not in df.columns:
            return None
        
        # Use mixed format to handle both "December 16, 2023" and "2023-12-16"
        df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        last_date = df['Date'].max()
        return last_date
    except Exception as e:
        print(f"Error reading last processed date: {e}")
        return None


def process_new_fights_only(input_path='data/fight_details_date.csv',
                            output_path='data/modified_fight_details.csv',
                            last_processed_date=None):
    """
    Process only new fights and append to existing processed data.
    
    Args:
        input_path: Path to raw scraped data
        output_path: Path to processed data
        last_processed_date: Only process fights after this date
    
    Returns:
        Number of new fights processed
    """
    print("\n" + "="*60)
    print("Processing New Fights")
    print("="*60)
    
    # Read raw data
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        return 0
    
    df = pd.read_csv(input_path)
    
    # Filter to only new fights
    if last_processed_date:
        # Use mixed format to handle both "December 16, 2023" and "2023-12-16"
        df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        initial_count = len(df)
        df = df[df['Date'] > last_processed_date]
        print(f"Found {len(df)} new fights to process (out of {initial_count} total)")
    else:
        print(f"Processing all {len(df)} fights (no previous data)")
    
    if df.empty:
        print("✓ No new fights to process")
        return 0
    
    # Reset index after filtering (critical for row deletion logic)
    df = df.reset_index(drop=True)
    
    # Apply the same transformations as modify_fights.py
    df = apply_data_transformations(df)
    
    # Append to existing file or create new one
    output_exists = os.path.exists(output_path)
    
    if output_exists:
        print(f"Appending {len(df)} new fights to {output_path}")
        df.to_csv(output_path, mode='a', header=False, index=False)
    else:
        print(f"Creating new file at {output_path}")
        df.to_csv(output_path, index=False)
    
    print(f"✓ Successfully processed {len(df)} new fights")
    print("="*60 + "\n")
    
    return len(df)


def apply_data_transformations(df):
    """
    Apply the same transformations as modify_fights.py
    (Converting ratios, times, filtering, etc.)
    """
    
    # Function to convert "x of y" strings to a tuple of (x, x/y)
    def convert_ratio(value):
        if isinstance(value, str) and ' of ' in value:
            try:
                x, y = value.split(' of ')
                x, y = int(x), int(y)
                return x, x/y if y != 0 else 0
            except:
                return value, value
        else:
            return value, value
    
    # Function to convert "m:ss" time strings to total seconds
    def time_to_seconds(time_str):
        if isinstance(time_str, str) and ':' in time_str:
            try:
                minutes, seconds = time_str.split(':')
                return (int(minutes) * 60 + int(seconds))/60
            except:
                return time_str
        else:
            return time_str
    
    # Process each column
    for col in df.columns:
        # Convert columns with "x of y" pattern
        if df[col].apply(lambda x: isinstance(x, str) and ' of ' in x).any():
            df[col], new_col = zip(*df[col].apply(convert_ratio))
            df[f'{col}%'] = new_col
        
        # Convert columns with "m:ss" time format
        if df[col].apply(lambda x: isinstance(x, str) and ':' in x).any():
            df[col] = df[col].apply(time_to_seconds)
    
    # Identify rows to delete based on missing Winner
    rows_to_delete = set()
    i = 0
    while i < len(df) - 1:
        if pd.isna(df.iloc[i]['Winner']) or df.iloc[i]['Winner'] == '':
            rows_to_delete.add(i + 1)
            i += 2
        else:
            i += 1
    
    # Delete the identified rows
    if rows_to_delete:
        df = df.drop(list(rows_to_delete))
    
    # Delete specified columns if they exist
    columns_to_delete = ["Red Sig. str. %", "Red Td %", "Blue Sig. str. %", 
                        "Blue Td %", "Red Sig. str", "Blue Sig. str", 
                        "Red Sig. str%", "Blue Sig. str%"]
    existing_cols_to_delete = [col for col in columns_to_delete if col in df.columns]
    if existing_cols_to_delete:
        df = df.drop(columns=existing_cols_to_delete)
    
    # Filter out women's fights and open weight
    df = df[~df['Title'].str.contains("Women", na=False)]
    df = df[~df['Title'].str.contains("Open", na=False)]
    
    return df


def needs_full_reprocess(detailed_fights_path='data/detailed_fights.csv',
                         modified_fights_path='data/modified_fight_details.csv'):
    """
    Check if we need to fully reprocess all fights (for feature engineering).
    Returns True if detailed_fights.csv doesn't exist or is older than modified data.
    """
    if not os.path.exists(detailed_fights_path):
        return True
    
    if not os.path.exists(modified_fights_path):
        return True
    
    # Compare modification times
    detailed_mtime = os.path.getmtime(detailed_fights_path)
    modified_mtime = os.path.getmtime(modified_fights_path)
    
    return modified_mtime > detailed_mtime


if __name__ == "__main__":
    # Test the incremental processing
    last_date = get_last_processed_date()
    print(f"Last processed date: {last_date}")
    
    new_count = process_new_fights_only(last_processed_date=last_date)
    print(f"Processed {new_count} new fights")
