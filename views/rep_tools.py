import html
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import claude_client

OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}
TRANSCRIPT_DIR = Path("data/sample/transcripts")


def render(df: pd.DataFrame, explanations: dict, model: str) -> None:
    st.header("Rep Tools — Pre-Call Brief")
    st.caption("Select a deal and generate a tailored brief before your next call.")

    open_deals = df[df["stage"].isin(OPEN_STAGES)].sort_values("risk_score", ascending=False).reset_index(drop=True)
    if open_deals.empty:
        st.info("No open deals found in the loaded data.")
        return

    options = [
        f"{row['account_name']} — {row['stage']} · ${int(row['amount']):,} · closes {row['close_date']}"
        for _, row in open_deals.iterrows()
    ]
    deal_index = st.selectbox(
        "Select a deal",
        range(len(options)),
        format_func=lambda i: options[i],
        label_visibility="collapsed",
    )
    selected_row = open_deals.iloc[deal_index]
    brief_key = f"brief_{selected_row['deal_id']}"

    col_btn, col_note = st.columns([1, 5])
    with col_btn:
        generate = st.button("Generate Brief", type="primary")
    with col_note:
        has_tx = bool(_load_transcript(str(selected_row["deal_id"])))
        st.caption("🎙 Transcript available — brief will include verbatim evidence." if has_tx else "No transcript — brief based on CRM signals only.")

    if generate:
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("Add ANTHROPIC_API_KEY to .env and restart.")
            return
        with st.spinner("Generating pre-call brief…"):
            transcript = _load_transcript(str(selected_row["deal_id"]))
            existing = explanations.get(selected_row["deal_id"], {})
            brief = claude_client.generate_pre_call_brief(selected_row, transcript, model, existing)
            if brief:
                st.session_state[brief_key] = brief
            else:
                st.error("Brief generation failed. Check API key and try again.")

    if brief_key in st.session_state:
        _render_brief(st.session_state[brief_key])


def _load_transcript(deal_id: str) -> str:
    matches = list(TRANSCRIPT_DIR.glob(f"{deal_id}_*.txt"))
    if not matches:
        return ""
    return matches[0].read_text(encoding="utf-8")[:2500]


def _render_brief(brief: dict) -> None:
    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

    # Context from Most Recent Call — neutral slate
    context = html.escape(brief.get("context", "No context available."))
    st.markdown(
        f"""<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;padding:1.25rem;margin-bottom:1rem">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#94a3b8;margin-bottom:0.5rem">Context from Most Recent Call</div>
        <div style="color:#475569;line-height:1.6">{context}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Open Objections — amber
    objections = brief.get("objections") or []
    obj_count = len(objections)
    obj_label = f"Open Objections ({obj_count})" if obj_count else "Open Objections"
    obj_body = _render_objections(objections)
    st.markdown(
        f"""<div style="background:#fef9f0;border:1px solid #fde68a;border-radius:10px;padding:1.25rem;margin-bottom:1rem">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#b45309;margin-bottom:0.5rem">{obj_label}</div>
        {obj_body}
        </div>""",
        unsafe_allow_html=True,
    )

    # Recommended Agenda — green
    agenda = brief.get("agenda") or []
    agenda_html = "".join(f"<li style='margin-bottom:0.4rem;color:#1e293b'>{html.escape(item)}</li>" for item in agenda)
    st.markdown(
        f"""<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:1.25rem;margin-bottom:1rem">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#15803d;margin-bottom:0.5rem">Recommended Agenda</div>
        <ol style="margin:0;padding-left:1.25rem;line-height:1.9">{agenda_html}</ol>
        </div>""",
        unsafe_allow_html=True,
    )

    # 3 Questions to Ask — purple
    questions = brief.get("questions") or []
    q_html = "".join(f'<li style="margin-bottom:0.4rem;color:#1e293b">"{html.escape(q)}"</li>' for q in questions)
    st.markdown(
        f"""<div style="background:#faf5ff;border:1px solid #d8b4fe;border-radius:10px;padding:1.25rem">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#7e22ce;margin-bottom:0.5rem">3 Questions to Ask</div>
        <ol style="margin:0;padding-left:1.25rem;line-height:1.9">{q_html}</ol>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_objections(objections: list) -> str:
    if not objections:
        return '<div style="color:#64748b;font-style:italic">No objections identified in available data.</div>'
    items = []
    for obj in objections:
        label = html.escape(obj.get("label", ""))
        quote = obj.get("quote", "")
        quote_html = f' — <em>"{html.escape(quote)}"</em>' if quote else ""
        status = obj.get("status", "")
        dot_color = "#ef4444" if status == "Unresolved" else "#22c55e"
        items.append(
            f'<div style="display:flex;align-items:flex-start;gap:0.5rem;margin-bottom:0.4rem">'
            f'<span style="color:{dot_color};font-weight:700;flex-shrink:0;margin-top:2px">●</span>'
            f'<span style="color:#1e293b"><strong>{label}</strong>{quote_html} '
            f'<em style="color:#64748b">{html.escape(status)}</em></span>'
            f'</div>'
        )
    return "".join(items)
