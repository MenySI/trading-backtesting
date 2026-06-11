import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


_TEMPLATE = "plotly_dark"


def price_chart(df: pd.DataFrame, trades: list) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
        subplot_titles=("Price", "Volume"),
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="Price", showlegend=False,
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ), row=1, col=1)

    # Volume bars
    colors = ["#26a69a" if c >= o else "#ef5350"
              for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker_color=colors, name="Volume", showlegend=False,
    ), row=2, col=1)

    # Trade markers
    if trades:
        entry_dates = [t["entry_date"] for t in trades]
        entry_prices = [t["entry_price"] for t in trades]
        exit_dates = [t["exit_date"] for t in trades]
        exit_prices = [t["exit_price"] for t in trades]

        fig.add_trace(go.Scatter(
            x=entry_dates, y=entry_prices, mode="markers",
            marker=dict(symbol="triangle-up", size=14,
                        color="lime", line=dict(color="#00c853", width=1)),
            name="Buy", hovertemplate="Buy<br>%{x}<br>$%{y:.2f}<extra></extra>",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=exit_dates, y=exit_prices, mode="markers",
            marker=dict(symbol="triangle-down", size=14,
                        color="#ff1744", line=dict(color="#b71c1c", width=1)),
            name="Sell", hovertemplate="Sell<br>%{x}<br>$%{y:.2f}<extra></extra>",
        ), row=1, col=1)

    fig.update_layout(
        template=_TEMPLATE,
        height=480,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def equity_chart(equity_curve: list, df: pd.DataFrame, initial_cash: float) -> go.Figure:
    if not equity_curve:
        return go.Figure()

    dates = [e["date"] for e in equity_curve]
    values = [e["value"] for e in equity_curve]

    # Buy-and-hold baseline aligned to equity curve dates
    close = df["Close"].reindex(pd.to_datetime(dates), method="nearest")
    bah = initial_cash * close.values / close.values[0]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values, mode="lines",
        name="Strategy", line=dict(color="#00bcd4", width=2),
        hovertemplate="$%{y:,.2f}<extra>Strategy</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=bah, mode="lines",
        name="Buy & Hold", line=dict(color="#ff9800", width=2, dash="dot"),
        hovertemplate="$%{y:,.2f}<extra>Buy & Hold</extra>",
    ))
    fig.add_hline(y=initial_cash, line_dash="dash", line_color="#555",
                  annotation_text="Initial cash", annotation_position="bottom right")

    fig.update_layout(
        template=_TEMPLATE,
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        yaxis_title="Portfolio Value ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
