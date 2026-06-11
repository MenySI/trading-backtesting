import backtrader as bt
import backtrader.analyzers as btanalyzers
from data_loader import get_feed
from analyzers import TradeList, EquityCurve


def run_backtest(df, strategy_cls, params: dict, cash: float = 10_000,
                 commission: float = 0.001, commission_fixed: bool = False) -> dict:
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(strategy_cls, **params)
    cerebro.adddata(get_feed(df))
    cerebro.broker.setcash(cash)
    if commission_fixed:
        cerebro.broker.setcommission(commission=commission,
                                     commtype=bt.CommInfoBase.COMM_FIXED)
    else:
        cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.04)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(TradeList, _name="tradelist")
    cerebro.addanalyzer(EquityCurve, _name="equity")

    results = cerebro.run()
    strat = results[0]

    final = cerebro.broker.getvalue()
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio") or 0.0
    dd = strat.analyzers.dd.get_analysis().get("max", {}).get("drawdown", 0)
    t = strat.analyzers.trades.get_analysis()
    total = t.get("total", {}).get("total", 0)
    won = t.get("won", {}).get("total", 0)
    lost = t.get("lost", {}).get("total", 0)
    avg_win = (t.get("won", {}).get("pnl", {}).get("average") or 0)
    avg_loss = (t.get("lost", {}).get("pnl", {}).get("average") or 0)

    return {
        "final_value": round(final, 2),
        "return_pct": round((final / cash - 1) * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_dd_pct": round(dd, 2),
        "total_trades": total,
        "won": won,
        "lost": lost,
        "win_rate": round((won / total * 100) if total else 0, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "trades": strat.analyzers.tradelist.get_analysis(),
        "equity_curve": strat.analyzers.equity.get_analysis(),
    }
