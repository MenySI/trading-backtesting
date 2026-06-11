import backtrader as bt


class BollingerStrategy(bt.Strategy):
    """Buy when price closes below lower band; sell when it closes above upper band."""
    params = (
        ("period", 20),
        ("devfactor", 2.0),
    )

    def __init__(self):
        bb = bt.ind.BollingerBands(period=self.p.period, devfactor=self.p.devfactor)
        self.lower = bb.lines.bot
        self.upper = bb.lines.top

    def next(self):
        if not self.position:
            if self.data.close[0] < self.lower[0]:
                self.buy()
        elif self.data.close[0] > self.upper[0]:
            self.close()
