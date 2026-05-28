import html
import os

import pandas as pd
import streamlit as st

import claude_client

OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}
HIGH_RISK_THRESHOLD = 60


def render(df: pd.DataFrame, explanations: dict, model: str) -> None:
    st.header("Manager View — Pipeline Review")
    st.caption("Generate a structured agenda for your weekly pipeline call.")

    open_df = df[df["stage"].isin(OPEN_STAGES)].copy()
    if open_df.empty:
        st.info("No open deals found in the loaded data.")
        return

    agenda_key = "manager_agenda"

    col_btn, col_note = st.columns([1, 5])
    with col_btn:
        generate = st.button("Generate Agenda", type="primary")
    with col_note:
        high_risk_count = len(open_df[open_df["risk_score"] >= HIGH_RISK_THRESHOLD])
        total_pipeline = int(open_df["amount"].sum())
        st.caption(f"{len(open_df)} open deals · {high_risk_count} high-risk · ${total_pipeline:,} pipeline")

    if generate:
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("Add ANTHROPIC_API_KEY to .env and restart.")
            return
        with st.spinner("Generating pipeline review agenda…"):
            rep_summaries = _build_rep_summaries(open_df)
            agenda = claude_client.generate_pipeline_review(rep_summaries, model)
            if agenda:
                st.session_state[agenda_key] = agenda
            else:
                st.error("Agenda generation failed. Check API key and try again.")

    if agenda_key in st.session_state:
        _render_agenda(st.session_state[agenda_key], open_df)


def _build_rep_summaries(df: pd.DataFrame) -> list:
    """Build rep-grouped deal summaries for high-risk deals only."""
    high_risk = df[df["risk_score"] >= HIGH_RISK_THRESHOLD].copy()
    summaries = []
    for rep_name, group in high_risk.groupby("owner"):
        deals = []
        for _, row in group.sort_values("risk_score", ascending=False).iterrows():
            signal = _primary_signal(row)
            deals.append({
                "account_name": row["account_name"],
                "stage": row["stage"],
                "risk_score": int(row["risk_score"]),
                "signal": signal,
            })
        summaries.append({"rep_name": rep_name, "deals": deals})
    summaries.sort(key=lambda x: max(d["risk_score"] for d in x["deals"]), reverse=True)
    return summaries


def _primary_signal(row) -> str:
    """Return a one-line description of the top risk signal for a deal."""
    days_in = int(row.get("days_in_stage", 0))
    median = int(row.get("_stage_median") or 14)
    stage_pts = int(row.get("_stage_pts", 0))
    act_pts = int(row.get("_act_pts", 0))
    close_pts = int(row.get("_close_pts", 0))

    if close_pts == 30:
        return "close date past due"
    if stage_pts >= 30:
        multiple = f"{days_in / median:.1f}×" if median > 0 else ""
        return f"{days_in} days in {row['stage']} ({multiple} median)"
    if act_pts >= 22:
        return f"no activity in {days_in} days"
    return f"score {int(row['risk_score'])}/100"


def _render_agenda(agenda: dict, open_df: pd.DataFrame) -> None:
    # Pipeline Pulse banner — blue
    pulse = html.escape(agenda.get("pulse", ""))
    st.markdown(
        f"""<div style="background:#f0f7ff;border:1px solid #93c5fd;border-radius:10px;padding:1.1rem;margin:1rem 0">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#1d4ed8;margin-bottom:0.4rem">Pipeline Pulse</div>
        <div style="color:#1e293b;line-height:1.6">{pulse}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Build rep questions lookup from Claude response
    questions_by_rep = {r["rep_name"]: r.get("questions", []) for r in (agenda.get("reps") or [])}

    # Per-rep sections: all reps, sorted by avg risk score desc
    rep_stats = (
        open_df.groupby("owner")
        .agg(
            deal_count=("deal_id", "count"),
            total_pipeline=("amount", "sum"),
            avg_risk=("risk_score", "mean"),
            max_risk=("risk_score", "max"),
        )
        .reset_index()
        .sort_values("avg_risk", ascending=False)
    )

    for _, rep_row in rep_stats.iterrows():
        rep_name = rep_row["owner"]
        rep_deals = open_df[open_df["owner"] == rep_name].sort_values("risk_score", ascending=False)
        high_risk_deals = rep_deals[rep_deals["risk_score"] >= HIGH_RISK_THRESHOLD]
        rep_questions = questions_by_rep.get(rep_name, [])

        has_risk = len(high_risk_deals) > 0

        # Risk badge
        if len(high_risk_deals) >= 2:
            badge = f'<span style="background:#fee2e2;color:#b91c1c;font-size:0.7rem;font-weight:700;padding:0.2rem 0.6rem;border-radius:99px">{len(high_risk_deals)} High Risk</span>'
        elif has_risk:
            badge = '<span style="background:#fef3c7;color:#b45309;font-size:0.7rem;font-weight:700;padding:0.2rem 0.6rem;border-radius:99px">1 High Risk</span>'
        else:
            badge = '<span style="background:#dcfce7;color:#15803d;font-size:0.7rem;font-weight:700;padding:0.2rem 0.6rem;border-radius:99px">All Green</span>'

        pipeline_val = f"${int(rep_row['total_pipeline']):,}"

        st.markdown(
            f"""<div style="border:1px solid #e2e8f0;border-radius:10px;margin-bottom:1rem;overflow:hidden">
            <div style="background:#f8fafc;padding:0.75rem 1.1rem;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center">
              <div style="font-weight:700;color:#1e293b">{html.escape(rep_name)}</div>
              <div style="display:flex;gap:0.75rem;align-items:center">{badge}<span style="color:#64748b;font-size:0.82rem">{pipeline_val} open</span></div>
            </div>""",
            unsafe_allow_html=True,
        )

        if not has_risk:
            st.markdown(
                '<div style="padding:0.85rem 1.1rem;color:#64748b;font-style:italic">No high-risk deals. Keep it brief — acknowledge momentum and move on.</div></div>',
                unsafe_allow_html=True,
            )
            continue

        # Deals to inspect
        deals_html = ""
        for _, deal in high_risk_deals.iterrows():
            signal = _primary_signal(deal)
            score_color = "#ef4444" if deal["risk_score"] >= 70 else "#f59e0b"
            deals_html += (
                f'<div style="display:flex;justify-content:space-between;color:#1e293b;margin-bottom:0.25rem">'
                f'<span>{html.escape(deal["account_name"])} <span style="color:#94a3b8">· {html.escape(deal["stage"])} · {html.escape(signal)}</span></span>'
                f'<span style="color:{score_color};font-weight:600">Score {int(deal["risk_score"])}</span>'
                f'</div>'
            )

        # Suggested questions — purple
        q_html = ""
        if rep_questions:
            items = "".join(f'<li style="margin-bottom:0.3rem;color:#1e293b">{html.escape(q)}</li>' for q in rep_questions)
            q_html = f"""<div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:8px;padding:0.85rem;margin-top:0.75rem">
              <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#7e22ce;margin-bottom:0.4rem">Suggested Questions</div>
              <ul style="margin:0;padding-left:1.2rem;line-height:1.9">{items}</ul>
            </div>"""

        st.markdown(
            f"""<div style="padding:1rem 1.1rem">
              <div style="font-size:0.75rem;font-weight:600;color:#64748b;margin-bottom:0.4rem">DEALS TO INSPECT</div>
              {deals_html}
              {q_html}
            </div></div>""",
            unsafe_allow_html=True,
        )
