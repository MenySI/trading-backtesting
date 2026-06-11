"""
Grid-search optimization over strategy parameters.
Usage: python optimize.py
"""
import itertools
import backtrader as bt
import backtrader.analyzers as btanalyzers
import pandas as pd
from tabulate import tabulate
from data_loader import fetch
from strategies import SMACross


TICKER = "AAPL"
START = "2018-01-01"
END = "2024-01-01"
CASH = 10_000
COMMISSION = 0.001

STRATEGY = SMACross

# --- Parameter grid -----------------------------------------------------------
PARAM_GRID = {
    "fast": [5, 10, 15, 20],
    "slow": [30, 50, 100, 200],
}
# ------------------------------------------------------------------------------


def run_single(data_feed, params: dict) -> dict:
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(STRATEGY, **params)
    cerebro.adddata(data_feed)
    cerebro.broker.setcash(CASH)
    cerebro.broker.setcommission(commission=COMMISSION)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.04)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")

    results = cerebro.run()
    strat = results[0]

    final = cerebro.broker.getvalue()
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio") or 0.0
    max_dd = strat.analyzers.dd.get_analysis().get("max", {}).get("drawdown", 0)
    trade_info = strat.analyzers.trades.get_analysis()
    total = trade_info.get("total", {}).get("total", 0)
    won = trade_info.get("won", {}).get("total", 0)
    win_rate = (won / total * 100) if total else 0.0

    return {
        **params,
        "final_value": round(final, 2),
        "return_pct": round((final / CASH - 1) * 100, 2),
        "sharpe": round(sharpe, 4),
        "max_dd_pct": round(max_dd, 2),
        "trades": total,
        "win_rate_pct": round(win_rate, 1),
    }


def optimize():
    print(f"\nLoading data for {TICKER} ({START} → {END})...")
    raw_feed = fetch(TICKER, START, END)

    keys = list(PARAM_GRID.keys())
    combos = list(itertools.product(*[PARAM_GRID[k] for k in keys]))

    # Filter out invalid combos (e.g. fast >= slow for SMA cross)
    valid = []
    for combo in combos:
        p = dict(zip(keys, combo))
        if "fast" in p and "slow" in p and p["fast"] >= p["slow"]:
            continue
        valid.append(p)

    print(f"Running {len(valid)} parameter combinations...\n")

    rows = []
    for i, params in enumerate(valid, 1):
        feed = fetch(TICKER, START, END)   # fresh feed each run
        result = run_single(feed, params)
        rows.append(result)
        print(f"  [{i:3d}/{len(valid)}] {params}  →  return={result['return_pct']:+.2f}%  sharpe={result['sharpe']:.3f}")

    df = pd.DataFrame(rows).sort_values("sharpe", ascending=False)
    df.to_csv("results/optimization_results.csv", index=False)

    print(f"\n{'='*70}")
    print(f"  TOP 10 RESULTS  (sorted by Sharpe)  —  {TICKER}")
    print(f"{'='*70}")
    print(tabulate(df.head(10), headers="keys", tablefmt="github", showindex=False))
    print(f"\nFull results saved to results/optimization_results.csv\n")

    best = df.iloc[0]
    print(f"Best params: { {k: best[k] for k in keys} }")
    print(f"  Return: {best['return_pct']:+.2f}%  |  Sharpe: {best['sharpe']:.3f}  |  Max DD: {best['max_dd_pct']:.2f}%\n")


if __name__ == "__main__":
    optimize()
