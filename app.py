import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TODAY = date.today()
SAMPLE_CSV = Path("data/sample/opportunities.csv")
TRANSCRIPT_DIR = Path("data/sample/transcripts")
PROMPT_DIR = Path("prompts")
TOP_N = 10
OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}
STAGE_THRESHOLDS = {"Discovery": 14, "Demo": 14, "Proposal": 21, "Negotiation": 21}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_prompt(name):
    path = PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def find_transcript(deal_id):
    matches = list(TRANSCRIPT_DIR.glob(f"{deal_id}_*.txt"))
    return matches[0].read_text(encoding="utf-8") if matches else ""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_risk_breakdown(row):
    """Return (total_score, breakdown_dict) for a deal row.

    breakdown_dict keys: stage_pts (max 40), act_pts (max 30), close_pts (max 30).
    """
    stage = row.get("stage", "")
    threshold = STAGE_THRESHOLDS.get(stage, 14)

    # 1. Days in stage — max 40 pts (linear to 2× stage threshold)
    try:
        days_in = int(row.get("days_in_stage", 0))
    except (ValueError, TypeError):
        days_in = 0
    stage_pts = min(40, int(days_in / threshold * 20))

    # 2. Activity recency — max 30 pts
    try:
        last_act = date.fromisoformat(str(row["last_activity_date"]))
        stale = max(0, (TODAY - last_act).days)
        if stale >= 21:
            act_pts = 30
        elif stale >= 14:
            act_pts = 22
        elif stale >= 7:
            act_pts = 14
        else:
            act_pts = int(stale / 7 * 14)
    except (ValueError, TypeError, KeyError):
        act_pts = 15

    # 3. Close date pressure — max 30 pts
    try:
        close = date.fromisoformat(str(row["close_date"]))
        days_until = (close - TODAY).days
        if days_until < 0:
            close_pts = 30
        elif days_until < 14:
            close_pts = 25
        elif days_until <= 30:
            close_pts = 15
        elif days_until <= 60:
            close_pts = 5
        else:
            close_pts = 0
    except (ValueError, TypeError, KeyError):
        close_pts = 10

    total = min(100, stage_pts + act_pts + close_pts)
    return total, {"stage_pts": stage_pts, "act_pts": act_pts, "close_pts": close_pts}


def compute_risk_score(row):
    """Return a 0–100 risk score. Higher means more at-risk."""
    return compute_risk_breakdown(row)[0]


def score_deals(df):
    """Filter to open stages, compute risk scores and breakdowns, return sorted descending."""
    open_df = df[df["stage"].isin(OPEN_STAGES)].copy()
    results = open_df.apply(lambda r: compute_risk_breakdown(r.to_dict()), axis=1)
    open_df["risk_score"] = results.apply(lambda x: x[0])
    open_df["_stage_pts"] = results.apply(lambda x: x[1]["stage_pts"])
    open_df["_act_pts"]   = results.apply(lambda x: x[1]["act_pts"])
    open_df["_close_pts"] = results.apply(lambda x: x[1]["close_pts"])
    return open_df.sort_values("risk_score", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Claude integration
# ---------------------------------------------------------------------------

def get_claude_explanation(row, transcript=""):
    """Call Claude to generate a risk explanation, confidence, and next action.

    Returns a dict with keys risk_explanation, confidence, next_action,
    or None if the API key is missing or the call fails.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

    prompt_template = load_prompt("deal_risk_explanation")
    if not prompt_template:
        return None

    deal_data = "\n".join([
        f"- Account: {row['account_name']}",
        f"- Stage: {row['stage']}",
        f"- Amount: ${int(row['amount']):,}",
        f"- Close Date: {row['close_date']}",
        f"- Days in Stage: {row['days_in_stage']}",
        f"- Last Activity: {row['last_activity_date']}",
        f"- Next Step: {row.get('next_step') or 'None'}",
        f"- Owner: {row['owner']}",
        f"- Industry: {row['industry']}",
        f"- Employee Count: {int(row['employee_count']):,}",
        f"- Risk Score: {row['risk_score']}/100",
        f"- Score breakdown: Stage {row.get('_stage_pts', 0)}/40 · Activity {row.get('_act_pts', 0)}/30 · Close {row.get('_close_pts', 0)}/30",
    ])

    transcript_section = (
        f"\nCall transcript excerpt:\n{transcript[:2000]}" if transcript else ""
    )

    prompt = (
        prompt_template
        .replace("{deal_data}", deal_data)
        .replace("{transcript_section}", transcript_section)
    )

    try:
        client = Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(text[start:end])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Deal Triage", layout="wide")

st.markdown("""<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.stDeployButton { display: none !important; }

/* ── App shell ── */
.main .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1080px; }
.stApp { background: #f8fafc; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
}
[data-testid="stMetricLabel"] > div {
    color: #64748b !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
}
[data-testid="stMetricValue"] > div {
    color: #0f172a !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #0f172a !important; }
[data-testid="stSidebar"] label {
    color: #94a3b8 !important;
    font-size: 0.65rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* ── Deal expanders ── */
[data-testid="stExpander"] {
    background: white !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary { font-weight: 500; }

/* ── Hide dividers — spacing handled by padding ── */
hr { display: none !important; }
</style>""", unsafe_allow_html=True)

st.markdown("""
<div style="padding:0 0 1.5rem 0">
  <div style="font-size:1.75rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;line-height:1.2">Deal Triage</div>
  <div style="color:#64748b;margin-top:0.35rem;font-size:0.9rem">Upload your CRM export to surface deals most likely to slip this quarter.</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
uploaded = st.file_uploader(
    "Upload opportunities CSV", type="csv", label_visibility="collapsed"
)

if uploaded is not None:
    df_raw = pd.read_csv(uploaded)
elif SAMPLE_CSV.exists():
    df_raw = pd.read_csv(SAMPLE_CSV)
    st.info("Showing sample data — upload your own CSV above to analyze real deals.")
else:
    st.error(
        f"Sample data not found at `{SAMPLE_CSV}`. "
        "Run `python3 scripts/generate_sample_data.py` from the project root first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Validate CSV columns
# ---------------------------------------------------------------------------
REQUIRED_COLS = {
    "deal_id", "account_name", "stage", "amount", "close_date",
    "days_in_stage", "last_activity_date", "owner", "industry", "employee_count",
}
missing = REQUIRED_COLS - set(df_raw.columns)
if missing:
    st.error(
        f"CSV is missing required columns: **{', '.join(sorted(missing))}**  \n"
        "See the README for the full column spec."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Score and rank
# ---------------------------------------------------------------------------
scored = score_deals(df_raw)

# ---------------------------------------------------------------------------
# Sidebar — owner filter
# ---------------------------------------------------------------------------
all_owners = sorted(scored["owner"].unique().tolist())
selected_owner = st.sidebar.selectbox("Filter by owner", ["All"] + all_owners)
filtered = scored[scored["owner"] == selected_owner] if selected_owner != "All" else scored

top10 = filtered.head(TOP_N).copy()

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Open Deals", len(filtered))
c2.metric("Top At-Risk", min(TOP_N, len(filtered)))
c3.metric("Open Pipeline", f"${int(filtered['amount'].sum()):,}")

st.divider()

# ---------------------------------------------------------------------------
# Pipeline health chart
# ---------------------------------------------------------------------------
import altair as alt

st.subheader("Pipeline Health")

_STAGE_ORDER = ["Discovery", "Demo", "Proposal", "Negotiation"]
_TIER_COLORS = ["#dc2626", "#d97706", "#16a34a"]

def _risk_tier(score):
    return "High" if score >= 70 else "Medium" if score >= 40 else "Low"

chart_df = filtered.copy()
chart_df["Risk Tier"] = chart_df["risk_score"].apply(_risk_tier)
chart_df["stage"] = pd.Categorical(chart_df["stage"], categories=_STAGE_ORDER, ordered=True)

pipeline_chart = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        x=alt.X("stage:O", sort=_STAGE_ORDER, title="Stage"),
        y=alt.Y("count():Q", title="Deals"),
        color=alt.Color(
            "Risk Tier:N",
            scale=alt.Scale(domain=["High", "Medium", "Low"], range=_TIER_COLORS),
            legend=alt.Legend(title="Risk Tier"),
        ),
        order=alt.Order("Risk Tier:N", sort="ascending"),
        tooltip=["stage:O", "Risk Tier:N", "count():Q"],
    )
    .properties(height=240)
)
st.altair_chart(pipeline_chart, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
st.subheader("Top 10 At-Risk Deals")

table_df = top10[["account_name", "stage", "amount", "close_date",
                   "days_in_stage", "risk_score", "owner"]].copy()
table_df.insert(0, "#", range(1, len(table_df) + 1))
table_df["amount"] = table_df["amount"].apply(lambda v: f"${int(v):,}")
table_df.columns = ["#", "Account", "Stage", "Amount",
                    "Close Date", "Days in Stage", "Risk Score", "Owner"]
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "#":             st.column_config.NumberColumn(width="small"),
        "Account":       st.column_config.TextColumn(width="medium"),
        "Stage":         st.column_config.TextColumn(width="small"),
        "Amount":        st.column_config.TextColumn(width="small"),
        "Close Date":    st.column_config.TextColumn(width="small"),
        "Days in Stage": st.column_config.NumberColumn(width="small"),
        "Risk Score":    st.column_config.ProgressColumn(
                             "Risk Score",
                             min_value=0,
                             max_value=100,
                             format="%d",
                             width="medium",
                         ),
        "Owner":         st.column_config.TextColumn(width="small"),
    },
)

# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------
api_key = os.getenv("ANTHROPIC_API_KEY")

if "explanations" not in st.session_state:
    st.session_state.explanations = {}

st.divider()

if api_key:
    col_btn, col_note = st.columns([1, 4])
    with col_btn:
        analyze = st.button("Analyze with Claude", type="primary")
    with col_note:
        st.caption("Calls Claude once per deal — results are cached until you re-analyze.")
    if analyze:
        st.session_state.explanations = {}
        with st.spinner("Analyzing top deals with Claude (~15 seconds)…"):
            for _, row in top10.iterrows():
                transcript = find_transcript(str(row["deal_id"]))
                result = get_claude_explanation(row.to_dict(), transcript)
                st.session_state.explanations[row["deal_id"]] = result
else:
    st.info(
        "**AI explanations disabled.** Add `ANTHROPIC_API_KEY=your_key` to `.env` "
        "and restart to enable Claude-powered risk analysis."
    )

# ---------------------------------------------------------------------------
# Per-deal expanders
# ---------------------------------------------------------------------------
st.subheader("Deal Detail")

CONFIDENCE_BADGE = {
    "High":   '<span style="background:#fee2e2;color:#b91c1c;padding:2px 12px;border-radius:99px;font-size:0.75rem;font-weight:600">High</span>',
    "Medium": '<span style="background:#fef3c7;color:#92400e;padding:2px 12px;border-radius:99px;font-size:0.75rem;font-weight:600">Medium</span>',
    "Low":    '<span style="background:#dcfce7;color:#166534;padding:2px 12px;border-radius:99px;font-size:0.75rem;font-weight:600">Low</span>',
}

for rank, (_, row) in enumerate(top10.iterrows(), start=1):
    label = f"#{rank} — {row['account_name']}  ·  {row['stage']}  ·  Risk score: {row['risk_score']}/100"
    with st.expander(label, expanded=(rank == 1)):
        m1, m2, m3 = st.columns(3)
        m1.metric("Amount", f"${int(row['amount']):,}")
        m2.metric("Days in Stage", int(row["days_in_stage"]))
        m3.metric("Close Date", str(row["close_date"]))

        st.caption(
            f"Stage stagnation: {int(row['_stage_pts'])}/40  ·  "
            f"Activity gap: {int(row['_act_pts'])}/30  ·  "
            f"Close pressure: {int(row['_close_pts'])}/30"
        )

        next_step = row.get("next_step") or "—"
        st.write(f"**Owner:** {row['owner']}  |  **Next Step:** {next_step}")
        st.write(f"**Industry:** {row['industry']}  |  **Employees:** {int(row['employee_count']):,}")

        explanation = st.session_state.explanations.get(row["deal_id"])
        if explanation:
            st.markdown("---")
            confidence_label = CONFIDENCE_BADGE.get(explanation.get("confidence", ""), "<span>Unknown</span>")
            st.markdown(f"**Confidence:** {confidence_label}", unsafe_allow_html=True)
            st.markdown(f"**Risk:** {explanation.get('risk_explanation', '')}")
            st.markdown(f"**Suggested action this week:** {explanation.get('next_action', '')}")
        elif st.session_state.explanations:
            st.caption("Explanation unavailable for this deal.")
