from twelvedata import TDClient
import pandas as pd
import sys # To exit cleanly if error

# !!! IMPORTANT: Replace with your actual API key !!!
api_key = '6d39651259df48f6a4bb6f3c3755792f'

if api_key == 'YOUR_TWELVEDATA_API_KEY_PLACEHOLDER':
    print("Error: Please replace 'YOUR_TWELVEDATA_API_KEY_PLACEHOLDER' with your actual API key in test_twelve.py")
    sys.exit(1)

td = TDClient(apikey=api_key)
ticker_symbol = 'AMODW'
output_size = 63

print(f"Attempting to fetch data for {ticker_symbol} from Twelve Data...")

try:
    ts = td.time_series(
        symbol=ticker_symbol,
        interval='1day',
        outputsize=output_size,
        timezone='America/New_York'
    ).as_pandas()

    print(f'\nTicker: {ticker_symbol}, Interval: 1day, OutputSize: {output_size}')
    print(f'Data Length: {len(ts)}')
    if not ts.empty:
        print("\nData Head:")
        print(ts.head())
    else:
        print("\nReceived empty DataFrame.")

except Exception as e:
    print(f'\nError fetching {ticker_symbol} from Twelve Data: {e}') 