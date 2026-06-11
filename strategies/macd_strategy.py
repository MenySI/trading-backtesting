import backtrader as bt


class MACDStrategy(bt.Strategy):
    params = (
        ("fast_period", 12),
        ("slow_period", 26),
        ("signal_period", 9),
    )

    def __init__(self):
        macd = bt.ind.MACD(
            period1=self.p.fast_period,
            period2=self.p.slow_period,
            period_signal=self.p.signal_period,
        )
        self.crossover = bt.ind.CrossOver(macd.macd, macd.signal)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy()
        elif self.crossover < 0:
            self.close()
