# GitHub Setup

This folder must be the GitHub repository root.

The daily mail workflow is stored at `.github/workflows/daily_update.yml`.
It runs every day at `23:00 UTC` and can also be started manually with `workflow_dispatch`.

## Required GitHub Secrets

Set these repository secrets before enabling the workflow:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`

Optional:

- `FRED_API_KEY`

## Push This Project

Run these commands from this folder:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

## Notes

- GitHub Actions cron uses UTC, not local time.
- The workflow sends the email by running `python main.py`.
- If market data is stale or unavailable, the workflow may still complete with missing indicators, but it will not silently use stale BIS CSV data as fresh output.
