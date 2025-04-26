import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from termcolor import colored, cprint
import os # Added for path handling

# Ensure plots directory exists
PLOTS_DIR = "plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

def backtest_portfolio(symbols, investment_per_stock=100, start_date_str=None, end_date_str=None, benchmark="SPY", results_filename="skyrocket_candidates_24_hours.csv"):
    """
    Backtest a portfolio of stocks with equal investment in each.

    Parameters:
    -----------
    symbols : list
        List of stock symbols to backtest
    investment_per_stock : float
        Amount to invest in each stock
    start_date_str : str, optional
        Start date for backtesting (YYYY-MM-DD format), defaults to 30 days ago
    end_date_str : str, optional
        End date for backtesting (YYYY-MM-DD format), defaults to today
    benchmark : str
        Symbol for benchmark comparison (default: SPY)
    results_filename : str
        Filename of the screener results CSV used (for plot title)
    """
    if not symbols:
        cprint("Error: No symbols provided for backtesting.", "red")
        return None

    if start_date_str is None:
        start_date = (datetime.now() - timedelta(days=30))
        start_date_str = start_date.strftime('%Y-%m-%d')
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            cprint(f"Error: Invalid start date format: {start_date_str}. Use YYYY-MM-DD.", "red")
            return None

    if end_date_str is None:
        end_date = datetime.now()
        end_date_str = end_date.strftime('%Y-%m-%d')
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            cprint(f"Error: Invalid end date format: {end_date_str}. Use YYYY-MM-DD.", "red")
            return None

    if start_date >= end_date:
        cprint(f"Error: Start date ({start_date_str}) must be before end date ({end_date_str}).", "red")
        return None

    print(f"\nBacktesting portfolio of {len(symbols)} stocks from {start_date_str} to {end_date_str}...")

    # Add benchmark to symbols if not already present
    all_symbols = list(set(symbols + [benchmark])) # Use set to avoid duplicates

    # Download price data
    try:
        # Add 1 day to end_date for yfinance download to include the end date itself
        dl_end_date = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        prices = yf.download(all_symbols, start=start_date_str, end=dl_end_date, progress=False)['Adj Close']
        if prices.empty:
             cprint(f"Error: No price data downloaded for symbols: {all_symbols}", "red")
             return None
        # Filter prices back to the original end_date
        prices = prices[:end_date_str]
        if prices.empty:
             cprint(f"Error: No price data available within the specified date range after filtering.", "red")
             return None
    except Exception as e:
        cprint(f"Error downloading price data: {e}", "red")
        return None

    # Handle cases where some symbols might not have data for the full range
    prices = prices.dropna(axis=1, how='all') # Drop columns with no data at all
    valid_symbols = [s for s in symbols if s in prices.columns and not prices[s].isnull().all()]
    if benchmark not in prices.columns or prices[benchmark].isnull().all():
         cprint(f"Error: Benchmark symbol {benchmark} has no valid price data for the period.", "red")
         return None

    if not valid_symbols:
         cprint("Error: None of the provided symbols have valid price data for the backtest period.", "red")
         return None
    if len(valid_symbols) < len(symbols):
         cprint(f"Warning: Only {len(valid_symbols)} out of {len(symbols)} symbols had valid data for backtesting.", "yellow")

    # Calculate returns
    returns = prices[valid_symbols + [benchmark]].pct_change().iloc[1:] # Drop first NaN row
    if returns.empty:
        cprint("Error: Could not calculate returns (insufficient data points?).", "red")
        return None

    # Calculate portfolio performance
    portfolio_values = pd.DataFrame(index=returns.index)

    # Calculate shares purchased for each stock at the start date
    start_prices = prices.iloc[0]
    shares = {}
    actual_investment_per_stock = {}
    total_investment = 0
    invested_symbols = []

    for symbol in valid_symbols:
        start_price = start_prices.get(symbol)
        if start_price is not None and pd.notna(start_price) and start_price > 0:
            shares[symbol] = investment_per_stock / start_price
            actual_investment_per_stock[symbol] = investment_per_stock
            total_investment += investment_per_stock
            invested_symbols.append(symbol)
        else:
            cprint(f"Warning: Could not invest in {symbol} (invalid start price: {start_price}).", "yellow")
            shares[symbol] = 0
            actual_investment_per_stock[symbol] = 0

    if total_investment == 0:
        cprint("Error: Could not invest in any stocks due to missing/invalid start prices.", "red")
        return None

    # Calculate daily portfolio value
    portfolio_values['Portfolio'] = 0
    for symbol in invested_symbols:
        # Ensure the column exists after potential drops and fill NaNs forward temporarily for calculation
        portfolio_values['Portfolio'] += (prices[symbol].ffill() * shares[symbol])

    # Calculate benchmark performance (normalized to same starting investment)
    benchmark_start_price = start_prices.get(benchmark)
    if benchmark_start_price is not None and pd.notna(benchmark_start_price) and benchmark_start_price > 0:
        benchmark_shares = total_investment / benchmark_start_price
        portfolio_values['Benchmark'] = prices[benchmark].ffill() * benchmark_shares
    else:
        cprint(f"Error: Cannot calculate benchmark performance due to invalid start price: {benchmark_start_price}.", "red")
        portfolio_values['Benchmark'] = total_investment # Flat line

    # Calculate portfolio metrics
    portfolio_returns_ts = portfolio_values['Portfolio'].pct_change().dropna()
    benchmark_returns_ts = portfolio_values['Benchmark'].pct_change().dropna()

    # Calculate Sharpe ratio (annualized, assuming risk-free rate of 0%)
    sharpe_ratio = np.nan
    if not portfolio_returns_ts.empty and portfolio_returns_ts.std() != 0:
        sharpe_ratio = np.sqrt(252) * portfolio_returns_ts.mean() / portfolio_returns_ts.std()

    # Calculate max drawdown
    portfolio_cumulative = (1 + portfolio_returns_ts).cumprod() * total_investment # Start value = total investment
    running_max = portfolio_cumulative.cummax()
    drawdown = (portfolio_cumulative / running_max) - 1
    max_drawdown = drawdown.min()

    # Calculate total return
    total_return = (portfolio_values['Portfolio'].iloc[-1] / total_investment) - 1
    benchmark_total_return = (portfolio_values['Benchmark'].iloc[-1] / total_investment) - 1

    # Plot results
    plt.style.use('seaborn-v0_8-darkgrid') # Use a nice style
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(portfolio_values.index, portfolio_values['Portfolio'], label=f'Screened Portfolio ({total_return:.2%})', linewidth=2)
    ax.plot(portfolio_values.index, portfolio_values['Benchmark'], label=f'{benchmark} ({benchmark_total_return:.2%})', linestyle='--', linewidth=2)

    # Formatting
    ax.set_title(f'Portfolio Performance vs {benchmark}\n({len(invested_symbols)} stocks from {results_filename}, ${investment_per_stock:.0f}/stock)', fontsize=14)
    ax.set_ylabel('Portfolio Value ($)', fontsize=12)
    ax.set_xlabel('Date', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save plot
    plot_filename = os.path.join(PLOTS_DIR, f'backtest_{results_filename.replace(".csv","")}_{start_date_str}_to_{end_date_str}.png')
    try:
        plt.savefig(plot_filename)
        print(f"\nBacktest plot saved to: {plot_filename}")
    except Exception as e:
        cprint(f"Error saving plot: {e}", "red")
    plt.close(fig) # Close the plot figure

    # Print results
    print("\n" + "="*60)
    print(colored("BACKTEST RESULTS".center(60), "light_green", attrs=["bold"]))
    print("="*60)
    print(f" Period:             {start_date_str} to {end_date_str}")
    print(f" Stocks Tested:      {len(invested_symbols)}/{len(symbols)}")
    print(f" Investment/Stock: ${investment_per_stock:.2f}")
    print(f" Total Investment:   ${total_investment:.2f}")
    print(f" Final Portfolio Value: ${portfolio_values['Portfolio'].iloc[-1]:.2f}")
    print("-"*60)
    print(colored(" PERFORMANCE METRICS:", "cyan"))
    return_color = "green" if total_return >= benchmark_total_return else "red"
    print(f"  Total Return:      {colored(f'{total_return:.2%}', return_color)}")
    benchmark_text = colored(f" (vs {benchmark}: {benchmark_total_return:.2%})", "grey")
    print(f"  Benchmark Return: {benchmark_text}")
    print(f"  Sharpe Ratio:      {sharpe_ratio:.2f}")
    print(f"  Max Drawdown:      {colored(f'{max_drawdown:.2%}', 'red')}")
    print("="*60 + "\n")

    # Return the results dict
    return {
        "total_return": total_return,
        "benchmark_return": benchmark_total_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "portfolio_values": portfolio_values,
        "plot_filename": plot_filename
    }

def run_backtest(results_file):
    """Reads symbols from a results file and runs the backtest."""
    try:
        df = pd.read_csv(results_file)
        if 'ticker' not in df.columns:
            cprint(f"Error: Results file '{results_file}' missing 'ticker' column.", "red")
            return
        symbols = df['ticker'].dropna().unique().tolist()
        if symbols:
            # You might want to make backtest parameters configurable here too
            backtest_portfolio(symbols, results_filename=os.path.basename(results_file))
        else:
            print(f"No valid stock tickers found in {results_file} to backtest.")
    except FileNotFoundError:
        cprint(f"Error: Results file '{results_file}' not found. Run the screener first.", "red")
    except pd.errors.EmptyDataError:
         cprint(f"Error: Results file '{results_file}' is empty.", "red")
    except Exception as e:
        cprint(f"An error occurred during backtest execution: {e}", "red")

# Example usage (if run directly)
if __name__ == "__main__":
    # Find the most recent skyrocket results file if no argument is given
    import glob
    try:
        list_of_files = glob.glob('skyrocket_candidates_*.csv')
        if list_of_files:
             latest_file = max(list_of_files, key=os.path.getctime)
             print(f"Running backtest on latest results file: {latest_file}")
             run_backtest(latest_file)
        else:
             print("No 'skyrocket_candidates_*.csv' files found in the current directory.")
    except Exception as e:
         print(f"Error finding latest results file: {e}") 