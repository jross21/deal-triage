"""Shared UI chrome for consistent, plain-language headers and labels.

Used by app.py and every view in views/ so the app reads the same way on every
page. The CSS classes referenced here (.intro-card, .who-chip, .section-label,
.callout, .tier-legend, .view-card, .step-row) are defined once in app.py's
injected stylesheet, so these helpers only emit lightweight markup.

`title` and `who` are HTML-escaped; `what` and `try_this` are authored in-code
(trusted) and may contain inline markup like <b>…</b>.
"""

import html

import streamlit as st

from constants import HIGH_RISK_THRESHOLD, MEDIUM_RISK_THRESHOLD

RISK_COLORS = {"High": "#dc2626", "Medium": "#d97706", "Low": "#16a34a"}


def page_intro(title: str, what: str, who: str, try_this: str | None = None, container=st) -> None:
    """Standard per-page header: title, one-line 'what', a 'who it's for' chip,
    and an optional 'Try this →' nudge."""
    try_html = (
        f"<span class='try-nudge'>Try this&nbsp;→&nbsp;{try_this}</span>" if try_this else ""
    )
    container.markdown(
        f"""<div class="intro-card">
          <div class="intro-title">{html.escape(title)}</div>
          <div class="intro-what">{what}</div>
          <div class="intro-meta">
            <span class="who-chip">{html.escape(who)}</span>
            {try_html}
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


def section_label(text: str, container=st) -> None:
    """Small uppercase slate label for grouping (sidebar sections, etc.)."""
    container.markdown(
        f"<div class='section-label'>{html.escape(text)}</div>",
        unsafe_allow_html=True,
    )


def callout(text: str, kind: str = "info", container=st) -> None:
    """Inline info/warn banner. `text` may contain inline markup."""
    container.markdown(
        f"<div class='callout callout-{kind}'>{text}</div>",
        unsafe_allow_html=True,
    )


def tier_legend(container=st) -> None:
    """Tiny risk-tier key, kept in sync with the scoring thresholds."""
    container.markdown(
        "<div class='tier-legend'>"
        f"<span><b style='color:{RISK_COLORS['High']}'>●</b> High&nbsp;≥&nbsp;{HIGH_RISK_THRESHOLD}</span>"
        f"<span><b style='color:{RISK_COLORS['Medium']}'>●</b> Medium&nbsp;≥&nbsp;{MEDIUM_RISK_THRESHOLD}</span>"
        f"<span><b style='color:{RISK_COLORS['Low']}'>●</b> Low&nbsp;&lt;&nbsp;{MEDIUM_RISK_THRESHOLD}</span>"
        "</div>",
        unsafe_allow_html=True,
    )
