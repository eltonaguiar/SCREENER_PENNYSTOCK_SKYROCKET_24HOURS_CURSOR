![Growth Stock Screener](screenshots/startup.png)

# Short-Term Stock Screener ("Skyrocket Screener")

An automated stock screening system focused on identifying low-priced stocks (e.g., under $4) exhibiting technical indicators suggestive of potential rapid short-term price increases ("skyrocketing").

**Disclaimer:** Stock market investing involves risk. This tool is for informational and educational purposes only and does **not** constitute financial advice. Always conduct thorough research and consult with a qualified financial advisor before making investment decisions.

## Key Features:

*   **Short-Term Focus:** Screens for stocks based on technical indicators suitable for short timeframes (24 hours to 1 month).
*   **Customizable Criteria:** Adjust timeframe, price range, and specific indicator thresholds via settings and command-line arguments.
*   **Data Fetching:** Uses `yfinance` to fetch stock data, with an optional **failover** to the [Twelve Data API](https://twelvedata.com/) (requires API key) for tickers with incomplete `yfinance` data.
*   **Caching:** Caches downloaded data locally to speed up subsequent runs.
*   **Scoring System:** Ranks stocks based on a weighted score derived from technical indicators relevant to the selected timeframe.
*   **Outputs:**
    *   Detailed CSV file (`skyrocket_candidates_*.csv`) with screened stocks and calculated metrics.
    *   Optional comprehensive **HTML Report** (`skyrocket_candidates_*.html`) for better visualization and analysis.
    *   Optional basic **Backtesting** plot (`plots/backtest_*.png`) showing the hypothetical performance of screened stocks against a benchmark (SPY).
*   **Quick Mode:** Option to process a random subset of tickers for faster scans.

## Stock Picking Methodology

This screener operates on the hypothesis that specific combinations of technical indicators can signal a higher probability of significant short-term price increases in low-priced stocks. It **does not** rely on traditional long-term growth metrics (like deep fundamental analysis or SEC filing data used in the original version of this repository).

**Core Steps:**

1.  **Initial Universe:** Starts with a list of NASDAQ-listed stocks (or a user-provided list via `--tickers`).
2.  **Price Filter:** Removes stocks outside the specified price range (e.g., not between $0.10 and $4.00).
3.  **Data Fetching & Validation:** Fetches historical price/volume data (default 3 months, 1 year for report) and basic company info using `yfinance` (with cache). If data is insufficient for calculations (less than ~21 days), it attempts to use Twelve Data as a fallback (if API key provided).
4.  **Indicator Calculation:** For each remaining stock, it calculates:
    *   **Volatility/Momentum:** RSI (14d), ATR (14d %), Bollinger Band Squeeze & Width (20d), Breakout (20d High), 6-Month Momentum.
    *   **Volume:** Volume Surge (Current vs. 10d Avg).
    *   **Short Interest:** Float Short %, Short Ratio (Data from `yfinance` `.info`, may be delayed or unavailable).
    *   **Other:** Institutional Ownership % (from `.info`), Catalyst Proxy (% Price Change over 5d), Sharpe Ratio (1y).
5.  **Timeframe-Based Scoring:** Assigns a score (0-100) based on a weighted combination of the calculated indicators. The specific indicators and weights **vary depending on the selected timeframe (`-t` argument)**:
    *   **24 Hours:** Focuses heavily on immediate signals like Volume Surge, RSI extremes, and recent Breakouts.
    *   **3 Days:** Blends Volume, Breakouts, recent Volatility (ATR), and RSI momentum.
    *   **7 Days:** Incorporates potential reversal signals like Bollinger Band Squeeze and RSI extremes, along with Volume and Institutional Ownership.
    *   **2 Weeks / 1 Month:** Give more weight to factors suggesting sustained moves, like High Short Interest, Bollinger Bands, Institutional Ownership, recent significant price changes (Catalyst Proxy), and RSI momentum.
6.  **Output:** Saves stocks with a score > 0 to a CSV file, sorted by score. Optionally generates an HTML report and/or a backtest plot.

**Why this Methodology?**

*   **Focus:** Targets a specific niche (low-priced, potential short-term movers) often driven by technicals and sentiment rather than long-term fundamentals.
*   **Quantification:** Attempts to quantify common technical setups (e.g., volume spikes, breakouts, squeezes, high short interest) into a comparable score.
*   **Adaptability:** Timeframe selection adjusts the indicator focus (e.g., immediate volume vs. squeeze development).

## Limitations and Considerations

*   **High Risk:** Screening for short-term, low-priced stock movements is inherently speculative and high-risk. There is **no guarantee** any identified stock will actually "skyrocket".
*   **Data Quality & Lag:** Relies heavily on data from `yfinance` (and potentially Twelve Data). This data can have inaccuracies, delays (especially `.info` fields like short interest), or gaps (as seen with `AMODW`).
*   **Indicator Limitations:** Technical indicators are not perfect predictors. They can generate false signals. The chosen indicators and weights are based on common technical analysis patterns but are subjective.
*   **No Fundamental Analysis:** The current methodology **ignores** fundamental factors like revenue/earnings trends (beyond basic `.info` fields), debt, management, industry outlook, etc., which are crucial for long-term investing.
*   **Catalyst Proxy is Basic:** The current "Catalyst Proxy" is simply based on recent price change, not actual news analysis.
*   **Backtesting Limitations:** The included backtest is basic (equal weight, fixed period, no transaction costs/slippage) and only shows past performance, which doesn't guarantee future results.

## Potential Enhancements

*   **Strategy Picker:** Allow choosing between this short-term methodology and the original growth-focused strategy (or others).
*   **Advanced Catalyst Detection:** Integrate news APIs or NLP on filings to identify real catalysts.
*   **Refined Scoring/Weighting:** Optimize indicator weights based on more rigorous backtesting or machine learning.
*   **Data Source Robustness:** Fully integrate and potentially cache data from paid sources like Twelve Data for improved reliability.
*   **User Interface:** Develop a Streamlit or web UI for easier interaction.
*   **Alerts:** Add real-time alerts for newly identified high-scoring stocks.
*   _(See `IDEAS.md` for more details)_*

## Installation

#### Prerequisites

First, ensure that you have [Python 3.11+](https://www.python.org/) and optionally [Firefox](https://www.mozilla.org/en-US/firefox/new/) (if using older versions requiring Selenium, although current version primarily uses APIs) installed.

#### Clone this Repository:

```bash
git clone https://github.com/starboi-63/growth-stock-screener.git
```

#### Navigate to the Root Directory:

```bash
cd growth-stock-screener
```

#### Install Python Dependencies:

```bash
# It's recommended to use a virtual environment
# python -m venv venv
# source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

## Usage

**Basic Run (24hr timeframe, default settings):**

```bash
python growth_stock_screener/run_screen.py
```
> Creates `skyrocket_candidates_24_hours.csv`

**Run with Specific Timeframe and HTML Report:**

```bash
python growth_stock_screener/run_screen.py --timeframe 7_days --html
```
> Creates `skyrocket_candidates_7_days.csv` and `skyrocket_candidates_7_days.html`

**Quick Scan (25% sample) + Backtest:**

```bash
python growth_stock_screener/run_screen.py --quick --backtest
```
> Runs faster, creates default CSV, and saves plot to `plots/` directory.

**Scan Specific Tickers:**

```bash
python growth_stock_screener/run_screen.py --tickers "GME;AMC;BB" --html
```
> Only processes GME, AMC, BB and creates default CSV + HTML report.

**Use Penny Stock Price Preset:**

```bash
python growth_stock_screener/run_screen.py --price-preset penny_stocks
```

**Command-Line Arguments Reference:**

*   `-t TIMEFRAME`, `--timeframe TIMEFRAME`: `24_hours` (default), `3_days`, `7_days`, `2_weeks`, `1_month`.
*   `-p PRESET`, `--price-preset PRESET`: `skyrocket_under_4` (default), `penny_stocks`, `sub_10_dollar`.
*   `--min-price PRICE`: Custom minimum price filter.
*   `--max-price PRICE`: Custom maximum price filter.
*   `--tickers "SYM1;SYM2"`: Process only specific tickers (semicolon-separated).
*   `--cache-age DAYS`: Max age for cached data (default: 1.0). 0 disables cache.
*   `--quick`: Process random 25% sample (asks to reuse previous sample if available).
*   `--html`: Generate detailed HTML report.
*   `--backtest`: Run 30-day backtest vs SPY and save plot.

#### Modifying Settings:

Default values, API keys (placeholder), and less-common options can be modified in `growth_stock_screener/screen/settings.py`.

#### Viewing Results:

*   **CSV:** `skyrocket_candidates_*.csv` in the project root.
*   **HTML Report:** `skyrocket_candidates_*.html` in the project root (if `--html` used).
*   **Backtest Plot:** `plots/backtest_*.png` (if `--backtest` used).

*(Note: The sections below describe the original growth screening methodology, which is currently bypassed by `run_screen.py`)*

## Original Growth Screen Iterations (Currently Bypassed)

An initial list of stocks from which to screen is sourced from _NASDAQ_.

![NASDAQ Listings](screenshots/nasdaq_listings.png)

Then, the following screen iterations are executed sequentially:

### Iteration 1: Relative Strength

The market's strongest stocks are determined by calculating a raw weighted average percentage price change over the last $12$ months of trading. A $40\\%$ weight is attributed to the most recent quarter, while the previous three quarters each receive a weight of $20\\%$.

$$\text{RS (raw)} = 0.2(Q_1\ \\%\Delta) + 0.2(Q_2\ \\%\Delta) + 0.2(Q_3\ \\%\Delta) + 0.4(Q_4\ \\%\Delta)$$

These raw values are then assigned a _percentile rank_ from $0\to 100$ and turned into _RS ratings_. By default, only stocks with a relative strength rating greater than or equal to $90$ make it through this stage of screening.

### Iteration 2: Liquidity

All _micro-cap_ companies and _thinly traded_ stocks are filtered out based on the following criteria:

$$
\begin{aligned}
\text{Market Cap} &\geq \$1\ \text{Billion}\\
\text{Price} &\geq \$10\\
50\ \text{day Average Volume} &\geq 100,000\ \text{Shares}
\end{aligned}
$$

### Iteration 3: Trend

All stocks which are not in a _stage-two_ uptrend are filtered out. A stage-two uptrend is defined as follows:

$$
\begin{aligned}
\text{Price} &\geq 50\ \text{Day SMA}\\
\text{Price} &\geq 200\ \text{Day SMA}\\
10\ \text{Day SMA} &\geq 20\ \text{Day SMA} \geq 50\ \text{Day SMA}\\
\text{Price} &\geq 50\\%\ \text{of}\ 52\ \text{Week High}
\end{aligned}
$$

### Iteration 4: Revenue Growth

Only the most rapidly growing companies with _high revenue growth_ are allowed to pass this iteration of the screen. Specifically,
the percent increase in the most recent reported quarterly revenue versus a year ago must be at least $25\\%$; if available, the percent increase in the prior period versus the same quarter a year ago must also be at least $25\\%$. Revenue data is extracted from XBRL from company 10-K and 10-Q _SEC_ filings, which eliminates foreign stocks in the process.

The current market often factors in _future_ revenue growth; historically, this means certain exceptional stocks have exhibited super-performance _without_ having strong on-paper revenue growth (examples include NVDA, UPST, PLTR, AI, etc.). To ensure that these stocks aren't needlessly filtered out, a small exception to revenue criteria is added: stocks with an $\text{RS} \geq 97$ can bypass revenue criteria and make it through this screen iteration.

### Iteration 5: Institutional Accumulation

Any stocks with a _net-increase_ in institutional-ownership are marked as being under accumulation. Institutional-ownership is measured by the difference in total inflows and outflows in the most recently reported financial quarter. Since this information lags behind the current market by a few months, no stocks are outright eliminated based on this screen iteration.
