import backtrader as bt


class RSIStrategy(bt.Strategy):
    params = (
        ("rsi_period", 14),
        ("oversold", 30),
        ("overbought", 70),
        ("printlog", False),
    )

    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.rsi_period)

    def next(self):
        if not self.position:
            if self.rsi < self.p.oversold:
                self.buy()
        elif self.rsi > self.p.overbought:
            self.close()

    def stop(self):
        if self.p.printlog:
            print(f"  rsi_period={self.p.rsi_period:2d} "
                  f"oversold={self.p.oversold} overbought={self.p.overbought} "
                  f"| Final Value: {self.broker.getvalue():.2f}")
