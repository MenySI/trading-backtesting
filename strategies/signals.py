"""
Signal-only indicators (no order execution) used by CombinedANDStrategy.
Each exposes two lines: buy (1.0) and sell (1.0) on trigger bars, 0.0 otherwise.
"""
import backtrader as bt


class SMACrossSignal(bt.Indicator):
    lines = ("buy", "sell")
    params = (("fast", 10), ("slow", 30))

    def __init__(self):
        fast_ma = bt.ind.SMA(period=self.p.fast)
        slow_ma = bt.ind.SMA(period=self.p.slow)
        self._cross = bt.ind.CrossOver(fast_ma, slow_ma)

    def next(self):
        self.lines.buy[0]  = 1.0 if self._cross[0] > 0 else 0.0
        self.lines.sell[0] = 1.0 if self._cross[0] < 0 else 0.0


class RSISignal(bt.Indicator):
    lines = ("buy", "sell")
    params = (("rsi_period", 14), ("oversold", 30), ("overbought", 70))

    def __init__(self):
        self._rsi = bt.ind.RSI(period=self.p.rsi_period)

    def next(self):
        self.lines.buy[0]  = 1.0 if self._rsi[0] < self.p.oversold  else 0.0
        self.lines.sell[0] = 1.0 if self._rsi[0] > self.p.overbought else 0.0


class MACDSignal(bt.Indicator):
    lines = ("buy", "sell")
    params = (("fast_period", 12), ("slow_period", 26), ("signal_period", 9))

    def __init__(self):
        macd = bt.ind.MACD(
            period1=self.p.fast_period,
            period2=self.p.slow_period,
            period_signal=self.p.signal_period,
        )
        self._cross = bt.ind.CrossOver(macd.macd, macd.signal)

    def next(self):
        self.lines.buy[0]  = 1.0 if self._cross[0] > 0 else 0.0
        self.lines.sell[0] = 1.0 if self._cross[0] < 0 else 0.0


class BollingerSignal(bt.Indicator):
    lines = ("buy", "sell")
    params = (("period", 20), ("devfactor", 2.0))

    def __init__(self):
        bb = bt.ind.BollingerBands(period=self.p.period, devfactor=self.p.devfactor)
        self._lower = bb.lines.bot
        self._upper = bb.lines.top

    def next(self):
        self.lines.buy[0]  = 1.0 if self.data.close[0] < self._lower[0] else 0.0
        self.lines.sell[0] = 1.0 if self.data.close[0] > self._upper[0] else 0.0
