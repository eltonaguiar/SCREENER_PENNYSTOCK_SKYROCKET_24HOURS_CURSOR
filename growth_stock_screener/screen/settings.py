import multiprocessing

# TIMEFRAME SELECTION (for short-term skyrocket screening)
# Options: "24_hours", "3_days", "7_days", "2_weeks", "1_month"
TIMEFRAME = "24_hours"

# ITERATIONS (modify these values as desired)

# Price Range Settings (Used by short_term_momentum)
min_price_short_term: float = 0.10 # Default min for short-term
max_price_short_term: float = 4.00 # Default max for short-term

price_range_presets = {
    "skyrocket_under_4": {"min": 0.10, "max": 4.00}, # Current default
    "penny_stocks": {"min": 0.10, "max": 5.00},
    "sub_10_dollar": {"min": 0.50, "max": 10.00},
    # Add more presets as needed
}
active_price_preset = "skyrocket_under_4" # Default preset key

# Iteration 1: Relative Strength
min_rs: int = 90  # minimum RS rating to pass (integer from 0-100)

# Iteration 2: Liquidity
min_market_cap: float = 1000000000  # minimum market cap (USD)
min_price: float = 10               # minimum price (USD)
min_volume: int = 100000            # minimum 50-day average volume

# Iteration 3: Trend
trend_settings = {
    "Price >= 50-day SMA": True,               # set values to 'True' or 'False'
    "Price >= 200-day SMA": True,              # ^
    "10-day SMA >= 20-day SMA": True,          # ^ 
    "20-day SMA >= 50-day SMA": True,          # ^
    "Price within 50% of 52-week High": True,  # ^
}

# Iteration 4: Revenue Growth
min_growth_percent: float = 25  # minimum revenue growth for a quarter compared to the same quarter 1 year ago (percentage)
protected_rs: int = 97          # minimum RS rating to bypass revenue screen iteration (see README)

# Iteration 5: Institutional Accumulation
# (no parameters to modify)

# THREADS (manually set the following value if the screener reports errors during the "Trend" or "Institutional Accumulation" iterations)
# Recommended values are 1-10. Currently set to 3/4 the number of CPU cores on the system (with a max of 10)

# Thread Pool Size
threads: int = min(int(multiprocessing.cpu_count() * 0.75), 10)  # number of concurrent browser instances to fetch dynamic data (positive integer)

# CACHING
MAX_CACHE_AGE_DAYS: float = 1.0 # Maximum age of cached stock data in days. Set to 0 to disable caching.

# THIRD-PARTY APIs (Store securely - e.g., environment variables or .env file)
# --- Replace placeholder with your actual key ONLY for local testing --- 
TWELVEDATA_API_KEY: str = "6d39651259df48f6a4bb6f3c3755792f" # <<< YOUR KEY HERE (DO NOT COMMIT)

# PERFORMANCE
QUICK_MODE_FRACTION: float = 1.0 # Fraction of tickers to process (e.g., 0.25 for 25%). Set > 1.0 to disable.
