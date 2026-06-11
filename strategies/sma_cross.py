import backtrader as bt


class SMACross(bt.Strategy):
    params = (
        ("fast", 10),
        ("slow", 30),
        ("printlog", False),
    )

    def __init__(self):
        fast_ma = bt.ind.SMA(period=self.p.fast)
        slow_ma = bt.ind.SMA(period=self.p.slow)
        self.crossover = bt.ind.CrossOver(fast_ma, slow_ma)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy()
        elif self.crossover < 0:
            self.close()

    def stop(self):
        if self.p.printlog:
            print(f"  fast={self.p.fast:2d} slow={self.p.slow:2d} "
                  f"| Final Value: {self.broker.getvalue():.2f}")
