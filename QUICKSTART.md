# ESI-Lite 快速开始

下面是最短可跑通路径。

## 1. 进入项目目录

```bash
cd eurodollar_stress_lite
```

## 2. 创建并激活虚拟环境

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

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 4. 配置环境变量

复制样例：

```bash
cp .env.example .env
```

至少在需要发邮件时配置：

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_user
SMTP_PASSWORD=your_password
MAIL_FROM=sender@example.com
MAIL_TO=recipient@example.com
```

说明：

- `FRED_API_KEY` 可留空
- BIS 默认自动抓取，失败后尝试本地 CSV

## 5. 生成数据

```bash
python main.py
```

成功后会生成：

- `dashboard_data/latest_snapshot.json`
- `dashboard_data/history.json`
- `dashboard_data/indicator_status.json`
- `outputs/daily_summary.pdf`
- `outputs/email_summary.html`
- `outputs/metadata.json`

## 6. 打开 dashboard

```bash
streamlit run app.py
```

## 7. 最快检查点

确认以下文件存在：

```text
dashboard_data/latest_snapshot.json
dashboard_data/history.json
dashboard_data/indicator_status.json
outputs/daily_summary.pdf
outputs/email_summary.html
outputs/metadata.json
outputs/plots/stress_index.png
outputs/plots/contribution.png
```

## 8. GitHub Actions

默认 workflow：

```text
.github/workflows/daily_update.yml
```

默认 cron 为 UTC。  
如果你希望靠近美东收盘后运行，请自行调整 cron。
