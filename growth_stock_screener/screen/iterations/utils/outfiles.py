import pandas as pd
import os

# Determine the base path relative to this file's location
# __file__ gives the path to outfiles.py
# os.path.dirname gets the directory (utils/)
# os.path.abspath ensures it's absolute
# os.path.join(..., '..', '..') goes up two levels to growth_stock_screener/
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.abspath(os.path.join(UTILS_DIR, "..", "..", "json"))

# Ensure the JSON directory exists
os.makedirs(JSON_DIR, exist_ok=True)

def open_outfile(filename: str) -> pd.DataFrame:
    """Open json outfile data as pandas dataframe."""
    # Use the pre-calculated JSON_DIR
    json_path = os.path.join(JSON_DIR, f"{filename}.json")
    # Add error handling
    try:
        df = pd.read_json(json_path)
        return df
    except ValueError as e:
        # Handle potential empty or invalid JSON file
        print(f"Error reading JSON file {json_path}: {e}. Returning empty DataFrame.")
        return pd.DataFrame()
    except FileNotFoundError:
        print(f"Error: JSON file not found: {json_path}. Returning empty DataFrame.")
        return pd.DataFrame()


def create_outfile(data: pd.DataFrame, filename: str) -> None:
    """Serialize a pandas dataframe in JSON format and save in the project's json directory."""
    serialized_json = data.to_json(orient="records", indent=4) # Use records orient for better readability
    # Use the pre-calculated JSON_DIR
    outfile_path = os.path.join(JSON_DIR, f"{filename}.json")

    try:
        with open(outfile_path, "w") as outfile:
            outfile.write(serialized_json)
        # print(f"Data saved to {outfile_path}") # Optional confirmation
    except Exception as e:
         print(f"Error writing JSON file to {outfile_path}: {e}")
