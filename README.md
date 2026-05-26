# Deal Triage

B2B SaaS pipeline risk scoring — heuristic signals + Claude explanations for AEs and RevOps managers.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://deal-triage-julian-ross.streamlit.app)

![Deal Triage screenshot](docs/assets/screenshot.png)

## What it does

AEs and managers lose deals because nobody notices them slipping until it's too late. Spreadsheet pipeline reviews are slow, subjective, and miss subtle signals like a deal that's been in Proposal for 45 days with no activity and a close date two weeks out.

Deal Triage ingests a CRM export (HubSpot-style CSV), scores every open deal on three heuristic dimensions, and surfaces the top 10 at-risk deals. With an Anthropic API key, it calls Claude to generate a one-paragraph risk explanation grounded in specific CRM signals and call transcript quotes — plus a concrete next action for the AE to take this week.

## How it works

### Heuristic scoring (0–100 per deal)

| Dimension | Max pts | Logic |
|-----------|---------|-------|
| Days in stage | 40 | Linear to 2× stage threshold (Discovery/Demo: 14 days, Proposal/Negotiation: 21 days) |
| Activity recency | 30 | 0–6 days stale: 0–13 pts · 7–13 days: 14 pts · 14–20 days: 22 pts · 21+ days: 30 pts |
| Close date pressure | 30 | Past due: 30 · <14 days: 25 · 15–30 days: 15 · 31–60 days: 5 · 60+ days: 0 |

Closed Won and Closed Lost deals are filtered out before scoring. Only open pipeline is ranked.

### Claude layer (optional)

For each of the top 10 at-risk deals, Claude (`claude-haiku-4-5`) reads the CRM fields and — when a transcript snippet is available — quotes from the call to explain the risk, assign a confidence level (High / Medium / Low), and suggest a specific action. The prompt lives in `prompts/deal_risk_explanation.md` so the reasoning is fully transparent and easy to tune.

Results are cached in session state — the API is only called when you click "Analyze with Claude," not on every UI interaction.

## Getting started

**Prerequisites:** Python 3.9+, pip

```bash
git clone https://github.com/jross21/deal-triage.git
cd deal-triage
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app loads with 100 synthetic deals automatically — no API key needed to see the scoring view.

**To enable Claude explanations:**

```bash
cp .env.example .env
# open .env and set ANTHROPIC_API_KEY=your_key_here
streamlit run app.py
```

An "Analyze with Claude" button will appear. Click it to generate explanations for the top 10 at-risk deals (~15 seconds for all 10).

## CSV format

Upload any CSV with these fields:

| Field | Type | Notes |
|-------|------|-------|
| `deal_id` | string | Unique identifier |
| `account_name` | string | Company name |
| `stage` | string | `Discovery`, `Demo`, `Proposal`, `Negotiation`, `Closed Won`, `Closed Lost` |
| `amount` | number | Deal value in dollars |
| `close_date` | YYYY-MM-DD | Expected close |
| `days_in_stage` | integer | Days since last stage change |
| `last_activity_date` | YYYY-MM-DD | Most recent logged activity |
| `next_step` | string | AE's documented next action (can be blank) |
| `owner` | string | AE name |
| `industry` | string | Account industry |
| `employee_count` | integer | Account headcount |

## Project structure

```
deal-triage/
├── app.py                         # Streamlit app — scorer + Claude integration
├── prompts/
│   └── deal_risk_explanation.md  # Claude prompt template (readable, editable)
├── data/sample/
│   ├── opportunities.csv         # 100 synthetic deals — ships with the app
│   └── transcripts/              # 15 call transcript snippets, keyed by deal_id
├── scripts/
│   └── generate_sample_data.py  # Reproducible data generator (seed=42)
├── .env.example                  # API key template
└── requirements.txt
```

To regenerate the sample data:

```bash
python3 scripts/generate_sample_data.py
```

## Roadmap

**v2 — Live data**
n8n workflow that pulls open opportunities from HubSpot on a daily schedule, runs the same scoring pipeline, and posts a Slack digest of the top at-risk deals to the team channel. No manual CSV export required.

**v3 — Warehouse model**
dbt project modeling deal signal data — stage velocity, rep activity patterns, win/loss rates by segment — so the heuristic weights can be tuned against actual historical outcomes rather than rules of thumb.

## Built with

Python · [Streamlit](https://streamlit.io) · [Anthropic Claude](https://anthropic.com) · pandas · python-dotenv
