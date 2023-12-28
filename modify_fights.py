import pandas as pd

# Reading the data from data\fight_details.csv file
df = pd.read_csv(r'data\fight_details.csv')

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
df = df[~df['Title'].str.contains("Women")]
df = df[~df['Title'].str.contains("Open")]
#df = df[~df['Title'].str.contains("Title")]
# Saving the modified DataFrame back to CSV or you can use it as is in your Python environment
df.to_csv('data\modified_fight_details.csv', index=False)

# Israel Adesanya,16,1131.9101928075177,12.0,240.0,168.0,-18.0,3.0,1.0,-25.01666666666667,240.0,45.0,19.0,176.0,246.0,-18.0,12.0,1.130486641768835,0.7995857264691455,-2.7634920634920634,1.130486641768835,0.9464661345739814,0.44584948993712337,0.7380345872896514,1.4338087582947758,-1.57277183600713,2.3772727272727274

