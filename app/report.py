"""Generate a standalone weekly marketing HTML report."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

try:
    from app.analyzer import load_and_analyze_data
    from app.insights import generate_insights
except ImportError:
    from analyzer import load_and_analyze_data
    from insights import generate_insights


DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "campaigns.csv"
DEFAULT_OUTPUT_PATH = "reports/weekly_report.html"
INSIGHT_ORDER = ("victoire", "alerte", "recommandation")
INSIGHT_LABELS = {
    "victoire": "Victoire",
    "alerte": "Alerte",
    "recommandation": "Recommandation",
}


def format_currency(value: float) -> str:
    """Format a numeric value as USD currency."""
    return f"${value:,.2f}"


def _format_number(value: Any) -> str:
    """Format integer-like values for display."""
    return f"{int(value):,}"


def _format_percentage(value: Any) -> str:
    """Format percentage values for display."""
    return f"{float(value):.2f}%"


def _format_roas(value: Any) -> str:
    """Format ROAS values for display."""
    return f"{float(value):.2f}x"


def _fallback_insights_message(error: Exception) -> dict[str, list[dict[str, str]]]:
    """Build a stable fallback insights payload when generation fails."""
    message = (
        "Les insights automatiques ne sont pas disponibles pour cette generation de rapport. "
        f"Detail technique: {error}"
    )
    return {
        "insights": [
            {
                "type": "victoire",
                "title": "Insights indisponibles",
                "message": message,
            },
            {
                "type": "alerte",
                "title": "Generation a verifier",
                "message": "L analyse KPI reste disponible, mais la production des insights a echoue.",
            },
            {
                "type": "recommandation",
                "title": "Relancer la generation",
                "message": "Verifiez la configuration OpenAI ou utilisez le mode fallback local avant le prochain envoi.",
            },
        ]
    }


def _normalize_insights(insights: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return insight blocks keyed by expected type."""
    normalized: dict[str, dict[str, str]] = {}

    for item in insights.get("insights", []):
        if not isinstance(item, dict):
            continue
        insight_type = str(item.get("type", "")).strip().lower()
        if insight_type not in INSIGHT_ORDER or insight_type in normalized:
            continue
        normalized[insight_type] = {
            "title": str(item.get("title", "")).strip() or INSIGHT_LABELS[insight_type],
            "message": str(item.get("message", "")).strip() or "Aucun message disponible.",
        }

    for insight_type in INSIGHT_ORDER:
        normalized.setdefault(
            insight_type,
            {
                "title": INSIGHT_LABELS[insight_type],
                "message": "Insight non disponible.",
            },
        )

    return normalized


def generate_html_report(data: dict[str, Any], insights: dict[str, Any]) -> str:
    """Build the full standalone HTML report."""
    summary = data.get("summary", {})
    campaigns = data.get("campaigns", [])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_insights = _normalize_insights(insights)

    insight_blocks = "\n".join(
        f"""
        <article class="insight-card {insight_type}">
            <p class="insight-type">{escape(INSIGHT_LABELS[insight_type])}</p>
            <h3>{escape(normalized_insights[insight_type]["title"])}</h3>
            <p>{escape(normalized_insights[insight_type]["message"])}</p>
        </article>
        """
        for insight_type in INSIGHT_ORDER
    )

    table_rows = "\n".join(
        f"""
        <tr>
            <td>{escape(str(campaign.get("campaign", "N/A")))}</td>
            <td>{format_currency(float(campaign.get("spend", 0.0)))}</td>
            <td>{_format_number(campaign.get("impressions", 0))}</td>
            <td>{_format_number(campaign.get("clicks", 0))}</td>
            <td>{_format_number(campaign.get("conversions", 0))}</td>
            <td>{format_currency(float(campaign.get("revenue", 0.0)))}</td>
            <td>{_format_percentage(campaign.get("ctr", 0.0))}</td>
            <td>{_format_roas(campaign.get("roas", 0.0))}</td>
        </tr>
        """
        for campaign in campaigns
    )

    if not table_rows:
        table_rows = """
        <tr>
            <td colspan="8" class="empty-state">No campaign data available.</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Marketing Performance Report</title>
    <style>
        :root {{
            --bg: #f3f6fb;
            --panel: #ffffff;
            --panel-alt: #f8fbff;
            --text: #18212f;
            --muted: #5f6b7a;
            --border: #dbe3ee;
            --shadow: 0 18px 40px rgba(16, 24, 40, 0.08);
            --primary: #145da0;
            --primary-soft: #eaf4ff;
            --success: #1f7a4d;
            --success-soft: #e9f8f0;
            --warning: #b35a00;
            --warning-soft: #fff3e8;
            --accent: #5c3b8a;
            --accent-soft: #f3ebff;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(180deg, #eef4fb 0%, #f7f9fc 100%);
            color: var(--text);
        }}

        .container {{
            width: min(1180px, calc(100% - 48px));
            margin: 0 auto;
            padding: 40px 0 56px;
        }}

        .hero {{
            background: linear-gradient(135deg, #123b63, #145da0 58%, #3b82c4);
            color: #ffffff;
            border-radius: 24px;
            padding: 36px 40px;
            box-shadow: var(--shadow);
        }}

        .hero h1 {{
            margin: 0 0 12px;
            font-size: 2rem;
            line-height: 1.2;
        }}

        .hero p {{
            margin: 0;
            color: rgba(255, 255, 255, 0.86);
            font-size: 0.98rem;
        }}

        .section {{
            margin-top: 28px;
            background: var(--panel);
            border: 1px solid rgba(219, 227, 238, 0.9);
            border-radius: 20px;
            padding: 28px;
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.05);
        }}

        .section h2 {{
            margin: 0 0 20px;
            font-size: 1.25rem;
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 18px;
        }}

        .kpi-card {{
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 20px;
        }}

        .kpi-card .label {{
            margin: 0 0 10px;
            color: var(--muted);
            font-size: 0.9rem;
        }}

        .kpi-card .value {{
            margin: 0;
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 18px;
        }}

        .insight-card {{
            border-radius: 18px;
            padding: 22px;
            border: 1px solid transparent;
        }}

        .insight-card h3 {{
            margin: 0 0 10px;
            font-size: 1.1rem;
        }}

        .insight-card p {{
            margin: 0;
            line-height: 1.6;
        }}

        .insight-type {{
            margin: 0 0 10px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.75rem;
            font-weight: 700;
        }}

        .victoire {{
            background: var(--success-soft);
            border-color: #bfe5d0;
        }}

        .victoire .insight-type {{
            color: var(--success);
        }}

        .alerte {{
            background: var(--warning-soft);
            border-color: #f2cfab;
        }}

        .alerte .insight-type {{
            color: var(--warning);
        }}

        .recommandation {{
            background: var(--accent-soft);
            border-color: #dccdf7;
        }}

        .recommandation .insight-type {{
            color: var(--accent);
        }}

        .table-wrap {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 760px;
        }}

        thead th {{
            background: #f4f7fb;
            color: var(--muted);
            text-align: left;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        th, td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
        }}

        tbody tr:hover {{
            background: #f9fbfd;
        }}

        tbody td {{
            font-size: 0.96rem;
        }}

        .empty-state {{
            text-align: center;
            color: var(--muted);
            padding: 28px;
        }}

        @media (max-width: 960px) {{
            .kpi-grid,
            .insights-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}

        @media (max-width: 640px) {{
            .container {{
                width: min(100% - 24px, 1180px);
                padding-top: 24px;
            }}

            .hero,
            .section {{
                padding: 22px;
            }}

            .kpi-grid,
            .insights-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <section class="hero">
            <h1>Weekly Marketing Performance Report</h1>
            <p>Generated on {escape(generated_at)}</p>
        </section>

        <section class="section">
            <h2>KPI Summary</h2>
            <div class="kpi-grid">
                <article class="kpi-card">
                    <p class="label">Total Spend</p>
                    <p class="value">{format_currency(float(summary.get("total_spend", 0.0)))}</p>
                </article>
                <article class="kpi-card">
                    <p class="label">Total Impressions</p>
                    <p class="value">{_format_number(summary.get("total_impressions", 0))}</p>
                </article>
                <article class="kpi-card">
                    <p class="label">Global CTR</p>
                    <p class="value">{_format_percentage(summary.get("global_ctr", 0.0))}</p>
                </article>
                <article class="kpi-card">
                    <p class="label">Global ROAS</p>
                    <p class="value">{_format_roas(summary.get("global_roas", 0.0))}</p>
                </article>
            </div>
        </section>

        <section class="section">
            <h2>Insights</h2>
            <div class="insights-grid">
                {insight_blocks}
            </div>
        </section>

        <section class="section">
            <h2>Campaign Performance</h2>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Campaign</th>
                            <th>Spend</th>
                            <th>Impressions</th>
                            <th>Clicks</th>
                            <th>Conversions</th>
                            <th>Revenue</th>
                            <th>CTR</th>
                            <th>ROAS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </section>
    </main>
</body>
</html>
"""


def save_report(html: str, output_path: str = DEFAULT_OUTPUT_PATH) -> str:
    """Save the HTML report to disk and return the resolved output path."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding="utf-8")
    return str(output_file.resolve())


if __name__ == "__main__":
    analysis = load_and_analyze_data(DEFAULT_CSV_PATH)

    try:
        insights_payload = generate_insights(analysis)
    except Exception as exc:
        insights_payload = _fallback_insights_message(exc)

    report_html = generate_html_report(analysis, insights_payload)
    final_path = save_report(report_html)
    print(final_path)
