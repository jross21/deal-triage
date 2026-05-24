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

def compute_risk_score(row):
    """Return a 0–100 risk score. Higher means more at-risk."""
    score = 0
    stage = row.get("stage", "")

    # 1. Days in stage — max 40 pts (linear to 2× stage threshold)
    threshold = STAGE_THRESHOLDS.get(stage, 14)
    try:
        days_in = int(row.get("days_in_stage", 0))
    except (ValueError, TypeError):
        days_in = 0
    score += min(40, int(days_in / threshold * 20))

    # 2. Activity recency — max 30 pts
    try:
        last_act = date.fromisoformat(str(row["last_activity_date"]))
        stale = max(0, (TODAY - last_act).days)
        if stale >= 21:
            score += 30
        elif stale >= 14:
            score += 22
        elif stale >= 7:
            score += 14
        else:
            score += int(stale / 7 * 14)
    except (ValueError, TypeError, KeyError):
        score += 15

    # 3. Close date pressure — max 30 pts
    try:
        close = date.fromisoformat(str(row["close_date"]))
        days_until = (close - TODAY).days
        if days_until < 0:
            score += 30
        elif days_until < 14:
            score += 25
        elif days_until <= 30:
            score += 15
        elif days_until <= 60:
            score += 5
    except (ValueError, TypeError, KeyError):
        score += 10

    return min(100, score)


def score_deals(df):
    """Filter to open stages, compute risk scores, return sorted descending."""
    open_df = df[df["stage"].isin(OPEN_STAGES)].copy()
    open_df["risk_score"] = open_df.apply(lambda r: compute_risk_score(r.to_dict()), axis=1)
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
st.header("Deal Triage")
st.caption("Upload your CRM export to surface deals most likely to slip this quarter.")

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
# Score and rank
# ---------------------------------------------------------------------------
scored = score_deals(df_raw)
top10 = scored.head(TOP_N).copy()

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Open Deals", len(scored))
c2.metric("Top At-Risk", min(TOP_N, len(scored)))
c3.metric("Open Pipeline", f"${int(scored['amount'].sum()):,}")

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
st.dataframe(table_df, use_container_width=True, hide_index=True)

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

CONFIDENCE_BADGE = {"High": "🔴 High", "Medium": "🟡 Medium", "Low": "🟢 Low"}

for rank, (_, row) in enumerate(top10.iterrows(), start=1):
    label = f"#{rank} — {row['account_name']}  ·  {row['stage']}  ·  Risk score: {row['risk_score']}/100"
    with st.expander(label, expanded=(rank == 1)):
        m1, m2, m3 = st.columns(3)
        m1.metric("Amount", f"${int(row['amount']):,}")
        m2.metric("Days in Stage", int(row["days_in_stage"]))
        m3.metric("Close Date", str(row["close_date"]))

        next_step = row.get("next_step") or "—"
        st.write(f"**Owner:** {row['owner']}  |  **Next Step:** {next_step}")
        st.write(f"**Industry:** {row['industry']}  |  **Employees:** {int(row['employee_count']):,}")

        explanation = st.session_state.explanations.get(row["deal_id"])
        if explanation:
            st.markdown("---")
            confidence_label = CONFIDENCE_BADGE.get(explanation.get("confidence", ""), "⚪ Unknown")
            st.markdown(f"**Confidence:** {confidence_label}")
            st.markdown(f"**Risk:** {explanation.get('risk_explanation', '')}")
            st.markdown(f"**Suggested action this week:** {explanation.get('next_action', '')}")
        elif st.session_state.explanations:
            st.caption("Explanation unavailable for this deal.")
