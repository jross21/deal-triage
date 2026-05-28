import html
import os

import altair as alt
import pandas as pd
import streamlit as st

import claude_client
from analytics import (
    compute_at_risk_pipeline,
    compute_avg_days_stagnant,
    compute_high_risk_rate,
    compute_proposal_health_rate,
    compute_signal_counts,
)

OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}


def render(df: pd.DataFrame, model: str) -> None:
    st.header("Leader View — Win/Loss Signal Intelligence")
    st.caption("Pattern analysis across the full pipeline. No per-deal calls required.")

    open_df = df[df["stage"].isin(OPEN_STAGES)].copy()
    if open_df.empty:
        st.info("No open deals found in the loaded data.")
        return

    # Snapshot for trend indicators: store on first visit, compare on subsequent
    snapshot_key = "leader_snapshot"
    current = {
        "high_risk_rate":       compute_high_risk_rate(df),
        "avg_days_stagnant":    compute_avg_days_stagnant(df),
        "at_risk_pipeline":     compute_at_risk_pipeline(df),
        "proposal_health_rate": compute_proposal_health_rate(df),
    }
    if snapshot_key not in st.session_state:
        st.session_state[snapshot_key] = current

    # ── KPI cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("High-Risk Rate", f"{current['high_risk_rate']}%",
              help="% of open deals with risk score ≥70.")
    c2.metric("Avg Days Stagnant", f"{current['avg_days_stagnant']}d",
              help="Mean days_in_stage across all open deals.")
    c3.metric("At-Risk Pipeline", f"${int(current['at_risk_pipeline']):,}",
              help="Total dollar value of deals scoring ≥70.")
    c4.metric("Proposal Health %", f"{current['proposal_health_rate']}%",
              help="% of Proposal-stage deals with risk score <40 (low-risk proxy).")

    st.divider()

    # ── Two-column charts ───────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Top Risk Signals Across Pipeline**")
        signal_counts = compute_signal_counts(df)
        signal_df = pd.DataFrame([
            {"Signal": k, "Deals": v} for k, v in signal_counts.items()
        ]).sort_values("Deals", ascending=False)

        bar_colors = ["#ef4444", "#ef4444", "#f59e0b", "#f59e0b", "#94a3b8"]
        signal_df["color"] = bar_colors[: len(signal_df)]

        chart = (
            alt.Chart(signal_df)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                y=alt.Y("Signal:N", sort="-x", title=None),
                x=alt.X("Deals:Q", title="Deal count"),
                color=alt.Color("color:N", scale=None, legend=None),
                tooltip=["Signal:N", "Deals:Q"],
            )
            .properties(height=200)
            .configure(background="transparent")
        )
        st.altair_chart(chart, use_container_width=True)

    with col_right:
        st.markdown("**Rep Portfolio Risk Profiles**")
        rep_stats = (
            open_df.groupby("owner")
            .agg(avg_risk=("risk_score", "mean"), deal_count=("deal_id", "count"))
            .reset_index()
            .sort_values("avg_risk", ascending=False)
            .rename(columns={"owner": "Rep", "avg_risk": "Avg Risk"})
        )
        rep_stats["Avg Risk"] = rep_stats["Avg Risk"].round(1)

        def _bar_color(score):
            if score >= 70:
                return "#ef4444"
            if score >= 40:
                return "#f59e0b"
            return "#22c55e"

        rep_stats["color"] = rep_stats["Avg Risk"].apply(_bar_color)

        rep_chart = (
            alt.Chart(rep_stats)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                y=alt.Y("Rep:N", sort="-x", title=None),
                x=alt.X("Avg Risk:Q", scale=alt.Scale(domain=[0, 100]), title="Avg risk score"),
                color=alt.Color("color:N", scale=None, legend=None),
                tooltip=["Rep:N", "Avg Risk:Q", "deal_count:Q"],
            )
            .properties(height=200)
            .configure(background="transparent")
        )
        st.altair_chart(rep_chart, use_container_width=True)

    st.divider()

    # ── Claude Strategic Insight ────────────────────────────────────────────
    insight_key = "strategic_insight"

    col_btn, _ = st.columns([1, 5])
    with col_btn:
        refresh = st.button("Refresh Insight", type="primary")

    if refresh or insight_key not in st.session_state:
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.warning("Add ANTHROPIC_API_KEY to .env to enable the Claude strategic insight.")
        else:
            with st.spinner("Generating strategic insight…"):
                rep_profiles = [
                    {
                        "rep_name": row["Rep"],
                        "avg_risk": float(row["Avg Risk"]),
                        "deal_count": int(row["deal_count"]),
                    }
                    for _, row in rep_stats.iterrows()
                ]
                insight = claude_client.generate_strategic_insight(signal_counts, rep_profiles, model)
                if insight:
                    st.session_state[insight_key] = insight

    if insight_key in st.session_state:
        escaped = html.escape(st.session_state[insight_key])
        st.markdown(
            f"""<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:1.1rem">
            <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#15803d;margin-bottom:0.5rem">Strategic Insight — Claude</div>
            <div style="color:#1e293b;line-height:1.7">{escaped}</div>
            </div>""",
            unsafe_allow_html=True,
        )
