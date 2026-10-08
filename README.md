# QQQ 波段观察

面向在境内买卖 513300、持仓几天到几周的用户。读取 QQQ 已收盘日线，通过 Supertrend（默认 ATR 10 / 倍数 3）显示买入观察、持有观察、卖出或减仓观察。持仓持续时间由趋势决定，可能超过几周。

## 本地使用

已经安装依赖时，双击 `启动页面.cmd`。浏览器打开 http://localhost:8501。

在另一台电脑上，安装 Python 3.11 或更高版本，在此文件夹执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

## 发布到 Streamlit Community Cloud

将这个文件夹的全部内容（包括 `.streamlit/config.toml`）放到你的 GitHub 仓库。登录 Streamlit Community Cloud，创建应用，选择仓库、分支和 `app.py`，选择 Python 3.12 后部署。若文件夹保留在仓库子目录中，入口填写该子目录下的 `app.py` 路径，依赖文件保持与入口同目录。

公网应用：https://qqq-513300-dashboard.streamlit.app/

代码仓库：https://github.com/LHY116001/qqq-513300-dashboard

部署说明：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## 信号与时间

- 普通日线、未复权 OHLC。ATR 使用 Wilder 平滑，首次以前 N 根真实波幅均值初始化。
- NASDAQ 交易日历确认正常交易时段收盘，额外等待 15 分钟。剔除未收盘、非交易日及未来日线；缺少最近应收盘日或近期日线有缺口，暂停建议。
- 最新日线出现趋势切换才称为新买卖信号。旧买点不被重复当作新买点。
- 境内交易时段及下一次开市取自 SSE 日历，考虑午休；日历实际安排以交易所公告为准。
- 页面打开时每 5 分钟检查，最新信号在境内交易时段弹出页面提醒，每个浏览器会话内去重。关闭页面后不会继续监控或向手机推送。浏览器后台可能节流，页面提醒不能保证准时送达。
- 在线数据检查失败时暂停建议，不会用模拟行情冒充实时行情。可上传真实 QQQ CSV；模拟示例明确禁用操作建议。
- 随附 `qqq_snapshot.csv` 是已实际下载的真实 QQQ 日线，截止美股交易日 2026-10-02。网络不佳时可在“观察设置”中明确选择“已下载 QQQ 行情快照”；新的交易日收盘后若快照未更新，会暂停建议。它不会冒充在线更新的行情。
- CSV 列名为 Date,Open,High,Low,Close；Date 为美股交易日，价格须为 QQQ 未复权日线。上传来源由用户自行核实。

## 使用边界

参数没有针对 513300 的收益验证。本应用不执行下单，不提供收益回测或胜率。QQQ 信号不等于 513300 的人民币成交价格；操作前核对基金溢价、净值日期、买卖价差、汇率及停牌公告。页面“趋势参考线”不是直接可执行的 513300 止损价。

在线行情来源为 Yahoo Finance，通过 yfinance 读取，可能延迟或不可用。不要将其视为交易所实时数据接口。
