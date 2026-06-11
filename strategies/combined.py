import backtrader as bt


class CombinedANDStrategy(bt.Strategy):
    """
    Buys when ALL sub-strategies have emitted a buy signal within the last
    `window` bars. Sells when ALL have emitted a sell signal within `window` bars.

    params:
        signal_configs  list of (SignalClass, params_dict) tuples
        window          look-back window in bars
    """
    params = (
        ("signal_configs", []),
        ("window", 5),
    )

    def __init__(self):
        self._signals = [
            cls(**p) for cls, p in self.p.signal_configs
        ]
        # last bar index on which each signal fired; -inf means never
        self._buy_last  = [-10_000] * len(self._signals)
        self._sell_last = [-10_000] * len(self._signals)

    def next(self):
        bar = len(self)
        w   = self.p.window

        for i, sig in enumerate(self._signals):
            if sig.lines.buy[0] > 0:
                self._buy_last[i] = bar
            if sig.lines.sell[0] > 0:
                self._sell_last[i] = bar

        all_buy  = all(bar - t <= w for t in self._buy_last)
        all_sell = all(bar - t <= w for t in self._sell_last)

        if not self.position:
            if all_buy:
                self.buy()
        elif all_sell:
            self.close()
