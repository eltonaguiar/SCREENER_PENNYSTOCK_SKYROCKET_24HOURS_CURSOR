from screen.iterations.utils import *
from datetime import datetime
import time
from termcolor import cprint, colored
import argparse # Import argparse
import pandas as pd
import random # Import random for sampling
import os # Import os for file existence checks
import json # Import json for saving/loading sample

# Import new screener and settings
import screen.settings as settings
import screen.iterations.nasdaq_listings
import screen.iterations.short_term_momentum
import backtest # Corrected: Import directly as it's in the root
import report_generator # Corrected: Import directly as it's in the root

# --- Argument Parsing ---
def parse_arguments():
    parser = argparse.ArgumentParser(description='Run Short-Term Stock Screener with custom settings.')
    # Timeframe argument
    parser.add_argument('-t', '--timeframe', type=str, default=settings.TIMEFRAME,
                        choices=["24_hours", "3_days", "7_days", "2_weeks", "1_month"],
                        help=f'Select the target timeframe (default: {settings.TIMEFRAME})')
    # Price range preset argument
    parser.add_argument('-p', '--price-preset', type=str, default=settings.active_price_preset,
                        choices=list(settings.price_range_presets.keys()),
                        help=f'Select a price range preset (default: {settings.active_price_preset})')
    # Custom price range arguments
    parser.add_argument('--min-price', type=float, default=None,
                        help='Override minimum price (use with --price-preset custom or instead of preset)')
    parser.add_argument('--max-price', type=float, default=None,
                        help='Override maximum price (use with --price-preset custom or instead of preset)')
    # Cache age argument
    parser.add_argument('--cache-age', type=float, default=settings.MAX_CACHE_AGE_DAYS,
                         help=f'Max cache age in days (0 to disable, default: {settings.MAX_CACHE_AGE_DAYS})')
    # Backtest argument
    parser.add_argument('--backtest', action='store_true',
                        help='Run a 30-day backtest on the screened results against SPY.')
    # Quick mode argument
    parser.add_argument('--quick', action='store_true',
                        help='Enable quick mode: process only 25% of the initial ticker list.')
    # Tickers argument
    parser.add_argument('--tickers', type=str, default=None,
                        help='Run screener on a specific list of tickers (semicolon-separated, e.g., "AAPL;MSFT;GOOGL") instead of all NASDAQ listings.')
    # HTML report argument
    parser.add_argument('--html', action='store_true',
                        help='Generate an HTML report from the results.')
    # TODO: Add arguments for backtest start/end dates, investment amount, benchmark

    return parser.parse_args()

args = parse_arguments()

# --- Apply Argument Overrides to Settings ---
settings.TIMEFRAME = args.timeframe
settings.MAX_CACHE_AGE_DAYS = args.cache_age
quick_mode_enabled = args.quick
quick_mode_fraction = settings.QUICK_MODE_FRACTION

if quick_mode_enabled:
    # Override setting fraction if --quick flag is used
    quick_mode_fraction = 0.25 
    print(f"INFO: --quick flag used. Enabling quick mode (processing {quick_mode_fraction:.0%}).")
elif 0 < quick_mode_fraction <= 1.0:
     print(f"INFO: Quick mode enabled via settings (processing {quick_mode_fraction:.0%}).")
     quick_mode_enabled = True
else:
     # Disable if fraction is > 1.0 or <= 0
     quick_mode_fraction = 1.0
     quick_mode_enabled = False

# Apply price settings
if args.min_price is not None:
    settings.min_price_short_term = args.min_price
    print(f"INFO: Using custom min price: ${settings.min_price_short_term:.2f}")
    settings.active_price_preset = "custom" # Mark as custom if min is set
elif args.price_preset != "custom":
    preset_settings = settings.price_range_presets.get(args.price_preset)
    if preset_settings:
        settings.min_price_short_term = preset_settings["min"]
        print(f"INFO: Using price preset '{args.price_preset}': Min Price ${settings.min_price_short_term:.2f}")
        settings.active_price_preset = args.price_preset # Update active preset
    else:
         print(f"Warning: Price preset '{args.price_preset}' not found. Using defaults.")
# Only set max if explicitly provided OR if using a non-custom preset
if args.max_price is not None:
    settings.max_price_short_term = args.max_price
    print(f"INFO: Using custom max price: ${settings.max_price_short_term:.2f}")
    settings.active_price_preset = "custom"
elif args.price_preset != "custom" and preset_settings:
     settings.max_price_short_term = preset_settings["max"]
     print(f"INFO: Using price preset '{args.price_preset}': Max Price ${settings.max_price_short_term:.2f}")
# Ensure min <= max
if settings.min_price_short_term >= settings.max_price_short_term:
     print(f"Warning: Min price (${settings.min_price_short_term}) >= Max price (${settings.max_price_short_term}). Adjusting min price to 0.")
     settings.min_price_short_term = 0

# --- End Apply Argument Overrides ---

# Define cache file path for quick mode sample
QUICK_SAMPLE_CACHE_FILE = os.path.join(screen.iterations.short_term_momentum.CACHE_DIR, "quick_mode_sample.json")

# constants
current_time = datetime.now()

# print banner and heading
print_banner()
# TODO: Update print_settings if needed to show TIMEFRAME
print_settings(current_time)

# check Python version
min_python_version = "3.11"
assert_python_updated(min_python_version)

# Inform user about caching status
if settings.MAX_CACHE_AGE_DAYS > 0:
    print(f"\nINFO: Caching is ENABLED (Max Age: {settings.MAX_CACHE_AGE_DAYS} days). Data will be stored in: {screen.iterations.short_term_momentum.CACHE_DIR}")
else:
    print("\nINFO: Caching is DISABLED.")

# wait for user to press enter
input_msg = f"\nPress Enter to run short-term skyrocket screen (Timeframe: {settings.TIMEFRAME}, Price: ${settings.min_price_short_term:.2f}-${settings.max_price_short_term:.2f})"
if args.tickers:
    input_msg += f" for specific tickers: {args.tickers[:50]}{'...' if len(args.tickers) > 50 else ''}"
input(input_msg + " . . .")

# track start time
start = time.perf_counter()

# Get initial list of tickers
if args.tickers:
    # Use the provided list of tickers
    ticker_list = [ticker.strip().upper() for ticker in args.tickers.split(';') if ticker.strip()]
    print(f"Processing specific ticker list: {ticker_list}")
    if not ticker_list:
        cprint("Error: No valid tickers provided via --tickers argument.", "red")
else:
    # Load from NASDAQ list
    print("Fetching/Loading NASDAQ listings...")
    # Import nasdaq_listings to trigger the download/save if needed (and not cached)
    import screen.iterations.nasdaq_listings 

    # Load the results using the utility function
    try:
        # Assuming utils are imported via 'from screen.iterations.utils import *'
        nasdaq_df = open_outfile("nasdaq_listings") 
        if not nasdaq_df.empty and 'Symbol' in nasdaq_df.columns:
             ticker_list = nasdaq_df['Symbol'].tolist()
             print(f"Obtained {len(ticker_list)} tickers from nasdaq_listings.json.")
        else:
             cprint("Error: Could not load valid tickers from nasdaq_listings.json.", "red")
             ticker_list = []
    except Exception as e:
        cprint(f"Error loading tickers from nasdaq_listings.json: {e}", "red")
        cprint("Please ensure the NASDAQ listing download was successful.", "red")
        ticker_list = [] # Set to empty list to prevent further errors

# Apply Quick Mode Sampling (only if not using specific tickers)
original_ticker_count = len(ticker_list)
reuse_sample = False

if not args.tickers and quick_mode_enabled and ticker_list:
    # Check if a reusable sample exists
    if os.path.exists(QUICK_SAMPLE_CACHE_FILE):
        try:
            with open(QUICK_SAMPLE_CACHE_FILE, 'r') as f:
                cached_sample_data = json.load(f)
            # Validate cache parameters
            if (
                cached_sample_data.get('original_count') == original_ticker_count and
                abs(cached_sample_data.get('fraction_used', 0) - quick_mode_fraction) < 0.001 and # Check fraction match
                isinstance(cached_sample_data.get('sampled_tickers'), list)
            ):
                print(f"INFO: Previous quick mode sample found ({len(cached_sample_data['sampled_tickers'])} tickers from {original_ticker_count} total at {quick_mode_fraction:.0%}).")
                user_choice = input("Reuse this sample? (y/N): ").strip().lower()
                if user_choice == 'y':
                    ticker_list = cached_sample_data['sampled_tickers']
                    print(f"INFO: Reusing previous sample of {len(ticker_list)} tickers.")
                    reuse_sample = True # Flag that we reused
        except Exception as e:
            print(f"Warning: Could not load or validate previous quick sample: {e}")

    # Generate a new sample if not reusing
    if not reuse_sample:
        sample_size = int(original_ticker_count * quick_mode_fraction)
        if sample_size < 1: sample_size = 1 # Ensure at least one ticker
        # Ensure sample size isn't larger than available tickers
        sample_size = min(sample_size, original_ticker_count) 
        ticker_list = random.sample(ticker_list, sample_size)
        print(f"INFO: Quick Mode active. Randomly sampling {len(ticker_list)} tickers (out of {original_ticker_count}).")
        
        # Save the new sample data
        new_sample_data = {
            'original_count': original_ticker_count,
            'fraction_used': quick_mode_fraction,
            'sampled_tickers': ticker_list
        }
        try:
            with open(QUICK_SAMPLE_CACHE_FILE, 'w') as f:
                json.dump(new_sample_data, f, indent=4)
            print(f"INFO: Saved new quick mode sample to {QUICK_SAMPLE_CACHE_FILE}")
        except Exception as e:
            print(f"Warning: Could not save new quick mode sample: {e}")

# Run the short-term momentum screen (only if tickers exist)
if ticker_list:
    screen_results_df = screen.iterations.short_term_momentum.screen_stocks(ticker_list, settings.TIMEFRAME)
else:
    # If original list was empty, or after sampling if it becomes empty (unlikely with sample_size >= 1)
    screen_results_df = pd.DataFrame() 

# track end time
end = time.perf_counter()

# Construct the expected output filename based on the logic in short_term_momentum.py
outfile_name = f"skyrocket_candidates_{settings.TIMEFRAME}.csv"

# notify user when finished
# Adjust message based on whether results were found
if screen_results_df is not None and not screen_results_df.empty:
    # Results were generated
    csv_success = True
    try:
        # Ensure the file was actually saved (screen_stocks might have errors)
        if not os.path.exists(outfile_name):
             print(f"Warning: Results DataFrame was not empty, but CSV file '{outfile_name}' was not found.")
             csv_success = False
        else:
             print_done_message(end - start, outfile_name)
    except Exception as e:
        # Handle potential errors in print_done_message if outfile_name is weird
        print(f"Error finalizing message: {e}")
        csv_success = False

    # --- Generate HTML Report (if requested and CSV saved) ---
    if args.html and csv_success:
        print("\n" + "-" * 80)
        cprint("GENERATING HTML REPORT", "blue", attrs=["bold"])
        print("-" * 80)
        html_report_filename = outfile_name.replace(".csv", ".html")
        report_generator.generate_html_report(outfile_name, html_report_filename)
        print("-" * 80)
    elif args.html and not csv_success:
         cprint("Skipping HTML report generation because CSV file was not saved successfully.", "yellow")

    # --- Run Backtest (if requested) ---
    if args.backtest and csv_success:
        print("\n" + "-" * 80)
        cprint("PERFORMING BACKTEST", "magenta", attrs=["bold"])
        print("-" * 80)
        backtest.run_backtest(outfile_name)
        print("-" * 80)
    elif args.backtest and not csv_success:
         cprint("Skipping backtest because CSV file was not saved successfully.", "yellow")

elif screen_results_df is None:
    # Handle case where screening function returned None (likely an error)
    duration = format_time(end - start)
    print("-" * 80)
    cprint(f"Scan completed in {duration}, but encountered errors. No results generated.", "red")
    print("-" * 80)
else: # screen_results_df is empty
    duration = format_time(end - start)
    print("-" * 80)
    cprint(f"Scan complete. No stocks met the criteria in {duration}.", "yellow")
    print("-" * 80)

# Keep the terminal open (optional)
# input("Press Enter to exit . . .")
