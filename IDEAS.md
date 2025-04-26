eltonaguiar: come up with a IDEAS.MD and give further enhancement ideas.

analyze our current project which has a goal to find stocks under $4 or $5 something like that...   

come up with a few enhancements to allow the user more flexibility to pick stocks from a certain price range..  

Improve their stock picking methodology somehow through a strategy picker, 

backtest their filtering criteria to see if they for example spend $100 on shares in each of the stocks in the list, how would the performance be,

Consider the sharpe ratio.. and momentum based stock choosing.. 


Workspace: Collecting workspace information# IDEAS.MD - Growth Stock Screener Enhancement Proposals

## Current Project Analysis

The Growth Stock Screener currently focuses on finding promising growth stocks with specific characteristics:
- Price range limited to $0.50-$4.00 (lowered from the original higher limits)
- Minimum market cap of $50 million (lowered from $1 billion)
- Minimum volume requirement reduced to 50,000 shares
- Strong relative strength (RS) ratings
- Technical trend criteria
- Revenue growth metrics
- Institutional accumulation signals

This configuration suggests the screener is being used to find lower-priced growth stocks with potential for significant upward movement, possibly targeting penny stocks or small caps with growth characteristics.

## Enhancement Ideas

### 1. Advanced Price Range Flexibility

#### Implementation:
```python
# Price Range Presets
price_range_presets = {
    "penny_stocks": {"min": 0.10, "max": 5.00},
    "small_cap_value": {"min": 5.00, "max": 20.00},
    "mid_cap_growth": {"min": 20.00, "max": 100.00},
    "blue_chip": {"min": 100.00, "max": 10000.00},
    "custom": {"min": min_price, "max": max_price}  # User's custom range
}

# Active preset (can be changed via command line argument)
active_price_preset = "penny_stocks"  # Default
```

Add a command-line interface to select price ranges:

```python
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run Growth Stock Screener with specific settings')
    parser.add_argument('--price-preset', type=str, choices=list(price_range_presets.keys()),
                        help='Select a price range preset')
    parser.add_argument('--min-price', type=float, help='Set custom minimum price')
    parser.add_argument('--max-price', type=float, help='Set custom maximum price')
    
    return parser.parse_args()

args = parse_arguments()
if args.price_preset:
    from screen.settings import price_range_presets
    active_price_preset = args.price_preset
    # Update the current min and max price settings
    if args.price_preset != "custom":
        min_price = price_range_presets[active_price_preset]["min"]
        max_price = price_range_presets[active_price_preset]["max"]
    elif args.min_price is not None and args.max_price is not None:
        min_price = args.min_price
        max_price = args.max_price
```

### 2. Strategy Picker with Pre-defined Investment Styles

Add different screening strategies that users can select:

```python
# Strategy Presets
strategy_presets = {
    "momentum": {
        "min_rs": 95,
        "trend_settings": {
            "Price >= 50-day SMA": True,
            "Price >= 200-day SMA": True,
            "10-day SMA >= 20-day SMA": True,
            "20-day SMA >= 50-day SMA": True,
            "Price within 50% of 52-week High": True
        },
        "min_growth_percent": 25,
        "protected_rs": 98
    },
    "value_growth": {
        "min_rs": 80,
        "trend_settings": {
            "Price >= 50-day SMA": True,
            "Price >= 200-day SMA": False,
            "10-day SMA >= 20-day SMA": True,
            "20-day SMA >= 50-day SMA": False,
            "Price within 50% of 52-week High": True
        },
        "min_growth_percent": 15,
        "protected_rs": 90
    },
    "breakout": {
        "min_rs": 90,
        "trend_settings": {
            "Price >= 50-day SMA": True,
            "Price >= 200-day SMA": False,
            "10-day SMA >= 20-day SMA": True,
            "20-day SMA >= 50-day SMA": True,
            "Price within 50% of 52-week High": True
        },
        "min_growth_percent": 30,
        "protected_rs": 95
    },
    "custom": {
        # Current user settings as default
        "min_rs": min_rs,
        "trend_settings": trend_settings,
        "min_growth_percent": min_growth_percent,
        "protected_rs": protected_rs
    }
}

active_strategy = "custom"  # Default to custom (current settings)
```

### 3. Performance Backtesting Module

Create a new module to backtest the performance of screened stocks:

```python
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from termcolor import colored, cprint

def backtest_portfolio(symbols, investment_per_stock=100, start_date=None, end_date=None, benchmark="SPY"):
    """
    Backtest a portfolio of stocks with equal investment in each.
    
    Parameters:
    -----------
    symbols : list
        List of stock symbols to backtest
    investment_per_stock : float
        Amount to invest in each stock
    start_date : datetime
        Start date for backtesting (defaults to 30 days ago)
    end_date : datetime
        End date for backtesting (defaults to today)
    benchmark : str
        Symbol for benchmark comparison (default: SPY)
    """
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
        
    print(f"Backtesting portfolio of {len(symbols)} stocks from {start_date} to {end_date}...")
    
    # Add benchmark to symbols
    all_symbols = symbols + [benchmark]
    
    # Download price data
    prices = yf.download(all_symbols, start=start_date, end=end_date)['Adj Close']
    
    # Calculate returns
    returns = prices.pct_change().dropna()
    
    # Calculate portfolio performance
    portfolio_values = pd.DataFrame(index=returns.index)
    
    # Calculate shares purchased for each stock
    shares = {}
    for symbol in symbols:
        if symbol in prices.columns and not pd.isna(prices[symbol].iloc[0]):
            shares[symbol] = investment_per_stock / prices[symbol].iloc[0]
        else:
            shares[symbol] = 0
    
    # Calculate daily portfolio value
    portfolio_values['Portfolio'] = 0
    for symbol in symbols:
        if symbol in prices.columns and shares[symbol] > 0:
            portfolio_values['Portfolio'] += prices[symbol] * shares[symbol]
    
    # Calculate benchmark performance (normalized to same starting investment)
    total_investment = investment_per_stock * len(symbols)
    benchmark_shares = total_investment / prices[benchmark].iloc[0]
    portfolio_values['Benchmark'] = prices[benchmark] * benchmark_shares
    
    # Calculate portfolio metrics
    portfolio_returns = portfolio_values.pct_change().dropna()
    
    # Calculate Sharpe ratio (assuming risk-free rate of 0% for simplicity)
    sharpe_ratio = np.sqrt(252) * portfolio_returns['Portfolio'].mean() / portfolio_returns['Portfolio'].std()
    
    # Calculate max drawdown
    portfolio_cumulative = (1 + portfolio_returns['Portfolio']).cumprod()
    running_max = portfolio_cumulative.cummax()
    drawdown = (portfolio_cumulative / running_max) - 1
    max_drawdown = drawdown.min()
    
    # Calculate total return
    total_return = (portfolio_values['Portfolio'].iloc[-1] / portfolio_values['Portfolio'].iloc[0]) - 1
    benchmark_return = (portfolio_values['Benchmark'].iloc[-1] / portfolio_values['Benchmark'].iloc[0]) - 1
    
    # Plot results
    plt.figure(figsize=(10, 6))
    plt.plot(portfolio_values.index, portfolio_values['Portfolio'], label=f'Screened Portfolio ({total_return:.2%})')
    plt.plot(portfolio_values.index, portfolio_values['Benchmark'], label=f'{benchmark} ({benchmark_return:.2%})')
    plt.title(f'Portfolio Performance vs {benchmark} ({start_date} to {end_date})')
    plt.ylabel('Portfolio Value ($)')
    plt.xlabel('Date')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'backtest_results_{datetime.now().strftime("%Y-%m-%d")}.png')
    
    # Print results
    print("\n" + "="*50)
    print(colored("BACKTEST RESULTS", "light_green", attrs=["bold"]))
    print("="*50)
    print(f"Time Period: {start_date} to {end_date}")
    print(f"Number of Stocks: {len(symbols)}")
    print(f"Investment per Stock: ${investment_per_stock:.2f}")
    print(f"Total Investment: ${total_investment:.2f}")
    
    print("\nPERFORMANCE METRICS:")
    print(f"Total Return: {total_return:.2%}" + 
          colored(f" (vs {benchmark}: {benchmark_return:.2%})", 
                 "green" if total_return > benchmark_return else "red"))
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Maximum Drawdown: {max_drawdown:.2%}")
    
    # Return the results
    return {
        "total_return": total_return,
        "benchmark_return": benchmark_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "portfolio_values": portfolio_values
    }

def run_backtest():
    # Assume screen_results.csv is the output of the main screener
    try:
        df = pd.read_csv("screen_results.csv")
        symbols = df['Ticker'].tolist()
        if symbols:
            backtest_portfolio(symbols)
        else:
            print("No stocks found in screen_results.csv to backtest.")
    except FileNotFoundError:
        print("screen_results.csv not found. Run the screener first.")

# Example of integrating the backtest call (e.g., in run_screen.py)
# after df.to_csv(...):
#    print("\nRunning backtest on screened results...")
#    from screen.backtest import run_backtest
#    run_backtest()

### 4. Momentum-Based Ranking and Sharpe Ratio Calculation

Enhance the screening output to include momentum indicators and calculate the Sharpe ratio for each stock.

```python
# Add to indicator calculation logic (e.g., in trend.py or a new module)

def calculate_momentum_sharpe(data):
    returns = data['Adj Close'].pct_change().dropna()
    
    # Momentum (e.g., 6-month cumulative return)
    momentum_period = 126 # approx 6 months
    if len(returns) >= momentum_period:
        momentum = (1 + returns.tail(momentum_period)).prod() - 1
    else:
        momentum = np.nan
        
    # Sharpe Ratio (annualized, risk-free rate assumed 0)
    if len(returns) > 1:
        sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()
    else:
        sharpe_ratio = np.nan
        
    return {"momentum_6m": momentum, "sharpe_ratio": sharpe_ratio}

# Integrate into main screening flow and add columns to output CSV
```

### 5. Short-Term "Skyrocket" Momentum Strategy

*   **Goal:** Identify stocks under a low price threshold (e.g., $4) that show potential for rapid price increase within defined short timeframes (24 hours, 3 days, 7 days, 2 weeks, 1 month).
*   **Implementation:**
    *   Replace long-term growth criteria with short-term technical indicators: Price Filter, Volatility (ATR), Volume Surge, RSI Extremes, Bollinger Band Squeeze, Recent Price Patterns (Breakouts), Short Interest, News/Catalyst Proxies.
    *   Add `TIMEFRAME` setting in `settings.py`.
    *   Create a new screening module (`short_term_momentum.py`) with timeframe-specific scoring logic.
    *   Use `yfinance` for data fetching.
    *   *(Status: Partially implemented)*

### 6. Data Caching Mechanism

*   **Goal:** Reduce redundant API calls and speed up subsequent runs by caching downloaded data.
*   **Implementation:**
    *   Add `MAX_CACHE_AGE_DAYS` setting in `settings.py`.
    *   Use `pickle` to store downloaded `yfinance` data (historical prices, ticker info) in a dedicated `cache/` directory.
    *   Check cache validity based on file modification time and `MAX_CACHE_AGE_DAYS` before fetching fresh data.
    *   Add `cache/` to `.gitignore`.
    *   *(Status: Implemented)*

### 7. Enhanced Data Sources & Integration

*   **Goal:** Improve data reliability, reduce rate-limiting issues, and potentially access more data points.
*   **Implementation Ideas:**
    *   Integrate a paid financial data API (e.g., Twelve Data, Alpha Vantage, EOD Historical Data) as an alternative or supplement to `yfinance`.
    *   Requires refactoring data fetching functions (`fetch_stock_data`, `fetch_ticker_info`) to handle the chosen API.
    *   Could provide more reliable real-time/intraday data, pre-calculated indicators, and broader data access.

### 8. Advanced Catalyst Detection

*   **Goal:** Move beyond simple price change proxies for identifying potential catalysts.
*   **Implementation Ideas:**
    *   Integrate news APIs (e.g., NewsAPI, Marketaux) or scrape financial news sites (e.g., Finviz, Yahoo Finance News).
    *   Perform basic NLP (keyword matching, sentiment analysis) on recent news headlines or SEC filings (already partially handled by `sec_requests.py` utils) related to earnings, FDA approvals, product launches, M&A, etc.
    *   Correlate news events with price/volume movements.

### 9. Institutional Ownership Cross-Check

*   **Goal:** Validate findings or add a scoring factor based on recent institutional interest.
*   **Implementation Ideas:**
    *   Re-integrate or adapt the original `institutional_accumulation.py` logic using SEC filings.
    *   Scrape data from sites summarizing institutional/superinvestor holdings (e.g., Dataroma, WhaleWisdom - check terms of service).
    *   Use this as an additional filter or add it to the scoring calculation for screened stocks.

### 10. User Interface and Alerts

*   **Goal:** Improve usability and provide timely notifications.
*   **Implementation Ideas:**
    *   Develop a simple web UI using Streamlit or Flask for easier configuration and result viewing.
    *   Implement real-time alerts (e.g., email, Telegram bot) for stocks meeting high-score criteria, especially for short timeframes.

Similar code found with 1 license type

eltonaguiar: save that stuff under IDEAS.MD

GitHub Copilot: