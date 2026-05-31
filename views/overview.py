"""Overview — the default landing page.

Explains, in plain language, what Deal Triage does, how the score works, and
what each of the four views is for. Buttons switch the sidebar nav via the
shared `nav_page` session-state key (set through on_click callbacks, the
Streamlit-sanctioned way to change another widget's value).
"""

import pandas as pd
import streamlit as st

from constants import HIGH_RISK_THRESHOLD


def _go(view: str) -> None:
    st.session_state["nav_page"] = view


# (view, icon, title, who, what)
_VIEWS = [
    ("Pipeline", "📊", "At-Risk Deals", "Reps & RevOps",
     "Every open deal ranked 0–100 by slip-risk, with Claude explaining the top 10 and a one-click follow-up email."),
    ("Rep Tools", "🎯", "Pre-Call Brief", "Account executives",
     "Pick a deal and get a tailored brief — context, open objections, an agenda, and three questions to ask."),
    ("Manager View", "🗂", "Pipeline Review", "Sales managers",
     "A ready-to-run weekly review agenda: a pipeline pulse plus per-rep deals to inspect and questions to ask."),
    ("Leader Dashboard", "📈", "Signal Intelligence", "Sales leaders",
     "Pattern analysis across the whole pipeline — top risk signals, per-rep risk profiles, and a strategic takeaway."),
]


def render(scored: pd.DataFrame) -> None:
    open_count = len(scored)
    high_risk = int((scored["risk_score"] >= HIGH_RISK_THRESHOLD).sum()) if open_count else 0
    pipeline_value = int(scored["amount"].sum()) if open_count else 0

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown(
        f"""<div class="intro-card" style="border-left-color:#0284c7">
          <div class="intro-title" style="font-size:1.6rem">Spot the deals about to slip — before they do.</div>
          <div class="intro-what">
            Deal Triage scores every open deal on how likely it is to stall, then uses Claude to
            explain <em>why</em> the riskiest ones are slipping and what to do next. It's a portfolio
            demo of a real RevOps workflow — explore it with the built-in sample pipeline, no setup required.
          </div>
          <div class="intro-meta">
            <span class="who-chip">{open_count} open deals</span>
            <span class="who-chip" style="background:#fee2e2;color:#b91c1c;border-color:#fca5a5">{high_risk} high-risk</span>
            <span class="who-chip" style="background:#f0fdf4;color:#15803d;border-color:#86efac">${pipeline_value:,} in play</span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── How it works ──────────────────────────────────────────────────────────
    st.subheader("How it works")
    st.markdown(
        """<div class="step-row">
          <div class="step-num">1</div>
          <div class="step-text"><b>A simple score ranks every deal (no AI, instant, free).</b>
          Each open deal gets 0–100 points from three plain signals: it's been
          <b>stuck in its stage too long</b>, it's <b>gone quiet</b> (no recent activity), or its
          <b>close date is slipping past</b>. Higher score = more likely to slip.</div>
        </div>
        <div class="step-row">
          <div class="step-num">2</div>
          <div class="step-text"><b>Claude explains the riskiest deals.</b>
          For the top at-risk deals, Claude reads the CRM fields and any call transcript, then writes
          why the deal is at risk and a concrete next step. (This part needs an API key — the scoring
          works without one.)</div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Four views ────────────────────────────────────────────────────────────
    st.subheader("Four views, one for each role")
    st.caption("Each view reframes the same scored pipeline for a different person on the team.")

    rows = [_VIEWS[:2], _VIEWS[2:]]
    for row in rows:
        cols = st.columns(2)
        for col, (view, icon, title, who, what) in zip(cols, row):
            with col:
                st.markdown(
                    f"""<div class="view-card">
                      <div class="vc-title">{icon}&nbsp; {title}</div>
                      <div class="vc-who">For {who}</div>
                      <div class="vc-what">{what}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.button(f"Open {view} →", key=f"go_{view}", on_click=_go, args=(view,),
                          use_container_width=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    st.button("Start with the Pipeline →", type="primary", on_click=_go, args=("Pipeline",))
    st.caption("Or pick any view from the sidebar on the left.")
