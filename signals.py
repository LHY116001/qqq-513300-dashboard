"""Confirmed daily bars and a Wilder-ATR Supertrend; no future bars used."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal


def normalize_prices(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).strip().title() for c in df.columns]
    if "Date" in df:
        df.index = pd.to_datetime(df.pop("Date"), errors="raise")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("需要 Date、Open、High、Low、Close 列，Date 使用 YYYY-MM-DD。")
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    df.index = df.index.normalize()
    needed = ["Open", "High", "Low", "Close"]
    if any(c not in df for c in needed):
        raise ValueError("行情缺少 Open、High、Low、Close 列。")
    df = df[needed].apply(pd.to_numeric, errors="raise").sort_index()
    if df.empty or df.index.has_duplicates or df.index.hasnans:
        raise ValueError("行情为空、日期重复或日期无效。")
    if not np.isfinite(df.to_numpy()).all() or (df <= 0).any().any():
        raise ValueError("行情存在缺失值或无效价格。")
    if ((df.High < df[needed].max(axis=1)) | (df.Low > df[needed].min(axis=1))).any():
        raise ValueError("行情的最高价／最低价不符合价格范围。")
    return df


def confirmed_prices(prices: pd.DataFrame, now: pd.Timestamp):
    """Include a bar only 15 minutes after its actual exchange session close."""
    now = pd.Timestamp(now).tz_convert("UTC")
    end = now.tz_convert("America/New_York").date()
    start = min(prices.index.min().date(), end - pd.Timedelta(days=40))
    schedule = mcal.get_calendar("NASDAQ").schedule(start_date=start, end_date=end)
    completed = schedule.loc[schedule.market_close + pd.Timedelta(minutes=15) <= now]
    if completed.empty:
        raise ValueError("找不到已收盘的交易日。")
    expected = completed.index[-1]
    confirmed = prices.loc[prices.index.isin(completed.index)].copy()
    if confirmed.empty:
        raise ValueError("没有已确认收盘的日线。")
    recent_sessions = completed.loc[confirmed.index[0]:].index
    recent_sessions = recent_sessions[-200:]
    missing = recent_sessions.difference(confirmed.index)
    fresh = confirmed.index[-1] == expected and len(missing) == 0
    return confirmed, expected, fresh


def supertrend(prices: pd.DataFrame, length: int = 10, factor: float = 3.0):
    if length < 2 or factor <= 0 or len(prices) < length + 2:
        raise ValueError("计算参数无效或历史日线不足。")
    result = prices.copy()
    high, low, close = (result[c].to_numpy(dtype=float) for c in ("High", "Low", "Close"))
    prev_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr[0] = high[0] - low[0]
    atr = np.full(len(prices), np.nan)
    atr[length - 1] = tr[:length].mean()
    for i in range(length, len(prices)):
        atr[i] = (atr[i-1] * (length-1) + tr[i]) / length
    upper = (high + low)/2 + factor*atr
    lower = (high + low)/2 - factor*atr
    trend = np.full(len(prices), np.nan)
    direction = np.zeros(len(prices), dtype=int)
    first = length-1
    direction[first] = -1
    trend[first] = upper[first]
    for i in range(length, len(prices)):
        if not (upper[i] < upper[i-1] or close[i-1] > upper[i-1]):
            upper[i] = upper[i-1]
        if not (lower[i] > lower[i-1] or close[i-1] < lower[i-1]):
            lower[i] = lower[i-1]
        if direction[i-1] == -1:
            direction[i] = 1 if close[i] > upper[i] else -1
        else:
            direction[i] = -1 if close[i] < lower[i] else 1
        trend[i] = lower[i] if direction[i] == 1 else upper[i]
    result["ATR"] = atr
    result["Supertrend"] = trend
    result["Direction"] = direction
    previous = np.r_[0, direction[:-1]]
    result["Signal"] = np.where((direction == 1) & (previous == -1), "买入观察",
                                np.where((direction == -1) & (previous == 1), "卖出观察", ""))
    return result


@dataclass(frozen=True)
class Advice:
    title: str
    detail: str
    tone: str


def advice_for(result, held: bool, fresh: bool, demo: bool = False):
    if demo:
        return Advice("界面示例 · 不提供操作建议", "图表使用模拟数据，不能用于交易。切换到在线行情或上传真实 QQQ 日线。", "warning")
    if not fresh:
        return Advice("暂停建议 · 等待完整行情", "行情尚未覆盖最近应收盘的美股交易日，或近期日线存在缺口。更新数据后再判断。", "warning")
    latest = result.iloc[-1]
    if latest.Signal == "买入观察":
        return Advice("持有观察" if held else "买入观察", "最新已收盘日线由下跌转为上涨。已有持仓可观察持有；空仓先核对 513300 的溢价与成交价格，再考虑小仓位参与。", "success")
    if latest.Signal == "卖出观察":
        return Advice("卖出／减仓观察" if held else "继续观望", "最新已收盘日线由上涨转为下跌。有持仓可在境内开市后评估减仓；空仓暂不参与。", "warning")
    if int(latest.Direction) == 1:
        return Advice("持有观察" if held else "等待新买点", "当前仍处于上涨趋势，但最新日线没有新买入信号。已有持仓可观察持有；空仓不把历史买点当作今天的新买点。", "success" if held else "info")
    return Advice("减仓／离场观察" if held else "继续观望", "当前处于下跌趋势，最新日线没有新卖出信号。有持仓可评估是否继续承担风险；空仓等待趋势转强。", "warning" if held else "info")


def china_session(now):
    local = pd.Timestamp(now).tz_convert("Asia/Shanghai")
    calendar = mcal.get_calendar("SSE")
    schedule = calendar.schedule(start_date=local.date(), end_date=local.date()+pd.Timedelta(days=35))
    if schedule.empty:
        return False, "境内交易日历不可用，请核对交易所公告。"
    for day, row in schedule.iterrows():
        opening = row.market_open.tz_convert("Asia/Shanghai")
        closing = row.market_close.tz_convert("Asia/Shanghai")
        if closing <= local:
            continue
        if "break_start" in row and pd.notna(row.break_start):
            break_start = row.break_start.tz_convert("Asia/Shanghai")
            break_end = row.break_end.tz_convert("Asia/Shanghai")
        else:
            break_start = opening.normalize()+pd.Timedelta(hours=11, minutes=30)
            break_end = opening.normalize()+pd.Timedelta(hours=13)
        active = opening <= local < closing and not (break_start <= local < break_end)
        if active:
            return True, "境内交易时段 · 操作前核对 513300 溢价及是否停牌"
        next_open = break_end if opening <= local < break_end else opening
        return False, "下次境内交易窗口："+next_open.strftime("%Y-%m-%d %H:%M")+"（北京时间）"
    return False, "境内当前休市，请核对交易日历。"


def demo_prices(now):
    end = pd.Timestamp(now).tz_convert("America/New_York").date()
    sessions = mcal.get_calendar("NASDAQ").schedule(start_date=end-pd.Timedelta(days=760), end_date=end).index
    rng = np.random.default_rng(17)
    close = 350*np.exp(np.cumsum(rng.normal(0.0005, 0.012, len(sessions))))
    opening = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"Open": opening, "High": np.maximum(opening, close)*1.006,
                         "Low": np.minimum(opening, close)*0.994, "Close": close}, index=sessions)
