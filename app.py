from datetime import datetime, timezone
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from signals import normalize_prices, confirmed_prices, supertrend, advice_for, china_session, demo_prices

st.set_page_config(page_title="QQQ 波段观察", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem; max-width:1250px}
[data-testid="stMetric"] {border:1px solid #283347; border-radius:12px; padding:16px}
h1 {letter-spacing:-1px} footer {visibility:hidden}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_qqq():
    # Unadjusted OHLC matches actual traded daily prices; no intraday forecasts.
    yf.set_tz_cache_location(str(Path(tempfile.gettempdir()) / "qqq_dashboard_yf"))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(yf.download, "QQQ", period="3y", interval="1d", auto_adjust=False,
                             progress=False, threads=False, timeout=15, multi_level_index=False)
    try:
        data = future.result(timeout=45)
    except TimeoutError as exc:
        raise ValueError("行情读取超过 45 秒。请稍后更新，或上传真实 QQQ 日线 CSV。") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    if data is None or data.empty:
        raise ValueError("暂时没有收到 QQQ 行情。Yahoo Finance 可能限流或网络不可达。")
    return normalize_prices(data), datetime.now(timezone.utc)


st.caption("NASDAQ 100 / DAILY TREND")
st.title("QQQ 波段观察")
st.write("用美股已收盘日线判断趋势，在境内交易时段评估 513300 的买卖。")

with st.expander("观察设置 · 持仓状态、行情来源和参数", expanded=False):
    st.title("观察设置")
    st.caption("513300 · 几天到几周的波段")
    position = st.radio("你目前的状态", ["空仓", "已持有 513300"])
    source = st.selectbox("行情来源", ["在线 QQQ 日线", "已下载 QQQ 行情快照", "上传 QQQ 日线 CSV", "界面示例（模拟数据）"])
    uploaded = None
    if source == "上传 QQQ 日线 CSV":
        uploaded = st.file_uploader("QQQ 日线文件", type=["csv"])
        st.caption("列名：Date, Open, High, Low, Close。日期为美股交易日；价格使用未复权价。")
    with st.expander("指标参数"):
        length = st.number_input("ATR 周期", min_value=2, max_value=50, value=10, step=1)
        factor = st.number_input("ATR 倍数", min_value=1.0, max_value=8.0, value=3.0, step=0.5)
        st.caption("默认 10 / 3 是试用起点，未经针对 513300 的收益验证。")
    auto = st.toggle("页面打开时每 5 分钟检查", value=True)
    notify = st.toggle("新信号出现时弹出页面提醒", value=True)
    if st.button("立即更新行情", width="stretch"):
        load_qqq.clear()
    st.caption("页面关闭后不会继续监控，也不会向手机推送。")

@st.fragment(run_every="5m" if auto else None)
def dashboard():
    now = pd.Timestamp.now(tz="UTC")
    demo = source == "界面示例（模拟数据）"
    with st.spinner("正在检查已收盘的 QQQ 日线…"):
        try:
            if demo:
                raw, fetched = demo_prices(now), now
            elif source == "已下载 QQQ 行情快照":
                snapshot = Path(__file__).with_name("qqq_snapshot.csv")
                raw = normalize_prices(pd.read_csv(snapshot))
                fetched = pd.Timestamp(snapshot.stat().st_mtime, unit="s", tz="UTC")
            elif source == "上传 QQQ 日线 CSV":
                if uploaded is None:
                    st.info("在观察设置中上传 QQQ 日线 CSV 后即可查看。")
                    return
                uploaded.seek(0)
                raw, fetched = normalize_prices(pd.read_csv(uploaded)), now
            else:
                raw, fetched = load_qqq()
            prices, expected, fresh = confirmed_prices(raw, now)
            if len(prices) < max(100, int(length)+2):
                raise ValueError("需要至少 100 根已收盘日线，请提供更长的行情历史。")
            result = supertrend(prices, int(length), float(factor))
        except Exception as exc:
            st.error("行情未就绪，暂停买卖建议。")
            st.write(str(exc))
            st.info("展开“观察设置”后，可点“立即更新行情”，或选择已下载的真实行情快照／上传 QQQ 日线 CSV。快照过期会暂停建议。若只想查看页面样式，可选择明确标注的模拟示例。")
            return

    recommendation = advice_for(result, position != "空仓", fresh, demo)
    getattr(st, recommendation.tone)("**"+recommendation.title+"**\n\n"+recommendation.detail)
    if demo:
        st.warning("模拟数据 · 所有价格和历史信号均为界面演示，不能用于交易。")
    elif source == "上传 QQQ 日线 CSV":
        st.caption("数据来自你上传的 CSV；页面无法验证文件是否确为 QQQ 行情。")
    elif source == "已下载 QQQ 行情快照":
        st.info("正在使用已下载的真实行情快照，没有在线更新。出现新的美股收盘日后，旧快照将暂停给出建议。")

    latest = result.iloc[-1]
    last_date = result.index[-1].strftime("%Y-%m-%d")
    last_events = result.loc[result.Signal != ""]
    recent_event = last_events.iloc[-1] if len(last_events) else None
    last_event_date = last_events.index[-1].strftime("%Y-%m-%d") if len(last_events) else "暂无"
    cols = st.columns(2) + st.columns(2)
    cols[0].metric("QQQ 已确认收盘价（USD）" if not demo else "模拟收盘价", f"${latest.Close:,.2f}")
    cols[1].metric("当前趋势", "上涨" if latest.Direction == 1 else "下跌")
    cols[2].metric("趋势参考线", f"${latest.Supertrend:,.2f}")
    cols[3].metric("最新日线信号", latest.Signal or "无新信号")
    fetched_local = pd.Timestamp(fetched).tz_convert("Asia/Shanghai")
    st.caption(f"依据美股交易日 {last_date} 的收盘日线 · 最近应确认日期 {expected:%Y-%m-%d} · 数据检查 {fetched_local:%Y-%m-%d %H:%M}（北京时间）")
    if recent_event is not None:
        st.caption(f"最近一次趋势切换：{last_event_date} / {recent_event.Signal}。历史信号不代表今天出现新买卖点。")
    try:
        active, session_text = china_session(now)
        st.info(session_text)
        st.caption("交易日历来自市场日历库；实际开市和临时停牌以交易所、基金公告为准。")
    except Exception:
        active = False
        st.warning("境内交易日历不可用，请自行核对开市时间；暂停页面信号提醒。")

    # Notify only on a latest-bar event, inside a valid China session. Deduplicate
    # by event and parameters in this browser session; do not replay old flips.
    if notify and active and fresh and not demo and latest.Signal:
        event_key = (last_date, latest.Signal, int(length), float(factor), source)
        seen = st.session_state.setdefault("seen_events", [])
        if event_key not in seen:
            st.toast(f"QQQ {last_date}：{latest.Signal}。操作 513300 前核对溢价。", icon="📈")
            st.session_state.seen_events = (seen+[event_key])[-100:]

    chart_tab, events_tab, rules_tab = st.tabs(["趋势图", "历史信号", "如何使用"])
    with chart_tab:
        window = st.select_slider("显示最近日线", options=[60, 120, 250, 500], value=120)
        view = result.tail(window)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=view.index, open=view.Open, high=view.High,
                                    low=view.Low, close=view.Close, name="QQQ" if not demo else "模拟价格",
                                    increasing_line_color="#34d399", decreasing_line_color="#fb7185"))
        for sign, name, color in [(1, "上涨趋势线", "#34d399"), (-1, "下跌趋势线", "#fb7185")]:
            fig.add_trace(go.Scatter(x=view.index, y=view.Supertrend.where(view.Direction == sign),
                                    mode="lines", line=dict(color=color, width=2), name=name, connectgaps=False))
        for label, symbol, color in [("买入观察", "triangle-up", "#34d399"), ("卖出观察", "triangle-down", "#fb7185")]:
            events = view[view.Signal == label]
            fig.add_trace(go.Scatter(x=events.index, y=events.Close, mode="markers", name=label,
                                    marker=dict(symbol=symbol, size=13, color=color)))
        fig.update_layout(height=510, margin=dict(l=0, r=0, t=10, b=0),
                          xaxis_rangeslider_visible=False, yaxis_title="美元 / 份", template="plotly_dark",
                          legend=dict(orientation="h", y=1.08), hovermode="x unified")
        st.plotly_chart(fig, width="stretch")
        st.caption("参考线会随新日线更新，不能当作固定止损价；QQQ 美元价格不能直接用于给 513300 下单。")
    with events_tab:
        events = result.loc[result.Signal != "", ["Close", "Supertrend", "Signal"]].copy()
        events.index.name = "美股交易日"
        events.columns = ["QQQ 收盘价", "趋势参考线", "信号"]
        st.dataframe(events.sort_index(ascending=False).round(2), width="stretch")
        st.download_button("下载历史信号", events.to_csv().encode("utf-8-sig"), "qqq_signals.csv", "text/csv")
        st.caption("信号历史不等于策略收益。这里没有扣费回测，也没有模拟 513300 的实际成交。")
    with rules_tab:
        st.markdown("""
**先看信号，再核对成交条件。**

- 日线从下跌转上涨：给出买入观察；从上涨转下跌：给出卖出观察。
- 没有新切换：根据你选择的持仓状态显示持有、等待或减仓观察。
- 仅使用美股正常交易时段收盘后的日线，并额外等待 15 分钟；考虑节假日、夏令时和提前收盘。
- 数据不完整或落后于最近应收盘日：暂停操作建议。假期重新开市时，以最新趋势为准。
- 操作 513300 前，检查基金溢价、参考净值日期、买卖价差和停牌公告。高溢价可能抵消纳指上涨带来的收益。

这是固定规则产生的观察建议，没有预测胜率或盈利保证。Supertrend 会滞后，也可能在震荡中反复切换。先模拟观察，再决定是否采用。

**提醒范围**：页面打开时每 5 分钟检查，境内交易时段出现最新信号时在页面弹出提醒。同一会话不重复弹出。关闭页面后不监控、不推送手机。

**数据来源**：在线行情通过 yfinance 读取 Yahoo Finance 的 QQQ 日线，可能延迟、限流或不可用；使用未复权价格。上传 CSV 时，日期应为美股交易日。

[Supertrend 规则](https://www.tradingview.com/support/solutions/43000634738-supertrend/) · [QQQ 基金资料](https://www.invesco.com/qqq-etf/en/about.html) · [513300 溢价风险公告](https://www.chinaamc.com/upload/resources/file/2026/02/25/445422.pdf)
""")


dashboard()
st.caption("QQQ 趋势 ≠ 513300 实际收益。人民币汇率、基金溢价及成交成本都会影响结果。")
