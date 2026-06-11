"""
Single backtest run with performance report.
Usage: python backtest.py
"""
import backtrader as bt
import backtrader.analyzers as btanalyzers
from data_loader import fetch
from strategies import SMACross


TICKER = "AAPL"
START = "2018-01-01"
END = "2024-01-01"
CASH = 10_000
COMMISSION = 0.001     # 0.1%

STRATEGY = SMACross
PARAMS = dict(fast=10, slow=30, printlog=True)


def run():
    cerebro = bt.Cerebro()
    cerebro.addstrategy(STRATEGY, **PARAMS)

    data = fetch(TICKER, START, END)
    cerebro.adddata(data)

    cerebro.broker.setcash(CASH)
    cerebro.broker.setcommission(commission=COMMISSION)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.04)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(btanalyzers.Returns, _name="returns")

    print(f"\n{'='*50}")
    print(f"  {TICKER}  |  {START} to {END}")
    print(f"  Strategy: {STRATEGY.__name__}  params={PARAMS}")
    print(f"{'='*50}")
    print(f"  Starting cash: ${CASH:,.2f}")

    results = cerebro.run()
    strat = results[0]

    final = cerebro.broker.getvalue()
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio", None)
    dd = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    ret = strat.analyzers.returns.get_analysis()

    total_trades = trades.get("total", {}).get("total", 0)
    won = trades.get("won", {}).get("total", 0)
    lost = trades.get("lost", {}).get("total", 0)
    win_rate = (won / total_trades * 100) if total_trades else 0

    print(f"\n--- Results ---")
    print(f"  Final value   : ${final:,.2f}  ({(final/CASH - 1)*100:+.2f}%)")
    print(f"  Sharpe ratio  : {sharpe:.3f}" if sharpe else "  Sharpe ratio  : N/A")
    print(f"  Max drawdown  : {dd.get('max', {}).get('drawdown', 0):.2f}%")
    print(f"  Trades        : {total_trades}  (W={won} L={lost} Win%={win_rate:.1f}%)")
    print(f"{'='*50}\n")

    cerebro.plot(style="candlestick", volume=True)


if __name__ == "__main__":
    run()
