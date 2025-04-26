import yfinance as yf
import pandas as pd
import ta
import time
from tqdm import tqdm
import os
import pickle
from datetime import datetime, timedelta
import screen.settings as settings # Import settings
import numpy as np # Add numpy import
from twelvedata import TDClient # Import Twelve Data client

# Constants
# PRICE_LIMIT = 4.0 # Replaced by settings
VOLUME_SURGE_FACTOR = 2
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
BREAKOUT_DAYS = 20
VOLUME_AVG_DAYS = 10
RSI_WINDOW = 14
BBANDS_WINDOW = 20
ATR_WINDOW = 14
CACHE_DIR = "growth_stock_screener/cache"

# Minimum data length required for indicators
MIN_INDICATOR_LENGTH = max(RSI_WINDOW, BBANDS_WINDOW, ATR_WINDOW, VOLUME_AVG_DAYS, BREAKOUT_DAYS) + 1

# Create cache directory if it doesn't exist
os.makedirs(CACHE_DIR, exist_ok=True)

# Initialize Twelve Data Client (if key is provided)
td_client = None
if settings.TWELVEDATA_API_KEY and settings.TWELVEDATA_API_KEY != "YOUR_TWELVEDATA_API_KEY_PLACEHOLDER":
    try:
        td_client = TDClient(apikey=settings.TWELVEDATA_API_KEY)
        print("INFO: Twelve Data client initialized.")
    except Exception as e:
        print(f"Warning: Failed to initialize Twelve Data client: {e}")
else:
    print("INFO: Twelve Data API key not provided or is placeholder. Twelve Data fallback disabled.")

# --- Scoring Weights Definition ---
SCORING_WEIGHTS = {
    "24_hours": {
        "description": "Focuses on immediate reversal/breakout potential.",
        "weights": {
            "Volume Surge (>2x Avg)": 40,
            "RSI Extreme (<30 or >70)": 30,
            "Breakout (New 20d High)": 30
        }
    },
    "3_days": {
        "description": "Looks for high volatility and strong near-term momentum.",
        "weights": {
            "Volume Surge (>2x Avg)": 30,
            "Breakout (New 20d High)": 20,
            "High ATR (>5% of Price)": 25,
            "RSI Momentum (>70)": 25
        }
    },
    "7_days": {
        "description": "Balances consolidation (squeeze) with momentum and potential institutional interest.",
        "weights": {
            "Bollinger Band Squeeze (<5% Width)": 35,
            "Volume Surge (>2x Avg)": 25,
            "RSI Extreme (<30 or >70)": 25,
            "Institutional Ownership (>5%)": 15 # Bonus
        }
    },
    "2_weeks": {
        "description": "Targets potential short squeezes and continuation plays.",
        "weights": {
            "Bollinger Band Squeeze (<5% Width)": 25,
            "High Short Interest (>15% Float)": 25,
            "Institutional Ownership (>5%)": 15, # Bonus
            "Volume Surge (>2x Avg)": 20,
            "RSI Momentum (>70)": 15
        }
    },
    "1_month": {
        "description": "Focuses on potential catalysts, short squeeze potential, and momentum.",
        "weights": {
            "Catalyst Proxy (>15% move in 5d)": 25,
            "High Short Interest (>15% Float)": 25,
            "Institutional Ownership (>5%)": 15, # Bonus
            "Volume Surge (>2x Avg)": 20,
            "RSI Momentum (>70)": 15
        }
    }
}

# Error handling for yfinance - Removed yf.pdr_override()
# yf.pdr_override()

def fetch_stock_data(ticker, period="3mo", interval="1d"):
    """Fetches historical stock data using yfinance, with Twelve Data as failover."""
    # --- Try yfinance first (with cache) ---
    yf_data = _fetch_yfinance_data(ticker, period, interval)

    if yf_data is not None and len(yf_data) >= MIN_INDICATOR_LENGTH:
        # print(f"[Fetcher] Using yfinance data for {ticker} (Length: {len(yf_data)})") # Debug
        return yf_data
    # else: print(f"[Fetcher] yfinance data insufficient for {ticker} (Length: {len(yf_data) if yf_data is not None else 0}). Trying Twelve Data...") # Debug

    # --- If yfinance failed or insufficient, try Twelve Data --- 
    if td_client:
        td_data = _fetch_twelvedata(ticker, interval)
        if td_data is not None and len(td_data) >= MIN_INDICATOR_LENGTH:
             # print(f"[Fetcher] Using Twelve Data for {ticker} (Length: {len(td_data)})") # Debug
             return td_data
        # else: print(f"[Fetcher] Twelve Data also insufficient for {ticker} (Length: {len(td_data) if td_data is not None else 0})") # Debug

    # --- If both failed or insufficient, return whatever yfinance gave (or None) ---
    # This allows calculate_indicators to print the specific warning if needed
    # print(f"[Fetcher] Both sources failed/insufficient for {ticker}. Returning yfinance result.") # Debug
    return yf_data

def _fetch_yfinance_data(ticker, period, interval):
    """Internal function to fetch data from yfinance using cache."""
    cache_enabled = settings.MAX_CACHE_AGE_DAYS > 0
    max_age_seconds = settings.MAX_CACHE_AGE_DAYS * 24 * 60 * 60
    cache_filename = f"{ticker}_{period}_{interval}_yf.pkl" # Suffix for clarity
    cache_filepath = os.path.join(CACHE_DIR, cache_filename)

    # Check cache first
    if cache_enabled and os.path.exists(cache_filepath):
        try:
            file_mod_time = os.path.getmtime(cache_filepath)
            if (time.time() - file_mod_time) < max_age_seconds:
                with open(cache_filepath, 'rb') as f:
                    data = pickle.load(f)
                    if isinstance(data, pd.DataFrame): # Check if it's a DataFrame (even empty)
                        if not data.empty and not all(col in data.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume']):
                            print(f"Warning: yfinance Cached data for {ticker} missing columns. Refetching.")
                        else:
                            # print(f"Cache hit for yfinance {ticker}") # Debug
                            return data # Return even if empty, fetch_stock_data decides
                    else:
                        print(f"Warning: Invalid yfinance cached data for {ticker}. Refetching.")
        except Exception as e:
            print(f"Error reading yfinance cache for {ticker}: {e}. Refetching.")
            try: os.remove(cache_filepath) 
            except OSError: pass

    # Fetch fresh from yfinance
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period, interval=interval, auto_adjust=True)
        # Ensure required columns exist if not empty
        if not data.empty and not all(col in data.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume']):
             print(f"Warning: Missing expected yfinance columns for {ticker}")
             # Don't cache potentially incomplete data, return empty df? Or None?
             # Returning None aligns with previous error handling.
             return None
        # Cache the result (even if empty, indicates fetch was attempted)
        if cache_enabled:
            try:
                with open(cache_filepath, 'wb') as f:
                    pickle.dump(data, f)
            except Exception as e:
                print(f"Error writing yfinance cache for {ticker}: {e}")
        return data
    except Exception as e:
        # Mute common yfinance errors for invalid tickers during bulk runs?
        # print(f"Error fetching yfinance data for {ticker}: {e}")
        # Cache failure? Return None
        if cache_enabled:
             try:
                 # Create an empty DataFrame to cache the failure for a short time?
                 # For now, just don't cache error.
                 pass
             except Exception as ce:
                 print(f"Error trying to cache yfinance fetch error state for {ticker}: {ce}")
        return None # Indicate failure

def _fetch_twelvedata(ticker, interval='1day'):
    """Internal function to fetch data from Twelve Data."""
    # Map interval format if needed (yfinance '1d' vs Twelve Data '1day')
    td_interval = interval if interval != '1d' else '1day' 
    # Calculate output size needed based on MIN_INDICATOR_LENGTH
    # Add buffer (e.g., 5 extra days) as exact trading days vary
    output_size = MIN_INDICATOR_LENGTH + 5 
    
    print(f"Attempting Twelve Data fetch for {ticker} ({output_size} days)...") # Info
    try:
        ts = td_client.time_series(
            symbol=ticker,
            interval=td_interval,
            outputsize=output_size,
            timezone='America/New_York' # Or configure timezone
        ).as_pandas()

        # --- Data Cleaning/Validation for Twelve Data --- 
        if ts.empty:
            return ts # Return empty df if API returns no data
            
        # Ensure standard OHLCV columns exist (TD uses lowercase)
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in ts.columns for col in required_cols):
             print(f"Warning: Twelve Data for {ticker} missing columns: {list(ts.columns)}. Cannot use.")
             return None
             
        # Rename columns to match yfinance output (TitleCase)
        ts.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }, inplace=True)
        
        # Select only the required columns
        ts = ts[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        # Convert index to datetime if it's not already (it should be)
        ts.index = pd.to_datetime(ts.index)
        
        # Sort by date ascending (TD often returns descending)
        ts.sort_index(ascending=True, inplace=True)
        
        return ts
        
    except Exception as e:
        print(f"Error fetching Twelve Data for {ticker}: {e}")
        return None

# --- Fetch Ticker Info (with Caching) ---
def fetch_ticker_info(ticker):
    """Fetches Ticker.info data, utilizing a simple cache."""
    cache_enabled = settings.MAX_CACHE_AGE_DAYS > 0
    max_age_seconds = settings.MAX_CACHE_AGE_DAYS * 24 * 60 * 60
    cache_filename = f"{ticker}_info.pkl"
    cache_filepath = os.path.join(CACHE_DIR, cache_filename)

    # Check cache
    if cache_enabled and os.path.exists(cache_filepath):
        try:
            file_mod_time = os.path.getmtime(cache_filepath)
            if (time.time() - file_mod_time) < max_age_seconds:
                with open(cache_filepath, 'rb') as f:
                    info = pickle.load(f)
                    if isinstance(info, dict):
                        return info
        except Exception as e:
            print(f"Error reading info cache for {ticker}: {e}. Refetching.")
            try:
                os.remove(cache_filepath)
            except OSError:
                pass

    # Fetch fresh
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Save to cache
        if cache_enabled and isinstance(info, dict) and info: # Only cache if valid dict
            try:
                with open(cache_filepath, 'wb') as f:
                    pickle.dump(info, f)
            except Exception as e:
                print(f"Error writing info cache for {ticker}: {e}")
        return info
    except Exception as e:
        # yfinance often throws errors for .info if ticker is invalid/delisted
        # print(f"Error fetching .info for {ticker}: {e}")
        return None # Return None, don't cache error

def calculate_indicators(ticker, data):
    """Calculates technical indicators needed for screening."""
    # Check data validity *before* calculating indicators
    if data is None or data.empty:
        # print(f"[Indicators] No data provided for {ticker}. Skipping.") # Debug
        return None
    
    indicators = {}
    try:
        # Ensure sufficient data length for calculations
        # min_required_length = max(RSI_WINDOW, BBANDS_WINDOW, ATR_WINDOW, VOLUME_AVG_DAYS, BREAKOUT_DAYS) + 1
        if len(data) < MIN_INDICATOR_LENGTH:
             # Warning if data was provided but still too short
             print(f"Warning [Ticker: {ticker}]: Insufficient data length ({len(data)} found, {MIN_INDICATOR_LENGTH} required) for indicator calculation. Skipping.")
             return None

        # --- Start Indicator Calculations ---
        indicators['current_price'] = data['Close'].iloc[-1]

        # RSI
        indicators['rsi'] = ta.momentum.RSIIndicator(data['Close'], window=RSI_WINDOW).rsi().iloc[-1]

        # Volume Surge
        avg_volume = data['Volume'].iloc[-VOLUME_AVG_DAYS:-1].mean() # Exclude current day's volume from average
        indicators['volume_surge'] = data['Volume'].iloc[-1] > VOLUME_SURGE_FACTOR * avg_volume if avg_volume > 0 else False

        # Breakout
        indicators['breakout'] = data['Close'].iloc[-1] > data['Close'].iloc[-BREAKOUT_DAYS:-1].max()

        # Bollinger Bands Squeeze
        bbands = ta.volatility.BollingerBands(data['Close'], window=BBANDS_WINDOW)
        bb_h = bbands.bollinger_hband()
        bb_l = bbands.bollinger_lband()
        bb_m = bbands.bollinger_mavg()
        # Calculate Bollinger Band Width (relative to middle band)
        bb_width = (bb_h - bb_l) / bb_m
        indicators['bb_squeeze'] = bb_width.iloc[-1] < 0.05 # Threshold for squeeze (e.g., < 5% width)
        indicators['bb_width'] = bb_width.iloc[-1] # Store the actual width for potential use

        # Average True Range (ATR) as Percentage of Price
        atr = ta.volatility.AverageTrueRange(data['High'], data['Low'], data['Close'], window=ATR_WINDOW).average_true_range()
        indicators['atr_percent'] = (atr.iloc[-1] / indicators['current_price']) * 100 if indicators['current_price'] > 0 else 0

        # --- Fetch Short Interest Data (from Ticker Info) ---
        ticker_info = fetch_ticker_info(ticker) # Use cached info fetch
        indicators['short_interest_pct'] = None
        indicators['short_ratio'] = None
        if ticker_info:
            shares_short = ticker_info.get('sharesShort')
            float_shares = ticker_info.get('floatShares')
            short_ratio = ticker_info.get('shortRatio')
            if shares_short is not None and float_shares is not None and float_shares > 0:
                indicators['short_interest_pct'] = (shares_short / float_shares) * 100
            if short_ratio is not None:
                 indicators['short_ratio'] = short_ratio

            # --- Institutional Ownership ---
            inst_own_pct = ticker_info.get('heldPercentInstitutions')
            if inst_own_pct is not None:
                 indicators['inst_own_pct'] = inst_own_pct * 100 # Store as percentage
            else:
                 indicators['inst_own_pct'] = None

        # --- Catalyst Proxy (Recent Price Action) ---
        indicators['catalyst_proxy_flag'] = False
        days_for_catalyst_check = 5 # Check price change over last 5 days
        if len(data['Close']) > days_for_catalyst_check:
            price_now = data['Close'].iloc[-1]
            price_then = data['Close'].iloc[-(days_for_catalyst_check + 1)]
            if price_then > 0:
                percent_change = ((price_now - price_then) / price_then) * 100
                if abs(percent_change) > 15: # Threshold e.g. > 15% move in 5 days
                     indicators['catalyst_proxy_flag'] = True
                     indicators['catalyst_proxy_pct_change'] = percent_change # Store change

        # --- Momentum and Sharpe Ratio ---
        indicators['momentum_6m'] = None
        indicators['sharpe_ratio'] = None
        if 'Close' in data.columns and len(data['Close']) > 1:
            returns = data['Close'].pct_change().dropna()
            if not returns.empty:
                # Momentum (6-month cumulative return)
                momentum_period = 126 # Approx 6 months (trading days)
                if len(returns) >= momentum_period:
                    # Calculate cumulative product for the period
                    momentum_return = (1 + returns.tail(momentum_period)).prod() - 1
                    indicators['momentum_6m'] = momentum_return * 100 # Store as percentage

                # Sharpe Ratio (annualized, risk-free rate assumed 0)
                if len(returns) > 1:
                    std_dev = returns.std()
                    if std_dev is not None and std_dev != 0: # Avoid division by zero
                         sharpe = np.sqrt(252) * returns.mean() / std_dev
                         indicators['sharpe_ratio'] = sharpe

    except Exception as e:
        # Add ticker symbol to error message
        print(f"Error calculating indicators for {ticker} (data length {len(data)}): {e}")
        # ... (traceback optional)
        return None
    return indicators

def screen_stocks(ticker_list, timeframe):
    """Screens a list of tickers for potential short-term price surges based on the selected timeframe."""
    results = []
    # Get price limits from settings
    min_price_limit = settings.min_price_short_term
    max_price_limit = settings.max_price_short_term
    print(f"\nScreening {len(ticker_list)} stocks for potential skyrocket candidates...")
    print(f"  Timeframe: {timeframe}, Price Range: ${min_price_limit:.2f} - ${max_price_limit:.2f}")

    # Use tqdm for progress bar
    for ticker in tqdm(ticker_list, desc="Screening Progress"):
        data = fetch_stock_data(ticker, period="3mo")
        if data is None or data.empty:
            # Add a small delay even on cache miss/error to prevent hammering API
            time.sleep(0.05)
            continue

        # Pass ticker to calculate_indicators
        indicators = calculate_indicators(ticker, data)
        if indicators is None or pd.isna(indicators.get('current_price')):
             continue

        # Apply Price Filter using settings
        current_price = indicators.get('current_price')
        # Explicitly check for None *before* numerical comparison
        if current_price is None or pd.isna(current_price):
            continue # Skip if no price
        # Now safe to compare
        if not (min_price_limit <= current_price < max_price_limit):
            continue

        # Calculate Score based on timeframe
        score = 0
        passing_criteria = [] # Keep track of which criteria passed

        # --- Timeframe-Specific Scoring Logic ---
        if timeframe == "24_hours":
            # Weights: Volume Surge (40%), RSI (30%), Breakout (30%)
            if indicators.get('volume_surge'):
                score += 40
                passing_criteria.append("VolumeSurge")
            # Use RSI extremes (oversold or overbought)
            rsi_val = indicators.get('rsi')
            # Add explicit None check
            if rsi_val is not None and not pd.isna(rsi_val):
                if rsi_val < RSI_OVERSOLD:
                    score += 30
                    passing_criteria.append(f"RSI Oversold ({rsi_val:.1f})")
                elif rsi_val > RSI_OVERBOUGHT:
                    score += 30
                    passing_criteria.append(f"RSI Overbought ({rsi_val:.1f})")
            if indicators.get('breakout'):
                score += 30
                passing_criteria.append("Breakout")

        elif timeframe == "3_days":
            # Weights: Volume Surge (30%), Breakout (20%), ATR > 5% (25%), RSI > 70 (25%)
            if indicators.get('volume_surge'):
                score += 30
                passing_criteria.append("VolumeSurge")
            if indicators.get('breakout'):
                 score += 20
                 passing_criteria.append("Breakout")
            atr_pct = indicators.get('atr_percent')
            # Add explicit None check
            if atr_pct is not None and not pd.isna(atr_pct) and atr_pct > 5:
                 score += 25
                 passing_criteria.append(f"High ATR ({atr_pct:.1f}%)")
            rsi_val = indicators.get('rsi')
            # Add explicit None check
            if rsi_val is not None and not pd.isna(rsi_val) and rsi_val > RSI_OVERBOUGHT:
                score += 25
                passing_criteria.append(f"RSI Momentum ({rsi_val:.1f})")

        elif timeframe == "7_days":
            # Weights: BB Squeeze (35%), Vol Surge (25%), RSI Extremes (25%), Inst Own >5% (15%)
            if indicators.get('bb_squeeze'):
                score += 35 # Adjusted weight
                passing_criteria.append(f"BBSqueeze (W:{indicators.get('bb_width', -1):.3f})")
            if indicators.get('volume_surge'):
                score += 25 # Adjusted weight
                passing_criteria.append("VolumeSurge")
            rsi_val = indicators.get('rsi')
            if rsi_val is not None and not pd.isna(rsi_val):
                if rsi_val < RSI_OVERSOLD:
                    score += 25 # Adjusted weight
                    passing_criteria.append(f"RSI Oversold ({rsi_val:.1f})")
                elif rsi_val > RSI_OVERBOUGHT:
                    score += 25 # Adjusted weight
                    passing_criteria.append(f"RSI Overbought ({rsi_val:.1f})")
            # Institutional Ownership Bonus
            inst_pct = indicators.get('inst_own_pct')
            if inst_pct is not None and not pd.isna(inst_pct) and inst_pct > 5:
                 score += 15
                 passing_criteria.append(f"InstOwn ({inst_pct:.1f}%)")

        elif timeframe == "2_weeks":
            # Weights: BB Squeeze (25%), High Short Int (>15%) (25%), Inst Own >5% (15%), Vol Surge (20%), RSI Momentum (15%)
            if indicators.get('bb_squeeze'):
                score += 25 # Adjusted weight
                passing_criteria.append(f"BBSqueeze (W:{indicators.get('bb_width', -1):.3f})")
            si_pct = indicators.get('short_interest_pct')
            # Add explicit None check
            if si_pct is not None and not pd.isna(si_pct) and si_pct > 15:
                 score += 25 # Adjusted weight
                 passing_criteria.append(f"HighShortInt ({si_pct:.1f}%)")
            # Institutional Ownership Bonus
            inst_pct = indicators.get('inst_own_pct')
            # Add explicit None check
            if inst_pct is not None and not pd.isna(inst_pct) and inst_pct > 5:
                 score += 15
                 passing_criteria.append(f"InstOwn ({inst_pct:.1f}%)")
            if indicators.get('volume_surge'):
                 score += 20
                 passing_criteria.append("VolumeSurge")
            rsi_val = indicators.get('rsi')
            if rsi_val is not None and not pd.isna(rsi_val) and rsi_val > RSI_OVERBOUGHT:
                score += 15 # Adjusted weight
                passing_criteria.append(f"RSI Momentum ({rsi_val:.1f})")

        elif timeframe == "1_month":
            # Weights: Catalyst Proxy (25%), High Short Int (>15%) (25%), Inst Own >5% (15%), Vol Surge (20%), RSI Momentum (15%)
            if indicators.get('catalyst_proxy_flag'):
                 score += 25 # Adjusted weight
                 change_pct = indicators.get('catalyst_proxy_pct_change', 0)
                 passing_criteria.append(f"CatalystProxy ({change_pct:.1f}% 5d)")
            si_pct = indicators.get('short_interest_pct')
            # Add explicit None check
            if si_pct is not None and not pd.isna(si_pct) and si_pct > 15:
                 score += 25 # Adjusted weight
                 passing_criteria.append(f"HighShortInt ({si_pct:.1f}%)")
             # Institutional Ownership Bonus
            inst_pct = indicators.get('inst_own_pct')
            # Add explicit None check
            if inst_pct is not None and not pd.isna(inst_pct) and inst_pct > 5:
                 score += 15
                 passing_criteria.append(f"InstOwn ({inst_pct:.1f}%)")
            if indicators.get('volume_surge'):
                 score += 20
                 passing_criteria.append("VolumeSurge")
            rsi_val = indicators.get('rsi')
            if rsi_val is not None and not pd.isna(rsi_val) and rsi_val > RSI_OVERBOUGHT:
                score += 15 # Adjusted weight
                passing_criteria.append(f"RSI Momentum ({rsi_val:.1f})")

        # --- End Timeframe-Specific Scoring Logic ---

        if score > 0:
            # Add new indicators to results
            results.append({
                'ticker': ticker,
                'price': f"{indicators['current_price']:.2f}",
                'rsi': f"{indicators.get('rsi', 'N/A'):.1f}" if pd.notna(indicators.get('rsi')) else 'N/A',
                'volume_surge': indicators.get('volume_surge', False),
                'breakout': indicators.get('breakout', False),
                'bb_squeeze': indicators.get('bb_squeeze', False),
                'atr_percent': f"{indicators.get('atr_percent', 'N/A'):.1f}" if pd.notna(indicators.get('atr_percent')) else 'N/A',
                'short_int_pct': f"{indicators.get('short_interest_pct', 'N/A'):.1f}" if pd.notna(indicators.get('short_interest_pct')) else 'N/A',
                'short_ratio': f"{indicators.get('short_ratio', 'N/A'):.1f}" if pd.notna(indicators.get('short_ratio')) else 'N/A',
                'catalyst_proxy': indicators.get('catalyst_proxy_flag', False),
                'momentum_6m': f"{indicators.get('momentum_6m', 'N/A'):.1f}" if pd.notna(indicators.get('momentum_6m')) else 'N/A',
                'sharpe_ratio': f"{indicators.get('sharpe_ratio', 'N/A'):.2f}" if pd.notna(indicators.get('sharpe_ratio')) else 'N/A',
                'inst_own_pct': f"{indicators.get('inst_own_pct', 'N/A'):.1f}" if pd.notna(indicators.get('inst_own_pct')) else 'N/A',
                'score': score,
                'criteria': ", ".join(passing_criteria),
                'timeframe': timeframe
            })
        # Reduced sleep delay as cache should help
        time.sleep(0.05)

    # Convert to DataFrame and sort
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        # Define columns order if desired
        cols = ['ticker', 'price', 'score', 'timeframe', 'criteria', 'rsi', 'volume_surge', 'breakout', 'bb_squeeze', 'atr_percent', 'short_int_pct', 'short_ratio', 'catalyst_proxy', 'momentum_6m', 'sharpe_ratio', 'inst_own_pct']
        # Ensure all columns exist in the dataframe before selection, adding missing ones as NA
        for col in cols:
            if col not in results_df.columns:
                results_df[col] = pd.NA
        results_df = results_df.sort_values(by='score', ascending=False)
        results_df = results_df[cols] # Reorder columns
        output_filename = f"skyrocket_candidates_{timeframe}.csv"
        print(f"\nSaving {len(results_df)} potential candidates to {output_filename}")
        results_df.to_csv(output_filename, index=False)
    else:
        print("\nNo stocks passed the screening criteria.")

    return results_df

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Use a small list of low-priced stocks for testing
    test_tickers = ["SNDL", "AMC", "NAKD", "CTRM", "ZOM", "BB", "GME", "EXPR", "CLOV", "WKHS"] # Example list
    test_timeframe = "24_hours"
    screen_stocks(test_tickers, test_timeframe)

    test_timeframe = "7_days" # Test another timeframe
    # screen_stocks(test_tickers, test_timeframe) # Uncomment to test 