# Eurodollar Stress Index Lite (ESI-Lite)

ESI-Lite 是一个零成本起步的离岸美元 / Eurodollar 压力监测项目。  
它使用免费官方数据源，生成两类主输出：

- 本地只读 `Streamlit` dashboard
- 每日邮件发送的 `PDF` 摘要

项目默认不把 `CSV` 作为主输出；`dashboard_data/` 和 `outputs/` 才是面板与报告的输入。

## 方案定位

- 免费数据优先：FRED、New York Fed、BIS
- 自动化友好：支持 GitHub Actions 每日更新
- 本地查看友好：`app.py` 只读取已生成的本地 JSON / PNG / PDF
- 邮件友好：`main.py` 生成 HTML 摘要并尝试通过 SMTP 发送 PDF 附件
- 降级安全：单一数据源失败不会导致整条流水线退出

## 当前实现

### 核心指标

- SOFR: Secured Overnight Financing Rate，反映美国担保隔夜融资利率水平。
- OBFR: Overnight Bank Funding Rate，反映美国银行隔夜无担保融资成本。
- SOFR - OBFR Spread: SOFR 与 OBFR 的利差，用于观察担保与无担保融资之间的张力。
- SOFR 20D Volatility: SOFR 的 20 日滚动波动率，用于刻画短端利率扰动强度。
- SOFR 5D Change: SOFR 的 5 日变化，跟踪短期利率的快速上移或回落。
- OBFR 5D Change: OBFR 的 5 日变化，跟踪银行无担保融资成本的短期变动。
- SOFR Volume: SOFR 成交量，量能收缩通常意味着流动性更脆弱。
- 30-Day Average SOFR: 30 日平均 SOFR，用于平滑观察短端资金价格趋势。
- 180-Day Average SOFR: 180 日平均 SOFR，用于提供更长周期的资金价格基准。
- 30D Avg SOFR - SOFR: 30 日平均 SOFR 与当日 SOFR 的利差，用于识别近期利率偏离趋势的程度。
- BIS USD Credit YoY: BIS 口径美国境外非银部门美元信贷同比，反映全球美元信用扩张或收缩。

### 增强接口（预留，默认不启用）

- FRA-OIS: 远期利率协议与隔夜指数掉期利差，常用于衡量银行间信用与流动性压力。
- CP-OIS: 商业票据与 OIS 利差，反映企业短期融资市场的紧张程度。
- EUR/USD basis: 欧元兑美元交叉货币 basis，反映离岸美元融资溢价。
- USD/JPY basis: 美元兑日元交叉货币 basis，反映亚洲美元融资压力。
- ON RRP: 美联储隔夜逆回购使用量，反映体系内流动性停泊情况。
- SRF: 常备回购便利使用量，反映机构对美联储流动性支持的依赖程度。

## 输出文件

### Dashboard 输入

- `dashboard_data/latest_snapshot.json`
- `dashboard_data/history.json`
- `dashboard_data/indicator_status.json`
- `outputs/metadata.json`
- `outputs/plots/*.png`

### 报告输出

- `outputs/daily_summary.pdf`
- `outputs/email_summary.html`

## 本地运行

### 1) 创建虚拟环境

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2) 安装依赖

```bash
pip install -r requirements.txt
```

### 3) 配置环境变量

复制样例文件：

```bash
cp .env.example .env
```

邮件发送依赖以下环境变量：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`

说明：

- `FRED_API_KEY` 不是必需项；Lite 版支持官方公开 CSV 回退
- BIS 默认走官方 API，失败后会尝试本地 `data/bis_usd_credit.csv`

### 4) 生成数据与报告

```bash
python main.py
```

该命令会：

- 抓取可用官方数据
- 计算指标与 ESI-Lite
- 生成 JSON、PNG、HTML、PDF
- 尝试通过 SMTP 发信
- 将邮件状态写入 `outputs/metadata.json`

### 5) 启动只读 dashboard

```bash
streamlit run app.py
```

如果结果文件不存在，`app.py` 会提示先运行 `python main.py`。

## GitHub Actions 启用

### 1) 推送到 GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-org>/<your-repo>.git
git push -u origin main
```

### 2) 启用 workflow

- 打开仓库 `Actions`
- 允许仓库运行 workflow
- 视需要手动触发 `workflow_dispatch`

### 3) 配置 GitHub Secrets

至少配置邮件相关 secrets：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`

可选：

- `FRED_API_KEY`

### 4) 调整定时任务

workflow 文件位于：

```text
.github/workflows/daily_update.yml
```

默认 cron：

```yaml
- cron: '0 20 * * *'
```

重要说明：

- GitHub Actions 使用 UTC
- 如需更贴近美东收盘后运行，请自行调整到更合适的 UTC 时间

## 配置说明

`config.yaml` 中最关键的配置项：

- `fred.series`
- `bis.mode`
- `bis.series.usd_credit_yoy`
- `indicators.definitions`
- `stress_index.regimes`
- `output.directories`
- `output.files`
- `email.smtp`

当前默认设置：

- FRED 使用官方 CSV 回退，因此无 key 也可跑
- BIS 默认 `auto`
- `BIS USD Credit YoY` 在代码中按季度同比计算后再做低频前填充
- `contribution.png` 为贡献图主文件名

## 重要提醒

### Dashboard 不是实时抓数

`app.py` 只读取本地结果文件，不做全量实时抓数。  
这保证了：

- 启动快
- 逻辑简单
- 本地和 CI 行为一致

### Lite 版的边界

- 缺少付费市场数据时，增强指标会显示 unavailable
- 综合指数会对剩余可用指标自动重归一化
- `2020-03` 这类极端阶段，Lite 指标集的刻画可能弱于专业资金市场数据组合

### 历史事件验证

项目会在输出中检查：

- 2019-09 repo spike
- 2020-03 COVID funding stress
- 2023-03 US regional bank stress

其中 `2020-03` 的验证应结合报告中的说明阅读，不建议把 Lite 指数视为完整替代品。

## 常见问题

### 1) 运行 `streamlit run app.py` 后提示没有数据

先执行：

```bash
python main.py
```

### 2) BIS 自动抓取失败

检查：

- `config.yaml` 中 `bis.mode`
- 本地 `data/bis_usd_credit.csv` 是否存在
- `outputs/metadata.json` 中的 `source_status`

### 3) 邮件发送失败

检查：

- SMTP 参数是否写入环境变量或 GitHub Secrets
- Gmail 是否使用 App Password
- `outputs/metadata.json` 中的 `mail_status`

## 升级方向

- 接入 FRA-OIS / CP-OIS
- 接入 EUR/USD 与 USD/JPY basis
- 增强 ON RRP / SRF 数据源
- 增加更丰富的邮件模板
- 在线部署 dashboard

更多建议见 `UPGRADE_GUIDE.md`。
