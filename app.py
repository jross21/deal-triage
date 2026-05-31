import html
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import claude_client
import hubspot_client
import feedback as feedback_store
import ui
from constants import MIN_BENCHMARK_SAMPLE, OPEN_STAGES, STAGE_THRESHOLDS, TOP_N
from scoring import compute_risk_breakdown, compute_stage_benchmarks, risk_tier, score_deals
from transcripts import find_transcript

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TODAY = date.today()
SAMPLE_CSV = Path("data/sample/opportunities.csv")
METHODOLOGY_MD = Path("METHODOLOGY.md")

# Per-tier expander border styles (dark mode / light mode)
_TIER_BORDER = {
    "high":   "border:1px solid #fca5a5!important;box-shadow:0 2px 8px rgba(239,68,68,0.1)!important;",
    "medium": "border:1px solid #fde68a!important;box-shadow:0 2px 8px rgba(245,158,11,0.08)!important;",
    "low":    "border:1px solid #e2e8f0!important;",
}


def _format_pull_timestamp(dt: datetime) -> str:
    total = int((datetime.now() - dt).total_seconds())
    if total < 60:
        return "Just pulled"
    if total < 3600:
        return f"Pulled {total // 60}m ago"
    return f"Pulled {total // 3600}h ago"


# ---------------------------------------------------------------------------
# Cached Claude analysis
# ---------------------------------------------------------------------------
# Persist analysis across reruns/refreshes so a page reload doesn't re-pay for
# the top-10 calls. Keyed on deal_id + model + a fingerprint of the scored
# fields and transcript, so it re-analyzes only when the inputs actually change.
# Failures (None) are raised so they are NOT cached — the next run retries.

class _AnalysisFailed(Exception):
    pass


@st.cache_data(show_spinner=False)
def _cached_analyze(deal_id, model, fingerprint, _row, _transcript):
    result = claude_client.analyze_deal(_row, _transcript, model)
    if result is None:
        raise _AnalysisFailed
    return result


def analyze_fingerprint(row, transcript) -> str:
    return "|".join(str(x) for x in (
        row.get("risk_score"), row.get("stage"), row.get("days_in_stage"),
        row.get("last_activity_date"), row.get("close_date"), len(transcript),
    ))


def cached_analyze(row, transcript, model):
    """Cached wrapper around claude_client.analyze_deal; returns None on failure."""
    try:
        return _cached_analyze(
            str(row["deal_id"]), model, analyze_fingerprint(row, transcript),
            _row=row, _transcript=transcript,
        )
    except _AnalysisFailed:
        return None


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Deal Triage", layout="wide")

# ── CSS constants ──────────────────────────────────────────────────────────

CSS_SHARED = """
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.stDeployButton { display: none !important; }
.main .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1080px; }
hr { display: none !important; }
[data-testid="stMetricLabel"] > div {
    font-size: 0.7rem !important; text-transform: uppercase;
    letter-spacing: 0.07em; font-weight: 600;
}
[data-testid="stMetricValue"] > div { font-size: 1.75rem !important; font-weight: 700 !important; }
[data-testid="stExpander"] summary { font-weight: 600; }
.badge-high, .badge-medium, .badge-low {
    padding: 2px 12px; border-radius: 99px; font-size: 0.75rem; font-weight: 600;
}
"""

CSS_THEME = """
.stApp { background: #f8fafc; }
[data-testid="stMetric"] {
    background: white !important; border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important; padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stMetricLabel"] > div { color: #64748b !important; }
[data-testid="stMetricValue"] > div { color: #0f172a !important; }
[data-testid="stExpander"] {
    background: white !important; border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
}
[data-testid="stBaseButton-primary"] > button {
    background: linear-gradient(135deg, #0284c7, #38bdf8) !important;
    border: none !important; color: white !important; font-weight: 700 !important;
}
.chart-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 1rem 1.25rem 0.25rem; margin-bottom: 1rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.info-banner {
    background: #eff6ff; border: 1px solid #bfdbfe;
    border-radius: 8px; padding: 0.65rem 1rem; color: #1d4ed8;
    font-size: 0.875rem; margin-bottom: 1rem;
}
.badge-high   { background: #fee2e2; color: #b91c1c; }
.badge-medium { background: #fef3c7; color: #92400e; }
.badge-low    { background: #dcfce7; color: #166534; }
"""

# ── Shared component classes (used by ui.py across all pages) ────────────────
CSS_COMPONENTS = """
.intro-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #0284c7;
    border-radius: 10px; padding: 1.1rem 1.25rem; margin-bottom: 1.25rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.intro-title { font-size: 1.35rem; font-weight: 800; color: #0f172a; letter-spacing: -0.01em; line-height: 1.25; }
.intro-what { color: #475569; margin-top: 0.35rem; line-height: 1.55; font-size: 0.95rem; }
.intro-meta { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; margin-top: 0.8rem; }
.who-chip {
    background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 99px;
    padding: 2px 11px; font-size: 0.72rem; font-weight: 600;
}
.try-nudge { color: #64748b; font-size: 0.82rem; }
.section-label {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em;
    color: #64748b; margin: 0.9rem 0 0.35rem 0;
}
.callout { border-radius: 8px; padding: 0.65rem 1rem; font-size: 0.875rem; margin-bottom: 1rem; }
.callout-info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; }
.callout-warn { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; }
.tier-legend { display: flex; gap: 1.1rem; color: #64748b; font-size: 0.78rem; margin: 0.1rem 0 0.85rem; }
.tier-legend b { font-size: 0.9rem; }
.view-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.1rem 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05); height: 100%;
}
.view-card .vc-title { font-weight: 700; color: #0f172a; font-size: 1.02rem; }
.view-card .vc-who {
    color: #0284c7; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; margin-top: 0.15rem;
}
.view-card .vc-what { color: #475569; font-size: 0.88rem; margin-top: 0.5rem; line-height: 1.5; }
.step-row { display: flex; gap: 0.8rem; align-items: flex-start; margin-bottom: 0.7rem; }
.step-num {
    flex-shrink: 0; width: 1.65rem; height: 1.65rem; border-radius: 99px;
    background: #0284c7; color: #fff; font-weight: 700; font-size: 0.85rem;
    display: flex; align-items: center; justify-content: center;
}
.step-text { color: #334155; line-height: 1.5; }
.step-text b { color: #0f172a; }
"""

# Inject all CSS
st.markdown(
    f"<style>{CSS_SHARED}{CSS_THEME}{CSS_COMPONENTS}</style>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar navigation (top of sidebar, before all other controls)
# ---------------------------------------------------------------------------
ui.section_label("View", container=st.sidebar)
page = st.sidebar.radio(
    "View",
    ["Overview", "Pipeline", "Rep Tools", "Manager View", "Leader Dashboard"],
    captions=[
        "Start here",
        "Reps & RevOps · triage at-risk deals",
        "Reps · prep for a call",
        "Managers · run the pipeline review",
        "Leaders · spot pipeline-wide patterns",
    ],
    label_visibility="collapsed",
    key="nav_page",
)

# Header (brand bar — shown on every page)
st.markdown("""
<div style="padding:0 0 1.25rem 0">
  <div style="font-size:1.6rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;line-height:1.2">Deal Triage</div>
  <div style="color:#64748b;margin-top:0.3rem;font-size:0.9rem">Spot the deals about to slip — and see why.</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data loading (top-level — needed by all pages)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Data Source selector
# ---------------------------------------------------------------------------
ui.section_label("Data source", container=st.sidebar)
source = st.sidebar.radio(
    "source",
    ["🔗 HubSpot", "📁 Upload CSV", "🧪 Sample Data"],
    index=2,
    label_visibility="collapsed",
    key="data_source",
)
st.sidebar.caption("Demo data is loaded by default — no setup needed.")

if source == "🔗 HubSpot":
    if not hubspot_client.is_connected():
        st.sidebar.error("Set HUBSPOT_ACCESS_TOKEN in .env")
        st.warning(
            "**HubSpot not connected.** Add `HUBSPOT_ACCESS_TOKEN` to your `.env` file "
            "and restart the app. See `.env.example` for setup instructions.",
            icon="🔗",
        )
        st.stop()

    pipelines = hubspot_client.get_pipelines()
    if not pipelines:
        st.sidebar.error("No pipelines found")
        st.stop()

    pipeline_options = {p["label"]: p["id"] for p in pipelines}
    selected_label = st.sidebar.selectbox("Pipeline", list(pipeline_options.keys()))
    selected_id = pipeline_options[selected_label]

    hs_cache_key = f"hs_data_{selected_id}"
    hs_pulled_key = f"hs_pulled_{selected_id}"

    col_refresh, col_ts = st.sidebar.columns([1, 2])
    with col_refresh:
        do_refresh = st.button("↻", help="Refresh from HubSpot", key="hs_refresh")
    with col_ts:
        pulled_at = st.session_state.get(hs_pulled_key)
        if pulled_at:
            st.caption(_format_pull_timestamp(pulled_at))

    if do_refresh or hs_cache_key not in st.session_state:
        try:
            with st.spinner("Fetching from HubSpot…"):
                st.session_state[hs_cache_key] = hubspot_client.fetch_pipeline(selected_id)
                st.session_state[hs_pulled_key] = datetime.now()
        except hubspot_client.HubSpotError as e:
            st.error(f"HubSpot error: {e}")
            st.stop()

    df_raw = st.session_state[hs_cache_key]

    if page == "Pipeline":
        deal_count = len(df_raw)
        st.markdown(
            f'<div class="info-banner">🔗&nbsp; Live data from HubSpot · {deal_count} open deals</div>',
            unsafe_allow_html=True,
        )

elif source == "📁 Upload CSV":
    uploaded = st.file_uploader(
        "Upload opportunities CSV",
        type="csv",
        label_visibility="collapsed",
        help="Upload a HubSpot-style CSV export.",
    )
    if uploaded is not None:
        df_raw = pd.read_csv(uploaded)
    else:
        st.info("Upload a CSV file to get started, or switch to Sample Data.")
        st.stop()

else:  # Sample Data
    if not SAMPLE_CSV.exists():
        st.error(
            f"Sample data not found at `{SAMPLE_CSV}`. "
            "Run `python3 scripts/generate_sample_data.py` first."
        )
        st.stop()
    df_raw = pd.read_csv(SAMPLE_CSV)
    if page == "Pipeline":
        st.markdown(
            '<div class="info-banner">ℹ️&nbsp; Showing sample data — switch to HubSpot or upload your own CSV above.</div>',
            unsafe_allow_html=True,
        )

REQUIRED_COLS = {
    "deal_id", "account_name", "stage", "amount", "close_date",
    "days_in_stage", "last_activity_date", "owner", "industry", "employee_count",
}
missing_cols = REQUIRED_COLS - set(df_raw.columns)
if missing_cols:
    st.error(
        f"CSV is missing required columns: **{', '.join(sorted(missing_cols))}**  \n"
        "See the README for the full column spec."
    )
    st.stop()

scored = score_deals(df_raw)

# ---------------------------------------------------------------------------
# Sidebar — shared controls (hidden on the Overview landing page to keep it clean)
# ---------------------------------------------------------------------------
api_key = os.getenv("ANTHROPIC_API_KEY")

if page == "Overview":
    # Overview only reads the full scored set; skip the per-page controls.
    filtered = scored
    selected_owner = "All"
    ACTIVE_MODEL = "claude-haiku-4-5-20251001"
else:
    ui.section_label("Filter", container=st.sidebar)
    all_owners = sorted(scored["owner"].unique().tolist())
    selected_owner = st.sidebar.selectbox(
        "Account executive",
        ["All"] + all_owners,
        help="Show only deals owned by one rep.",
    )
    filtered = scored[scored["owner"] == selected_owner] if selected_owner != "All" else scored

    ui.section_label("AI model", container=st.sidebar)
    model_choice = st.sidebar.selectbox(
        "Claude model",
        ["Haiku (fast)", "Sonnet (deeper)"],
        label_visibility="collapsed",
        help="Haiku is faster and cheaper. Sonnet produces richer analysis.",
    )
    ACTIVE_MODEL = (
        "claude-haiku-4-5-20251001" if "Haiku" in model_choice else "claude-sonnet-4-6"
    )

st.sidebar.markdown(
    "<div style='padding-top:1rem;color:#334155;font-size:0.65rem;"
    "text-transform:uppercase;letter-spacing:0.07em'>Deal Triage · v2.0</div>",
    unsafe_allow_html=True,
)

if "explanations" not in st.session_state:
    st.session_state.explanations = {}

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------
if page == "Overview":
    from views.overview import render as render_overview
    render_overview(scored)
    st.stop()

if page == "Rep Tools":
    from views.rep_tools import render as render_rep
    render_rep(scored, st.session_state.explanations, ACTIVE_MODEL)
    st.stop()

if page == "Manager View":
    from views.manager_view import render as render_manager
    render_manager(scored, st.session_state.explanations, ACTIVE_MODEL)
    st.stop()

if page == "Leader Dashboard":
    from views.leader_dashboard import render as render_leader
    render_leader(scored, ACTIVE_MODEL)
    st.stop()

# ---------------------------------------------------------------------------
# Pipeline page (default)
# ---------------------------------------------------------------------------
tab_main, tab_method = st.tabs(["📊 At-Risk Deals", "📖 How scoring works"])

# ---------------------------------------------------------------------------
# Methodology tab
# ---------------------------------------------------------------------------
with tab_method:
    if METHODOLOGY_MD.exists():
        st.markdown(METHODOLOGY_MD.read_text(encoding="utf-8"))
    else:
        st.warning("METHODOLOGY.md not found in project root.")

# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------
with tab_main:

    # -----------------------------------------------------------------------
    # Page intro + brief "how the score works" (full explanation in the tab)
    # -----------------------------------------------------------------------
    ui.page_intro(
        title="At-Risk Deals",
        what="Every open deal ranked 0–100 by how likely it is to slip. Claude explains the "
             "riskiest 10 and drafts a follow-up you can send.",
        who="For reps & RevOps",
        try_this="click <b>Analyze with Claude</b> below the table.",
    )

    with st.expander("How the 0–100 score works"):
        st.markdown(
            "Each open deal earns risk points from three signals — higher means more likely to slip:\n\n"
            "- **Stuck in stage** (up to 40) — how long it's sat in its current stage vs. your team's typical time.\n"
            "- **Gone quiet** (up to 30) — days since the last logged activity.\n"
            "- **Close date slipping** (up to 30) — how close (or past) the expected close date is.\n\n"
            "See the **How scoring works** tab for the full methodology."
        )

    top10 = filtered.head(TOP_N).copy()

    _transcripts = {str(did): find_transcript(str(did)) for did in top10["deal_id"]}
    deals_with_transcripts = {did for did, t in _transcripts.items() if t}

    if len(top10) == 0 and selected_owner != "All":
        owner_total = len(scored[scored["owner"] == selected_owner])
        st.markdown(
            f'<div class="info-banner">ℹ️&nbsp; No at-risk deals for <strong>{html.escape(selected_owner)}</strong> — '
            f'{owner_total} open deal{"s" if owner_total != 1 else ""} all scoring below 40.</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Summary metrics
    # -----------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Open Deals",
        len(filtered),
        help="Deals still in play (Discovery, Demo, Proposal, Negotiation). Closed deals are excluded.",
    )
    c2.metric(
        "High-Risk Deals",
        len(filtered[filtered["risk_score"] >= 70]),
        help="Deals scoring 70 or higher out of 100 — the ones most likely to slip.",
    )
    c3.metric(
        "Open Pipeline",
        f"${int(filtered['amount'].sum()):,}",
        help="Total dollar value of all open deals shown here.",
    )

    st.divider()

    # -----------------------------------------------------------------------
    # Pipeline health chart
    # -----------------------------------------------------------------------
    _STAGE_ORDER = ["Discovery", "Demo", "Proposal", "Negotiation"]
    _TIER_COLORS = ["#dc2626", "#d97706", "#16a34a"]

    st.subheader("Open deals by stage")
    st.caption("Each bar is one stage; colors show how many deals fall in each risk tier.")
    ui.tier_legend()
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)

    chart_df = filtered.copy()
    chart_df["Risk Tier"] = chart_df["risk_score"].apply(risk_tier)
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
        .configure(background="transparent")
    )
    st.altair_chart(pipeline_chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    st.subheader("The 10 most at-risk deals")
    st.caption("Ranked highest-risk first. 🎙 marks deals with a call transcript Claude can quote from.")

    table_df = top10[["account_name", "stage", "amount", "close_date",
                       "days_in_stage", "risk_score", "owner"]].copy()
    table_df.insert(0, "#", range(1, len(table_df) + 1))
    table_df["account_name"] = [
        f"🎙 {name}" if str(did) in deals_with_transcripts else name
        for did, name in zip(top10["deal_id"].values, table_df["account_name"])
    ]
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

    # -----------------------------------------------------------------------
    # Claude analysis
    # -----------------------------------------------------------------------
    st.divider()

    if api_key:
        col_btn, col_note = st.columns([1, 4])
        with col_btn:
            analyze = st.button("Analyze with Claude", type="primary")
        with col_note:
            st.caption(
                f"Calls Claude ({model_choice.split(' ')[0]}) once per deal · results cached until re-analyzed · "
                "high-confidence deals with transcripts receive a full deal memo with verbatim quotes."
            )
        if analyze:
            st.session_state.explanations = {}
            rows = [r.to_dict() for _, r in top10.iterrows()]
            with st.status("Analyzing top deals with Claude…", expanded=True) as _status:
                # Warm the cached system prefix with the first deal sequentially,
                # then fan the rest out concurrently — the warm call populates the
                # prompt cache so the parallel calls can read it (and it's much
                # faster than the old one-at-a-time loop either way).
                def _run(r):
                    return r["deal_id"], cached_analyze(
                        r, _transcripts.get(str(r["deal_id"]), ""), ACTIVE_MODEL
                    )

                if rows:
                    _status.write(f"🔍 {rows[0]['account_name']}…")
                    did, result = _run(rows[0])
                    st.session_state.explanations[did] = result

                if len(rows) > 1:
                    _status.write(f"🔍 Analyzing {len(rows) - 1} more deals in parallel…")
                    with ThreadPoolExecutor(max_workers=5) as pool:
                        for did, result in pool.map(_run, rows[1:]):
                            st.session_state.explanations[did] = result
                _status.update(label="Analysis complete", state="complete", expanded=False)
    else:
        st.markdown(
            '<div class="info-banner">⚠️&nbsp; <strong>AI explanations disabled.</strong> '
            'Add <code>ANTHROPIC_API_KEY=your_key</code> to <code>.env</code> and restart to enable Claude-powered risk analysis.</div>',
            unsafe_allow_html=True,
        )

    # Export enriched CSV (shown after Claude has run)
    if st.session_state.get("explanations"):
        export_rows = []
        for _, row in top10.iterrows():
            analysis = st.session_state.explanations.get(row["deal_id"]) or {}
            confidence = analysis.get("confidence", "")
            summary = analysis.get("executive_summary") or analysis.get("brief") or ""
            rec = analysis.get("recommended_actions") or []
            action = rec[0].get("action", "") if rec and isinstance(rec[0], dict) else analysis.get("next_action", "")
            export_rows.append({
                "deal_id": row["deal_id"],
                "account_name": row["account_name"],
                "stage": row["stage"],
                "amount": int(row["amount"]),
                "close_date": row["close_date"],
                "days_in_stage": int(row["days_in_stage"]),
                "risk_score": int(row["risk_score"]),
                "owner": row["owner"],
                "confidence": confidence,
                "analysis_summary": summary,
                "recommended_action": action,
            })
        st.download_button(
            "⬇ Download ranked deals + analysis",
            pd.DataFrame(export_rows).to_csv(index=False),
            "deal_triage_export.csv",
            "text/csv",
            help="Downloads the top 10 at-risk deals with risk scores and Claude analysis as a CSV.",
        )

    # -----------------------------------------------------------------------
    # Analysis feedback summary (closes the 👍/👎 loop)
    # -----------------------------------------------------------------------
    _fb = feedback_store.summarize_feedback()
    if _fb["total"]:
        with st.expander(
            f"📊 Analysis feedback · {_fb['total']} rating{'s' if _fb['total'] != 1 else ''}"
            + (f" · {_fb['helpful_rate']:.0f}% helpful" if _fb['helpful_rate'] is not None else "")
        ):
            cols = st.columns(3)
            for col, tier in zip(cols, feedback_store.TIERS):
                stats = _fb["by_tier"][tier]
                rate = stats["helpful_rate"]
                value = f"{rate:.0f}%" if rate is not None else "—"
                col.metric(
                    f"{tier} confidence",
                    value,
                    help=f"{stats['positive']}/{stats['total']} rated helpful.",
                )
                # Flag tiers that look like they need prompt tuning.
                if rate is not None and stats["total"] >= MIN_BENCHMARK_SAMPLE and rate < 50:
                    col.markdown(
                        "<span style='color:#b91c1c;font-size:0.75rem;font-weight:600'>"
                        "⚠ Needs prompt tuning</span>",
                        unsafe_allow_html=True,
                    )
            st.caption(
                "Helpful rate from 👍/👎 ratings, stored locally. Tiers below 50% with a "
                f"meaningful sample (≥{MIN_BENCHMARK_SAMPLE}) are flagged for prompt tuning."
            )

    # -----------------------------------------------------------------------
    # Per-deal expanders
    # -----------------------------------------------------------------------
    st.subheader("Deal Detail")

    CONFIDENCE_BADGE = {
        "High":   '<span class="badge-high">High</span>',
        "Medium": '<span class="badge-medium">Medium</span>',
        "Low":    '<span class="badge-low">Low</span>',
    }

    for rank, (_, row) in enumerate(top10.iterrows(), start=1):
        _has_tx = str(row["deal_id"]) in deals_with_transcripts
        label = f"#{rank} — {'🎙 ' if _has_tx else ''}{row['account_name']}  ·  {row['stage']}  ·  Risk score: {row['risk_score']}/100"
        with st.expander(label, expanded=(rank == 1)):

            # Inject risk-tier border via :has() selector scoped to this deal's unique ID
            _tier_key = risk_tier(row["risk_score"]).lower()
            _border_css = _TIER_BORDER[_tier_key]
            _safe_id = re.sub(r'[^A-Za-z0-9_-]', '', str(row["deal_id"]))
            st.markdown(
                f'<style>[data-testid="stExpander"]:has([data-deal-id="{_safe_id}"]) '
                f'{{ {_border_css} }}</style>'
                f'<span data-deal-id="{_safe_id}" style="display:none"></span>',
                unsafe_allow_html=True,
            )

            # Zone 1: CRM signals
            m1, m2, m3 = st.columns(3)
            m1.metric(
                "Amount",
                f"${int(row['amount']):,}",
                help="Deal value in USD from CRM.",
            )
            m2.metric(
                "Days in Stage",
                int(row["days_in_stage"]),
                help="Days since this deal last moved to a new stage. Scored against your team's historical median — longer means higher slip risk.",
            )
            m3.metric(
                "Close Date",
                str(row["close_date"]),
                help="Target close date from CRM. Past-due deals score maximum close date pressure (30/30 pts).",
            )
            try:
                _close_d = date.fromisoformat(str(row["close_date"]))
                _days_until = (_close_d - TODAY).days
                if _days_until < 0:
                    m3.markdown(
                        f"<span style='color:#dc2626;font-size:0.8rem;font-weight:500'>"
                        f"Past due · {abs(_days_until)}d overdue</span>",
                        unsafe_allow_html=True,
                    )
                elif _days_until < 14:
                    m3.markdown(
                        f"<span style='color:#d97706;font-size:0.8rem;font-weight:500'>"
                        f"{_days_until}d remaining</span>",
                        unsafe_allow_html=True,
                    )
            except (ValueError, TypeError):
                pass

            stage_median = int(row.get("_stage_median") or STAGE_THRESHOLDS.get(row["stage"], 14))
            days_in      = int(row["days_in_stage"])
            multiple     = f"{days_in / stage_median:.1f}×" if stage_median > 0 else ""

            # Plain-language "why" derived from which signals are elevated.
            _why = []
            if int(row["_stage_pts"]) >= 20:
                _why.append(f"stuck {multiple} the typical {stage_median}-day time in {row['stage']}")
            if int(row["_act_pts"]) >= 22:
                _why.append("no recent activity")
            elif int(row["_act_pts"]) >= 14:
                _why.append("activity slowing down")
            _cp = int(row["_close_pts"])
            if _cp >= 30:
                _why.append("past its close date")
            elif _cp >= 25:
                _why.append("close date within two weeks")
            elif _cp >= 15:
                _why.append("close date approaching")
            st.markdown(
                f"**Why it's risky:** {'; '.join(_why) if _why else 'only mild signals — worth a glance'}."
            )
            st.caption(
                f"Score breakdown — Stuck in stage {int(row['_stage_pts'])}/40  ·  "
                f"Gone quiet {int(row['_act_pts'])}/30  ·  "
                f"Close date {int(row['_close_pts'])}/30"
            )

            next_step = row.get("next_step") or "—"
            st.write(f"**Owner:** {row['owner']}  |  **Next Step:** {next_step}")
            st.write(f"**Industry:** {row['industry']}  |  **Employees:** {int(row['employee_count']):,}")

            # Zone 2: Claude analysis
            analysis = st.session_state.explanations.get(row["deal_id"])
            if analysis:
                st.markdown("---")
                confidence = analysis.get("confidence", "")
                badge_html = CONFIDENCE_BADGE.get(confidence, "")
                st.markdown(
                    f"<div style='margin-bottom:0.2rem'>"
                    f"<strong>Claude's take</strong>&nbsp;&nbsp;{badge_html} confidence"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    "Confidence reflects how much evidence Claude had — strong signals plus a "
                    "call transcript earn a fuller write-up."
                )

                # Verbatim transcript quotes as evidence
                quotes = [q for q in (analysis.get("quotes") or []) if q]
                _quote_bg = "#fef2f2"
                _quote_text = "#374151"
                _quote_attr = "#9ca3af"
                for quote in quotes:
                    st.markdown(
                        f"""<div style="border-left:3px solid #dc2626;padding:8px 14px;
                        background:{_quote_bg};margin:6px 0 10px 0;border-radius:0 4px 4px 0">
                        <span style="font-style:italic;color:{_quote_text}">"{html.escape(quote)}"</span><br>
                        <span style="font-size:0.72rem;color:{_quote_attr};margin-top:3px;display:block">— Call transcript</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                # Tiered content
                if confidence == "High":
                    exec_summary = analysis.get("executive_summary", "")
                    if exec_summary:
                        st.markdown(f"**Summary:** {exec_summary}")

                    risk_signals = analysis.get("risk_signals") or []
                    if risk_signals:
                        st.markdown("**Risk signals:**")
                        for sig in risk_signals:
                            if isinstance(sig, dict):
                                st.markdown(f"- **{sig.get('signal', '')}** — {sig.get('evidence', '')}")
                            else:
                                st.markdown(f"- {sig}")

                    bpa = analysis.get("buying_process_analysis", "")
                    if bpa:
                        _bpa_bg     = "#f8fafc"
                        _bpa_border = "#e2e8f0"
                        _bpa_label  = "#64748b"
                        _bpa_text   = "#1e293b"
                        st.markdown(
                            f"""<div style="background:{_bpa_bg};border:1px solid {_bpa_border};
                            border-radius:8px;padding:12px 16px;margin:10px 0">
                            <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;
                            color:{_bpa_label};font-weight:600;margin-bottom:6px">Buying Process Analysis</div>
                            <div style="color:{_bpa_text};line-height:1.6">{html.escape(bpa)}</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )

                    rec_actions = analysis.get("recommended_actions") or []
                    if rec_actions:
                        st.markdown("**Recommended actions:**")
                        for i, act in enumerate(rec_actions, start=1):
                            if isinstance(act, dict):
                                st.markdown(f"{i}. **{act.get('action', '')}** — *{act.get('rationale', '')}*")
                            else:
                                st.markdown(f"{i}. {act}")

                else:  # Low or Medium
                    brief = analysis.get("brief", "")
                    if brief:
                        st.markdown(brief)
                    risk_signals = analysis.get("risk_signals") or []
                    if risk_signals:
                        st.markdown("**Risk signals:**")
                        for sig in risk_signals:
                            st.markdown(f"- {sig}")
                    next_action = analysis.get("next_action", "")
                    if next_action:
                        st.markdown(f"**Suggested action this week:** {next_action}")

                # Thumbs feedback
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                feedback_key = f"feedback_{row['deal_id']}"
                if st.session_state.get(feedback_key):
                    st.caption("✓ Feedback recorded")
                else:
                    col_up, col_down, _ = st.columns([1, 1, 8])
                    if col_up.button("👍 Helpful", key=f"up_{row['deal_id']}"):
                        feedback_store.record_feedback(row.to_dict(), confidence, "positive")
                        st.session_state[feedback_key] = True
                        st.rerun()
                    if col_down.button("👎 Off-target", key=f"down_{row['deal_id']}"):
                        feedback_store.record_feedback(row.to_dict(), confidence, "negative")
                        st.session_state[feedback_key] = True
                        st.rerun()

                # Follow-up email draft
                if api_key:
                    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                    email_key = f"email_{row['deal_id']}"
                    if st.button("✉ Draft follow-up email", key=f"email_btn_{row['deal_id']}"):
                        with st.spinner("Drafting email…"):
                            email_draft = claude_client.generate_followup_email(
                                row.to_dict(), analysis, ACTIVE_MODEL
                            )
                            st.session_state[email_key] = email_draft
                    if st.session_state.get(email_key):
                        st.text_area(
                            "Follow-up email draft",
                            st.session_state[email_key],
                            height=180,
                            key=f"email_ta_{row['deal_id']}",
                        )

            elif st.session_state.explanations:
                st.caption("Explanation unavailable for this deal.")
