# Automated Marketing Insights

A simple Python project for analyzing marketing campaign performance, generating AI-powered weekly insights, rendering an HTML report, and delivering that report by email or Slack.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the repository root.

## Environment Variables

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini

EMAIL_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@example.com
EMAIL_TO=marketing-team@example.com

SLACK_ENABLED=false
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
```

## Run Locally

Run the analyzer script from the repository root:

```bash
python app/analyzer.py
```

Generate weekly insights:

```bash
python app/insights.py
```

Generate the HTML report:

```bash
python app/report.py
```

Run the scheduler:

```bash
python app/scheduler.py
```

## Scheduler Behavior

- `RUN_ON_START = True` runs the full reporting pipeline immediately when the scheduler starts.
- `TEST_MODE = True` schedules the job every 1 minute for local development.
- `TEST_MODE = False` schedules the job every Monday at 08:00 in `America/Vancouver`.

The scheduler pipeline now:

1. Loads campaign data from `data/campaigns.csv`
2. Generates structured insights
3. Saves the HTML report to `reports/weekly_report.html`
4. Attempts delivery through enabled email and Slack channels

## Delivery Notes

- Email delivery uses `smtplib` and standard library email MIME helpers.
- If the HTML report file exists, it is attached to the email.
- Slack delivery uses a simple incoming webhook.
- Disabled channels are skipped cleanly.
- Delivery results are printed in the scheduler logs.
