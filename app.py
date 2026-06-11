import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import itertools
from datetime import date

from data_loader import get_dataframe, get_feed
from engine import run_backtest
from charts import price_chart, equity_chart
from strategies import (
    SMACross, RSIStrategy, MACDStrategy, BollingerStrategy,
    CombinedANDStrategy,
    SMACrossSignal, RSISignal, MACDSignal, BollingerSignal,
)
import backtrader as bt
import backtrader.analyzers as btanalyzers
from analyzers import TradeList

# ── Strategy registry ─────────────────────────────────────────────────────────
STRATEGIES = {
    "SMA Cross": {
        "class": SMACross,
        "params": {
            "fast": dict(label="Fast MA",      type="int",   min=2,   max=50,  default=10,  step=1),
            "slow": dict(label="Slow MA",      type="int",   min=10,  max=200, default=30,  step=5),
        },
    },
    "RSI": {
        "class": RSIStrategy,
        "params": {
            "rsi_period": dict(label="RSI Period",  type="int", min=5,  max=30, default=14, step=1),
            "oversold":   dict(label="Oversold",    type="int", min=10, max=45, default=30, step=1),
            "overbought": dict(label="Overbought",  type="int", min=55, max=90, default=70, step=1),
        },
    },
    "MACD": {
        "class": MACDStrategy,
        "params": {
            "fast_period":   dict(label="Fast Period",   type="int", min=5,  max=20, default=12, step=1),
            "slow_period":   dict(label="Slow Period",   type="int", min=15, max=50, default=26, step=1),
            "signal_period": dict(label="Signal Period", type="int", min=3,  max=15, default=9,  step=1),
        },
    },
    "Bollinger Bands": {
        "class": BollingerStrategy,
        "params": {
            "period":    dict(label="Period",  type="int",   min=5,   max=50,  default=20,  step=1),
            "devfactor": dict(label="Std Dev", type="float", min=1.0, max=3.0, default=2.0, step=0.1),
        },
    },
}

SIGNAL_MAP = {
    "SMA Cross":       SMACrossSignal,
    "RSI":             RSISignal,
    "MACD":            MACDSignal,
    "Bollinger Bands": BollingerSignal,
}

ALL_STRATEGY_NAMES = list(STRATEGIES.keys()) + ["Combined (AND)"]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Backtesting Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Backtesting")
    st.divider()

    ticker = st.text_input("Ticker Symbol", value="AAPL", placeholder="e.g. AAPL, TSLA, SPY").strip().upper()

    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", value=date(2020, 1, 1))
    end_date   = col2.date_input("End Date",   value=date(2024, 1, 1))

    st.divider()
    initial_cash = st.number_input("Initial Cash ($)", min_value=1000, max_value=10_000_000,
                                   value=10_000, step=1000)

    comm_type = st.radio("Commission Type", ["% per trade", "$ per trade"], horizontal=True)
    commission_fixed = comm_type == "$ per trade"
    if commission_fixed:
        commission = st.number_input("Commission ($)", min_value=0.0, max_value=100.0,
                                     value=1.0, step=0.5, format="%.2f")
    else:
        commission_pct = st.slider("Commission (%)", 0.0, 1.0, 0.1, 0.01, format="%.2f%%")
        commission = commission_pct / 100

    st.divider()
    st.caption("Data is cached locally after the first download.")

# ── Helpers ───────────────────────────────────────────────────────────────────
def render_param_sliders(strat_key: str, prefix: str) -> dict:
    cfg = STRATEGIES[strat_key]["params"]
    cols = st.columns(len(cfg))
    result = {}
    for i, (name, c) in enumerate(cfg.items()):
        with cols[i]:
            key = f"{prefix}_{name}"
            if c["type"] == "int":
                result[name] = st.slider(c["label"], c["min"], c["max"], c["default"], c["step"], key=key)
            else:
                result[name] = st.slider(c["label"],
                                         float(c["min"]), float(c["max"]),
                                         float(c["default"]), float(c["step"]), key=key)
    return result


def validate_params(strat_key: str, params: dict):
    if strat_key == "SMA Cross" and params.get("fast", 0) >= params.get("slow", 1):
        return "Fast MA must be less than Slow MA."
    if strat_key == "MACD" and params.get("fast_period", 0) >= params.get("slow_period", 1):
        return "Fast Period must be less than Slow Period."
    return None


def show_results(r, df, cash, label):
    st.divider()
    st.subheader(f"Results — {label}")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Return",  f"{r['return_pct']:+.2f}%")
    m2.metric("Final Value",   f"${r['final_value']:,.0f}")
    m3.metric("Sharpe Ratio",  f"{r['sharpe']:.3f}")
    m4.metric("Max Drawdown",  f"{r['max_dd_pct']:.2f}%")
    m5.metric("Win Rate",      f"{r['win_rate']:.1f}%")
    m6.metric("Total Trades",  str(r["total_trades"]))

    st.divider()
    st.plotly_chart(price_chart(df, r["trades"]),
                    use_container_width=True, config={"scrollZoom": True})
    st.caption("Equity Curve vs Buy & Hold")
    st.plotly_chart(equity_chart(r["equity_curve"], df, cash),
                    use_container_width=True, config={"scrollZoom": True})

    if r["trades"]:
        st.subheader("Trade Log")
        tdf = pd.DataFrame(r["trades"])
        tdf["pnl"] = tdf["pnl"].map(lambda x: f"{x:+.2f}")
        st.dataframe(tdf, use_container_width=True, hide_index=True)
    else:
        st.info("No completed trades in this period.")


def run_single_opt(df, strategy_cls, params, cash, commission, commission_fixed=False):
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
    cerebro.addanalyzer(btanalyzers.DrawDown,    _name="dd")
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")
    results = cerebro.run()
    strat   = results[0]
    final   = cerebro.broker.getvalue()
    sharpe  = strat.analyzers.sharpe.get_analysis().get("sharperatio") or 0.0
    dd      = strat.analyzers.dd.get_analysis().get("max", {}).get("drawdown", 0)
    t       = strat.analyzers.trades.get_analysis()
    total   = t.get("total", {}).get("total", 0)
    won     = t.get("won",   {}).get("total", 0)
    # Only keep serializable (non-list) params in row
    row = {k: v for k, v in params.items() if not isinstance(v, list)}
    row.update({
        "return_pct": round((final / cash - 1) * 100, 2),
        "sharpe":     round(sharpe, 3),
        "max_dd_pct": round(dd, 2),
        "trades":     total,
        "win_rate":   round((won / total * 100) if total else 0, 1),
    })
    return row


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_bt, tab_opt = st.tabs(["Backtest", "Optimize"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — BACKTEST
# ─────────────────────────────────────────────────────────────────────────────
with tab_bt:
    st.subheader("Strategy")
    strategy_name = st.selectbox("Select Strategy", ALL_STRATEGY_NAMES,
                                 key="bt_strat", label_visibility="collapsed")

    # ── Single strategy ───────────────────────────────────────────────────────
    if strategy_name != "Combined (AND)":
        st.subheader("Parameters")
        params = render_param_sliders(strategy_name, prefix="bt")
        err = validate_params(strategy_name, params)
        if err:
            st.warning(err)

        run_btn = st.button("Run Backtest", type="primary",
                            disabled=bool(err), use_container_width=True)

        if run_btn:
            with st.spinner(f"Running {strategy_name} on {ticker}..."):
                try:
                    df = get_dataframe(ticker, str(start_date), str(end_date))
                    result = run_backtest(df, STRATEGIES[strategy_name]["class"],
                                         params, initial_cash, commission, commission_fixed)
                    st.session_state.update(bt_result=result, bt_df=df,
                                            bt_ticker=ticker, bt_cash=initial_cash)
                except Exception as e:
                    st.error(str(e))
                    st.session_state["bt_result"] = None

    # ── Combined (AND) ────────────────────────────────────────────────────────
    else:
        c_win, c_n = st.columns([4, 1])
        and_window = c_win.slider(
            "AND Window (days)",
            min_value=1, max_value=60, value=5,
            key="bt_and_window",
            help="A trade fires only when ALL strategies have signaled within this many bars of each other.",
        )
        n_strats = int(c_n.number_input("# Strategies", min_value=2, max_value=4,
                                        value=2, step=1, key="bt_n_strats"))

        sub_names, sub_params_list = [], []
        any_err = False

        for i in range(n_strats):
            with st.expander(f"Strategy {i + 1}", expanded=True):
                sub_name = st.selectbox(
                    f"Strategy {i+1}", list(STRATEGIES.keys()),
                    key=f"bt_sub_strat_{i}", label_visibility="collapsed",
                )
                sub_params = render_param_sliders(sub_name, prefix=f"bt_sub_{i}")
                sub_err = validate_params(sub_name, sub_params)
                if sub_err:
                    st.warning(sub_err)
                    any_err = True
                sub_names.append(sub_name)
                sub_params_list.append(sub_params)

        run_btn = st.button("Run Backtest", type="primary",
                            disabled=any_err, use_container_width=True)

        if run_btn:
            signal_configs = [(SIGNAL_MAP[n], p) for n, p in zip(sub_names, sub_params_list)]
            combined_params = {"signal_configs": signal_configs, "window": and_window}
            label = "Combined AND: " + " + ".join(sub_names)
            with st.spinner(f"Running combined strategy on {ticker}..."):
                try:
                    df = get_dataframe(ticker, str(start_date), str(end_date))
                    result = run_backtest(df, CombinedANDStrategy,
                                         combined_params, initial_cash, commission, commission_fixed)
                    st.session_state.update(bt_result=result, bt_df=df,
                                            bt_ticker=label, bt_cash=initial_cash)
                except Exception as e:
                    st.error(str(e))
                    st.session_state["bt_result"] = None

    # ── Results (shared) ──────────────────────────────────────────────────────
    if st.session_state.get("bt_result"):
        show_results(
            st.session_state["bt_result"],
            st.session_state["bt_df"],
            st.session_state["bt_cash"],
            st.session_state["bt_ticker"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — OPTIMIZE
# ─────────────────────────────────────────────────────────────────────────────
with tab_opt:
    st.subheader("Strategy")
    opt_strategy = st.selectbox("Select Strategy", ALL_STRATEGY_NAMES,
                                key="opt_strat", label_visibility="collapsed")

    # ── Single strategy optimize ──────────────────────────────────────────────
    if opt_strategy != "Combined (AND)":
        strat_params = STRATEGIES[opt_strategy]["params"]

        st.subheader("Parameter Ranges")
        grid = {}
        for name, cfg in strat_params.items():
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            c1.markdown(f"**{cfg['label']}**")
            if cfg["type"] == "int":
                lo  = int(c2.number_input("Min",  value=cfg["min"],    key=f"opt_{name}_lo",   label_visibility="collapsed"))
                hi  = int(c3.number_input("Max",  value=cfg["max"]//2, key=f"opt_{name}_hi",   label_visibility="collapsed"))
                stp = int(c4.number_input("Step", value=cfg["step"]*2, key=f"opt_{name}_step", label_visibility="collapsed", min_value=1))
                grid[name] = list(range(lo, hi + 1, stp))
            else:
                lo  = float(c2.number_input("Min",  value=float(cfg["min"]),  key=f"opt_{name}_lo",   label_visibility="collapsed", step=0.1, format="%.1f"))
                hi  = float(c3.number_input("Max",  value=float(cfg["max"]),  key=f"opt_{name}_hi",   label_visibility="collapsed", step=0.1, format="%.1f"))
                stp = float(c4.number_input("Step", value=float(cfg["step"]), key=f"opt_{name}_step", label_visibility="collapsed", step=0.1, format="%.1f", min_value=0.1))
                vals, v = [], lo
                while v <= hi + 1e-9:
                    vals.append(round(v, 4)); v += stp
                grid[name] = vals

        keys   = list(grid.keys())
        combos = list(itertools.product(*[grid[k] for k in keys]))
        valid_combos = []
        for combo in combos:
            p = dict(zip(keys, combo))
            if opt_strategy == "SMA Cross" and p.get("fast", 0) >= p.get("slow", 1):
                continue
            if opt_strategy == "MACD" and p.get("fast_period", 0) >= p.get("slow_period", 1):
                continue
            valid_combos.append(p)

        st.caption(f"{len(valid_combos)} valid combinations")
        opt_btn = st.button("Run Optimization", type="primary",
                            use_container_width=True, disabled=(len(valid_combos) == 0))

        if opt_btn:
            with st.spinner(f"Fetching {ticker} data..."):
                try:
                    df = get_dataframe(ticker, str(start_date), str(end_date))
                except Exception as e:
                    st.error(str(e)); df = None

            if df is not None:
                rows = []
                prog = st.progress(0, text="Running optimization...")
                for i, p in enumerate(valid_combos):
                    rows.append(run_single_opt(df, STRATEGIES[opt_strategy]["class"],
                                               p, initial_cash, commission, commission_fixed))
                    prog.progress((i + 1) / len(valid_combos),
                                  text=f"Combination {i+1}/{len(valid_combos)}")
                prog.empty()
                result_df = pd.DataFrame(rows).sort_values("sharpe", ascending=False).reset_index(drop=True)
                os.makedirs("results", exist_ok=True)
                result_df.to_csv(f"results/opt_{ticker}_{opt_strategy.replace(' ', '_')}.csv", index=False)
                st.session_state.update(opt_result=result_df, opt_label=f"{ticker} — {opt_strategy}",
                                        opt_keys=keys)

    # ── Combined (AND) optimize ───────────────────────────────────────────────
    else:
        st.subheader("AND Window Range")
        wc1, wc2, wc3 = st.columns(3)
        w_min  = int(wc1.number_input("Min (days)",  value=1,  min_value=1, key="opt_w_min"))
        w_max  = int(wc2.number_input("Max (days)",  value=20, min_value=2, key="opt_w_max"))
        w_step = int(wc3.number_input("Step (days)", value=1,  min_value=1, key="opt_w_step"))
        windows = list(range(w_min, w_max + 1, w_step))

        st.subheader("Sub-Strategies (fixed parameters)")
        opt_n = int(st.number_input("# Strategies", min_value=2, max_value=4,
                                    value=2, step=1, key="opt_n_strats"))

        opt_sub_names, opt_sub_params = [], []
        for i in range(opt_n):
            with st.expander(f"Strategy {i + 1}", expanded=True):
                sub_name = st.selectbox(
                    f"Strategy {i+1}", list(STRATEGIES.keys()),
                    key=f"opt_sub_strat_{i}", label_visibility="collapsed",
                )
                sub_p = render_param_sliders(sub_name, prefix=f"opt_sub_{i}")
                sub_e = validate_params(sub_name, sub_p)
                if sub_e:
                    st.warning(sub_e)
                opt_sub_names.append(sub_name)
                opt_sub_params.append(sub_p)

        st.caption(f"{len(windows)} window values to test: {windows[:10]}{'...' if len(windows) > 10 else ''}")
        opt_btn = st.button("Run Optimization", type="primary",
                            use_container_width=True, disabled=(len(windows) == 0))

        if opt_btn:
            signal_configs = [(SIGNAL_MAP[n], p) for n, p in zip(opt_sub_names, opt_sub_params)]
            with st.spinner(f"Fetching {ticker} data..."):
                try:
                    df = get_dataframe(ticker, str(start_date), str(end_date))
                except Exception as e:
                    st.error(str(e)); df = None

            if df is not None:
                rows = []
                prog = st.progress(0, text="Running optimization...")
                for i, w in enumerate(windows):
                    p = {"signal_configs": signal_configs, "window": w}
                    row = run_single_opt(df, CombinedANDStrategy, p, initial_cash, commission, commission_fixed)
                    row["window"] = w
                    rows.append(row)
                    prog.progress((i + 1) / len(windows),
                                  text=f"Window {w} ({i+1}/{len(windows)})")
                prog.empty()
                result_df = pd.DataFrame(rows).sort_values("sharpe", ascending=False).reset_index(drop=True)
                os.makedirs("results", exist_ok=True)
                result_df.to_csv(f"results/opt_{ticker}_combined_AND.csv", index=False)
                label = "Combined AND: " + " + ".join(opt_sub_names)
                st.session_state.update(opt_result=result_df, opt_label=f"{ticker} — {label}",
                                        opt_keys=["window"])

    # ── Opt results (shared) ──────────────────────────────────────────────────
    if st.session_state.get("opt_result") is not None:
        res_df = st.session_state["opt_result"]
        label  = st.session_state["opt_label"]
        keys   = st.session_state.get("opt_keys", [])

        st.divider()
        st.subheader(f"Optimization Results — {label}")

        best = res_df.iloc[0]
        best_params = {k: float(best[k]) if hasattr(best[k], 'item') else best[k]
                       for k in keys if k in best}
        st.success(
            f"Best: {best_params}  |  "
            f"Return: {best['return_pct']:+.2f}%  |  "
            f"Sharpe: {best['sharpe']:.3f}  |  "
            f"Max DD: {best['max_dd_pct']:.2f}%"
        )

        col_rename = {
            "return_pct": "Return %",
            "max_dd_pct": "Max DD %",
            "win_rate":   "Win Rate %",
            "trades":     "Trades",
            "sharpe":     "Sharpe",
        }
        sort_col = st.selectbox("Sort by", ["Sharpe", "Return %", "Max DD %", "Win Rate %", "Trades"],
                                key="opt_sort")
        sort_map = {"Sharpe": "sharpe", "Return %": "return_pct",
                    "Max DD %": "max_dd_pct", "Win Rate %": "win_rate", "Trades": "trades"}
        asc = sort_col == "Max DD %"
        display_df = res_df.sort_values(sort_map[sort_col], ascending=asc).reset_index(drop=True)
        display_df = display_df.rename(columns=col_rename)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption("Results saved to the results/ folder.")
