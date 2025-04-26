# growth_stock_screener/report_generator.py

import pandas as pd
import numpy as np
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, timedelta
import time # Import the time module
import math # For ceiling function

# Import functions from our momentum screener (assuming it's callable this way)
# Need to handle potential circular imports or structure changes if necessary.
# For simplicity, assume direct import works for now.
# If ModuleNotFoundError occurs, we might need to adjust imports/structure.
try:
    from screen.iterations.short_term_momentum import fetch_ticker_info, fetch_stock_data, SCORING_WEIGHTS
    import screen.settings as settings
except ImportError:
    print("Warning: Could not import from screen.iterations.short_term_momentum. Ensure structure is correct.")
    # Define dummy functions if import fails to allow basic structure creation
    def fetch_ticker_info(ticker): return {}
    def fetch_stock_data(ticker, period, interval): return pd.DataFrame()
    SCORING_WEIGHTS = {}
    class settings:
        min_price_short_term = 0
        max_price_short_term = 0
        TIMEFRAME = "N/A"

# --- Helper Functions --- 

def format_market_cap(market_cap):
    if market_cap is None or pd.isna(market_cap):
        return 'N/A'
    if market_cap >= 1e12:
        return f"${market_cap / 1e12:.2f} T"
    if market_cap >= 1e9:
        return f"${market_cap / 1e9:.2f} B"
    if market_cap >= 1e6:
        return f"${market_cap / 1e6:.2f} M"
    if market_cap >= 1e3:
        return f"${market_cap / 1e3:.2f} K"
    return f"${market_cap:.2f}"

def format_sma(current_price, sma_value):
    if sma_value is None or pd.isna(sma_value) or current_price is None or pd.isna(current_price) or sma_value == 0:
        return 'N/A'
    diff_pct = ((current_price - sma_value) / sma_value) * 100
    color_class = 'positive' if diff_pct >= 0 else 'negative'
    return f'<span class="{color_class}">${sma_value:.2f} ({diff_pct:+.1f}%)</span>'

def calculate_performance(hist_data):
    """Calculates performance over standard periods from historical data."""
    perf = {
        'perf_1w': None, 'perf_1m': None, 'perf_3m': None,
        'perf_6m': None, 'perf_1y': None
    }
    if hist_data is None or hist_data.empty or len(hist_data['Close']) < 2:
        return perf

    end_price = hist_data['Close'].iloc[-1]
    periods = {
        'perf_1w': 5, 'perf_1m': 21, 'perf_3m': 63,
        'perf_6m': 126, 'perf_1y': 252
    }

    for key, days_back in periods.items():
        if len(hist_data) > days_back:
            start_price = hist_data['Close'].iloc[-(days_back + 1)]
            if start_price > 0:
                perf[key] = ((end_price - start_price) / start_price) * 100
        elif len(hist_data) > 1: # If less than period, calculate vs start
             start_price = hist_data['Close'].iloc[0]
             if start_price > 0:
                 perf[key] = ((end_price - start_price) / start_price) * 100

    return perf

def calculate_technicals(hist_data):
    """Calculates additional technicals needed for the report."""
    tech = {
        'sma50': None, 'sma200': None,
        'pct_from_52w_high': None, 'pct_from_52w_low': None
    }
    if hist_data is None or hist_data.empty:
        return tech

    close_prices = hist_data['Close']
    if len(close_prices) >= 50:
        tech['sma50'] = close_prices.rolling(window=50).mean().iloc[-1]
    if len(close_prices) >= 200:
        tech['sma200'] = close_prices.rolling(window=200).mean().iloc[-1]

    if not close_prices.empty:
        current_price = close_prices.iloc[-1]
        high_52w = close_prices.max() # Max over the period fetched (e.g., 1 year)
        low_52w = close_prices.min()

        if high_52w > 0:
            tech['pct_from_52w_high'] = ((current_price - high_52w) / high_52w) * 100
        if low_52w > 0:
             tech['pct_from_52w_low'] = ((current_price - low_52w) / low_52w) * 100
             
    return tech

# --- Main Report Generation Function --- 

def generate_html_report(csv_filepath, output_filename="stock_report.html"):
    """Generates an HTML report from the screener results CSV file."""
    print(f"\nGenerating HTML report from {csv_filepath}...")

    try:
        results_df = pd.read_csv(csv_filepath)
        if results_df.empty:
             print("Report Generation Warning: Results CSV file is empty.")
             # Generate a report indicating no results?
             results_df = pd.DataFrame(columns=['ticker']) # Ensure loop runs zero times
             # return # Or just exit?

    except FileNotFoundError:
        print(f"Report Generation Error: Results CSV file not found at {csv_filepath}")
        return
    except Exception as e:
        print(f"Report Generation Error reading CSV {csv_filepath}: {e}")
        return

    # Prepare data list for template
    stocks_data = []
    total_stocks = len(results_df)
    print(f"Fetching additional data for {total_stocks} stock(s) for the report...")

    # Use tqdm for progress if many stocks
    from tqdm import tqdm
    for index, row in tqdm(results_df.iterrows(), total=total_stocks, desc="Report Data Fetch"):
        ticker = row['ticker']
        stock_report_data = row.to_dict() # Start with CSV data

        # Fetch additional required data
        # Use longer period for performance/technicals
        hist_data_1y = fetch_stock_data(ticker, period="1y", interval="1d") 
        ticker_info = fetch_ticker_info(ticker)

        # Add info and calculated metrics
        stock_report_data['info'] = ticker_info if ticker_info else {}
        perf_metrics = calculate_performance(hist_data_1y)
        tech_metrics = calculate_technicals(hist_data_1y)
        stock_report_data.update(perf_metrics)
        stock_report_data.update(tech_metrics)
        
        # Convert price from CSV string back to float for calculations/formatting
        try:
            stock_report_data['price'] = float(row['price'])
        except (ValueError, TypeError):
            stock_report_data['price'] = None # Handle potential errors
        
        # Convert other potential string numerics back
        for col in ['rsi', 'atr_percent', 'short_int_pct', 'short_ratio', 'momentum_6m', 'sharpe_ratio', 'inst_own_pct']:
             try:
                  stock_report_data[col] = float(row[col]) if pd.notna(row[col]) and row[col] != 'N/A' else None
             except (ValueError, TypeError):
                  stock_report_data[col] = None
        
        # Convert boolean-like strings
        for col in ['volume_surge', 'breakout', 'bb_squeeze', 'catalyst_proxy']:
            stock_report_data[col] = str(row[col]).lower() == 'true'

        # Calculate Score 1-10
        original_score = float(row['score']) if pd.notna(row['score']) else 0
        # Simple scaling: score/10, rounded up, clamped 1-10
        score_1_10 = max(1, min(10, math.ceil(original_score / 10)))
        stock_report_data['score_1_10'] = score_1_10

        stocks_data.append(stock_report_data)
        time.sleep(0.05) # Small delay

    # Ensure data is sorted by original score descending (important for top picks)
    # Note: screen_stocks already sorts, but we ensure it here before slicing
    stocks_data.sort(key=lambda x: float(x.get('score', 0)), reverse=True)

    # Get top 3 picks
    top_picks = stocks_data[:3]

    # Get weights for the current timeframe
    current_weights = SCORING_WEIGHTS.get(settings.TIMEFRAME, {})

    # Set up Jinja2 environment
    try:
        # Assume template is in the project root directory with run_screen.py
        # If report_generator moves, adjust path accordingly (e.g., using relative paths)
        template_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.exists(os.path.join(template_dir, 'report_template.html')):
            # Fallback if template isn't found relative to report_generator.py
            template_dir = '.' # Assume project root
            
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        # Add custom filters/functions needed by template
        env.globals['format_market_cap'] = format_market_cap
        env.globals['format_sma'] = format_sma # Use global for functions needing multiple args
        
        template = env.get_template("report_template.html")

        # Prepare context data for the template
        context = {
            'report_title': f"Skyrocket Stocks ({settings.TIMEFRAME.replace('_', ' ').title()}) Analysis",
            'generation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'stocks': stocks_data,
            'timeframe': settings.TIMEFRAME,
            'min_price': "{:.2f}".format(settings.min_price_short_term),
            'max_price': "{:.2f}".format(settings.max_price_short_term),
            'top_picks': top_picks, # Add top picks
            'timeframe_weights': current_weights # Add weights for transparency
            # Add more settings/criteria info here if needed
        }

        # Render the template
        html_content = template.render(context)

        # Save the rendered HTML
        report_path = os.path.abspath(output_filename) # Ensure absolute path
        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(html_content)

        print(f"HTML report generated successfully: {report_path}")

    except FileNotFoundError as e:
         print(f"Report Generation Error: Template file 'report_template.html' not found in {template_dir}. {e}")
    except Exception as e:
        print(f"Report Generation Error during template rendering: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging

# Example usage (could be called from run_screen.py)
if __name__ == "__main__":
    # Find the most recent results CSV to test report generation
    import glob
    try:
        list_of_files = glob.glob('skyrocket_candidates_*.csv')
        if list_of_files:
             latest_file = max(list_of_files, key=os.path.getctime)
             print(f"Testing report generation on: {latest_file}")
             generate_html_report(latest_file, output_filename=f"test_report_{os.path.basename(latest_file).replace('.csv', '.html')}")
        else:
             print("No 'skyrocket_candidates_*.csv' files found to test report generation.")
    except Exception as e:
         print(f"Error during report generation test: {e}") 