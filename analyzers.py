import backtrader as bt


class TradeList(bt.Analyzer):
    def start(self):
        self.trades = []

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        exit_price = round(trade.price + trade.pnl / trade.size, 4) if trade.size else 0
        self.trades.append({
            "entry_date": bt.num2date(trade.dtopen).date(),
            "exit_date": bt.num2date(trade.dtclose).date(),
            "entry_price": round(trade.price, 4),
            "exit_price": round(exit_price, 4),
            "size": round(abs(trade.size), 4),
            "pnl": round(trade.pnlcomm, 2),
        })

    def get_analysis(self):
        return self.trades


class EquityCurve(bt.Analyzer):
    def start(self):
        self.curve = []

    def next(self):
        self.curve.append({
            "date": self.data.datetime.date(0),
            "value": round(self.strategy.broker.getvalue(), 2),
        })

    def get_analysis(self):
        return self.curve
