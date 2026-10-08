# Streamlit Cloud 发布配置

公网应用：https://qqq-513300-dashboard.streamlit.app/

代码仓库：https://github.com/LHY116001/qqq-513300-dashboard 。仓库仅存放本应用文件，不上传虚拟环境、工作文件或账号凭据。

| 配置 | 值 |
| --- | --- |
| 分支 | main |
| 入口文件 | app.py |
| Python 版本 | 3.12 |
| 依赖 | requirements.txt |
| 配色 | .streamlit/config.toml |
| Secrets | 本版不需要 |

正常入口使用在线 QQQ 行情。接口失败时暂停建议，可明确选择已下载的真实行情快照；模拟数据不提供操作建议。2026-10-08 部署时，在线行情已读取到 2026-10-07 的收盘日线。

这版页面提醒仅在页面打开时检查，不包含后台手机推送。
