# Deal Triage v2 — Three-View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three role-specific views to Deal Triage — a Rep Pre-Call Brief, a Manager Pipeline Review, and a Leader Win/Loss Signal Dashboard — routed via sidebar nav.

**Architecture:** `app.py` becomes a thin router. Data loading and scoring move to the top level (before routing). Three view modules in `views/` (NOT `pages/` — Streamlit auto-discovers `pages/` as native multi-page routes, which conflicts with sidebar nav) each export a `render()` function. `claude_client.py` gets three new functions. An `analytics.py` module holds pure KPI-computation functions for the Leader Dashboard.

**Tech Stack:** Python 3.11+, Streamlit, Anthropic SDK (`anthropic`), Altair, Pandas, pytest, unittest.mock

---

## File Map

**Create:**
- `views/__init__.py` — empty package marker
- `views/rep_tools.py` — Rep Tools page: deal selector, brief rendering
- `views/manager_view.py` — Manager View page: agenda generation, per-rep sections
- `views/leader_dashboard.py` — Leader Dashboard page: KPI cards, charts, insight
- `analytics.py` — Pure KPI-computation functions (testable without Streamlit)
- `prompts/pre_call_brief.md` — Claude prompt for rep brief
- `prompts/pipeline_review.md` — Claude prompt for manager agenda
- `prompts/strategic_insight.md` — Claude prompt for leader insight
- `tests/__init__.py` — empty
- `tests/test_analytics.py` — unit tests for analytics.py
- `tests/test_claude_client_v2.py` — unit tests for the three new claude_client functions

**Modify:**
- `app.py` — move data loading + scoring + sidebar controls above tabs; add sidebar nav radio; add page routing
- `claude_client.py` — add `generate_pre_call_brief`, `generate_pipeline_review`, `generate_strategic_insight`

---

## Task 1: Restructure app.py — hoist data loading and add sidebar nav

**Files:**
- Modify: `app.py`

The current `app.py` loads data, validates, and scores inside `with tab_main:` (line 210+). Sidebar controls (owner filter, model selector) are also inside that block. We need these at the top level so every page can use them. We also add the nav radio and page routing.

- [ ] **Step 1: Add sidebar nav radio above the existing sidebar controls**

In `app.py`, find the line `# ---------------------------------------------------------------------------` just before `# Page setup` (line 125). Add the nav radio immediately after the sidebar version label block (after line 333). Actually — the cleanest approach is to add the `page` radio right after the CSS injection block (after line 183).

Find this line in `app.py`:
```python
# Header
st.markdown("""
<div style="padding:0 0 1.5rem 0">
```

Insert BEFORE it:
```python
# ---------------------------------------------------------------------------
# Sidebar navigation (top of sidebar, before all other controls)
# ---------------------------------------------------------------------------
page = st.sidebar.radio(
    "Navigate",
    ["Pipeline", "Rep Tools", "Manager View", "Leader Dashboard"],
    label_visibility="collapsed",
)
```

- [ ] **Step 2: Move data loading, validation, scoring, and sidebar controls above the tabs**

The current structure is:
```
tab_main, tab_method = st.tabs(...)   ← line 196
with tab_method: ...
with tab_main:
    # onboarding banner
    uploaded = st.file_uploader(...)  ← data loading starts here
    ... validate ...
    scored = score_deals(df_raw)
    # sidebar owner filter
    # sidebar model selector
    # summary metrics ...
```

Replace lines 196–333 (from `tab_main, tab_method = st.tabs(...)` through the sidebar version label) with this restructured block:

```python
# ---------------------------------------------------------------------------
# Data loading (top-level — needed by all pages)
# ---------------------------------------------------------------------------
uploaded = st.file_uploader(
    "Upload opportunities CSV",
    type="csv",
    label_visibility="collapsed",
    help="Upload a HubSpot-style CSV export. See 'How to use Deal Triage' above for required columns.",
)

if uploaded is not None:
    df_raw = pd.read_csv(uploaded)
elif SAMPLE_CSV.exists():
    df_raw = pd.read_csv(SAMPLE_CSV)
    if page == "Pipeline":
        st.markdown(
            '<div class="info-banner">ℹ️&nbsp; Showing sample data — upload your own CSV above to analyze real deals.</div>',
            unsafe_allow_html=True,
        )
else:
    st.error(
        f"Sample data not found at `{SAMPLE_CSV}`. "
        "Run `python3 scripts/generate_sample_data.py` from the project root first."
    )
    st.stop()

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
# Sidebar — shared controls
# ---------------------------------------------------------------------------
all_owners = sorted(scored["owner"].unique().tolist())
selected_owner = st.sidebar.selectbox(
    "Filter by owner",
    ["All"] + all_owners,
    help="Filter the at-risk deals by account executive.",
)
filtered = scored[scored["owner"] == selected_owner] if selected_owner != "All" else scored

model_choice = st.sidebar.selectbox(
    "Claude model",
    ["Haiku (fast)", "Sonnet (deeper)"],
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
tab_main, tab_method = st.tabs(["📊 Deal Triage", "📖 Methodology"])
```

- [ ] **Step 3: Fix the Pipeline tab — remove the data loading block that was inside it**

After the `with tab_main:` line (now further down), remove the file uploader, validation, scoring, and sidebar control blocks that were originally there (lines that are now duplicated after the restructure). Keep only:
- The onboarding banner block
- `top10 = filtered.head(TOP_N).copy()` and transcript loading
- The "no at-risk deals" info banner
- Summary metrics, pipeline chart, deal table, Claude analysis section, per-deal expanders

The `with tab_main:` block should start directly with the onboarding banner:
```python
with tab_main:
    # Onboarding banner
    if "onboarding_seen" not in st.session_state:
        st.session_state.onboarding_seen = False
    with st.expander(...):
        ...
    st.session_state.onboarding_seen = True

    top10 = filtered.head(TOP_N).copy()
    _transcripts = {str(did): find_transcript(str(did)) for did in top10["deal_id"]}
    deals_with_transcripts = {did for did, t in _transcripts.items() if t}

    if len(top10) == 0 and selected_owner != "All":
        ...
        st.stop()

    api_key = os.getenv("ANTHROPIC_API_KEY")

    # ... rest of pipeline content unchanged ...
```

- [ ] **Step 4: Verify the Pipeline page still works**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
streamlit run app.py
```

Expected: App loads, sidebar shows "Pipeline / Rep Tools / Manager View / Leader Dashboard" radio. Pipeline page renders identically to v1.5. Other pages show an error about missing `views` module (expected at this stage).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "refactor: hoist data loading to top level, add sidebar nav routing"
```

---

## Task 2: Scaffold views/ package

**Files:**
- Create: `views/__init__.py`

- [ ] **Step 1: Create the views package**

```bash
mkdir -p /Users/julian/dev/RevOps_Portfolio/deal-triage/views
touch /Users/julian/dev/RevOps_Portfolio/deal-triage/views/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add views/__init__.py
git commit -m "feat: add views/ package for page modules"
```

---

## Task 3: Pre-call brief — tests + prompt + claude_client function

**Files:**
- Create: `tests/__init__.py`, `tests/test_claude_client_v2.py`, `prompts/pre_call_brief.md`
- Modify: `claude_client.py`

- [ ] **Step 1: Create tests package**

```bash
mkdir -p /Users/julian/dev/RevOps_Portfolio/deal-triage/tests
touch /Users/julian/dev/RevOps_Portfolio/deal-triage/tests/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_claude_client_v2.py`:

```python
import json
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

SAMPLE_ROW = pd.Series({
    "deal_id": "DEAL-0001",
    "account_name": "Harbor Systems",
    "stage": "Proposal",
    "amount": 142000,
    "close_date": "2026-06-14",
    "days_in_stage": 18,
    "last_activity_date": "2026-05-16",
    "next_step": "Follow up with Sarah Chen",
    "owner": "Jen Matsuda",
    "industry": "FinTech",
    "employee_count": 500,
    "risk_score": 79,
    "_stage_pts": 34,
    "_act_pts": 22,
    "_close_pts": 15,
    "_stage_median": 21,
})

BRIEF_RESPONSE = {
    "context": "Discovery call 11 days ago. Sarah Chen (CFO) flagged a budget freeze through Q3.",
    "objections": [
        {"quote": "We've paused non-essential spend through Q3.", "label": "Budget", "status": "Unresolved"},
        {"quote": "", "label": "Stakeholder", "status": "Unresolved"},
    ],
    "agenda": [
        "Reopen the budget conversation — probe whether freeze applies to this category",
        "Get IT stakeholder on the call or schedule a separate technical review",
    ],
    "questions": [
        "Has anything changed on the budget side since we last spoke?",
        "Who on the IT side needs to be comfortable before you move forward?",
        "What would need to be true for you to sign before end of quarter?",
    ],
}


def _make_mock_response(payload: dict):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(payload))]
    return mock_msg


@patch("claude_client.Anthropic")
def test_generate_pre_call_brief_returns_required_keys(mock_anthropic_cls, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # Create minimal prompt file
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "pre_call_brief.md").write_text("Generate a pre-call brief.")
    monkeypatch.chdir(tmp_path)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_response(BRIEF_RESPONSE)

    from importlib import reload
    import claude_client as cc
    reload(cc)

    result = cc.generate_pre_call_brief(SAMPLE_ROW, transcript="", model="claude-haiku-4-5-20251001")

    assert result is not None
    assert "context" in result
    assert "objections" in result
    assert "agenda" in result
    assert "questions" in result
    assert isinstance(result["objections"], list)
    assert isinstance(result["agenda"], list)
    assert isinstance(result["questions"], list)


@patch("claude_client.Anthropic")
def test_generate_pre_call_brief_passes_transcript_to_prompt(mock_anthropic_cls, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "pre_call_brief.md").write_text("Generate a pre-call brief.")
    monkeypatch.chdir(tmp_path)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_response(BRIEF_RESPONSE)

    from importlib import reload
    import claude_client as cc
    reload(cc)

    cc.generate_pre_call_brief(SAMPLE_ROW, transcript="Budget freeze mentioned.", model="claude-haiku-4-5-20251001")

    call_args = mock_client.messages.create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "Budget freeze mentioned." in prompt_text


@patch("claude_client.Anthropic")
def test_generate_pre_call_brief_returns_none_without_api_key(mock_anthropic_cls, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from importlib import reload
    import claude_client as cc
    reload(cc)

    result = cc.generate_pre_call_brief(SAMPLE_ROW, transcript="", model="claude-haiku-4-5-20251001")
    assert result is None
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_claude_client_v2.py::test_generate_pre_call_brief_returns_required_keys -v
```

Expected: `FAILED` — `AttributeError: module 'claude_client' has no attribute 'generate_pre_call_brief'`

- [ ] **Step 4: Create the prompt file**

Create `prompts/pre_call_brief.md`:

```markdown
You are an expert B2B SaaS sales coach. Given CRM deal data and optionally a call transcript, generate a pre-call brief to help the account executive prepare for their next conversation.

Return ONLY a valid JSON object with this exact structure — no extra text, no markdown:
{
  "context": "2-3 sentences summarizing the deal situation and last interaction. If no transcript: note this and summarize from CRM signals.",
  "objections": [
    {"quote": "verbatim quote from transcript or empty string", "label": "Budget|Timing|Technical|Stakeholder|Competitive", "status": "Unresolved"}
  ],
  "agenda": ["specific action item 1", "specific action item 2", "specific action item 3"],
  "questions": ["verbatim question to ask?", "verbatim question to ask?", "verbatim question to ask?"]
}

Rules:
- context: If no transcript provided, write "No transcript available." then summarize deal risk from CRM signals (stage, days stagnant, close date).
- objections: Only include objections with clear evidence. Limit to 3 most significant. Use empty string for quote if no transcript.
- agenda: Ordered list. Specific to this deal's risk signals. Not generic sales advice.
- questions: Verbatim questions the rep should ask. Grounded in this specific deal. Not generic.

DEAL DATA:
{deal_data}
{transcript_section}
```

- [ ] **Step 5: Add `generate_pre_call_brief` to `claude_client.py`**

Append to `claude_client.py` (after `generate_followup_email`):

```python
def generate_pre_call_brief(
    row, transcript: str = "", model: str = DEFAULT_MODEL, existing_analysis: dict = None
) -> dict | None:
    """Generate a pre-call brief for a deal.

    Returns dict with keys: context, objections, agenda, questions.
    Returns None if API key missing or call fails.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

    prompt_template = _load_prompt("pre_call_brief")
    if not prompt_template:
        return None

    from datetime import date
    TODAY = date.today()

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
        f"- Risk Score: {row.get('risk_score', 0)}/100",
        f"- Score breakdown: Stage {row.get('_stage_pts', 0)}/40 · "
        f"Activity {row.get('_act_pts', 0)}/30 · Close {row.get('_close_pts', 0)}/30",
    ])

    if existing_analysis:
        deal_data += f"\n- Prior analysis summary: {existing_analysis.get('executive_summary') or existing_analysis.get('brief') or ''}"

    transcript_section = (
        f"\nCALL TRANSCRIPT EXCERPT:\n{transcript[:2500]}" if transcript else ""
    )

    prompt = (
        prompt_template
        .replace("{deal_data}", deal_data)
        .replace("{transcript_section}", transcript_section)
    )

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=800,
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
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_claude_client_v2.py -k "brief" -v
```

Expected: 3 tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add prompts/pre_call_brief.md claude_client.py tests/__init__.py tests/test_claude_client_v2.py
git commit -m "feat: add generate_pre_call_brief to claude_client with tests and prompt"
```

---

## Task 4: Rep Tools view module

**Files:**
- Create: `views/rep_tools.py`

- [ ] **Step 1: Create `views/rep_tools.py`**

```python
import glob
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
```

- [ ] **Step 2: Smoke-test Rep Tools in the browser**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
streamlit run app.py
```

Navigate to "Rep Tools" in sidebar. Select a deal. Click "Generate Brief". Verify:
- Brief renders all four panels with correct colors (slate / amber / green / purple)
- Deals with transcripts show the transcript note
- Deals without transcripts show the fallback note
- A deal that was already analyzed on the Pipeline page uses the existing analysis

- [ ] **Step 3: Commit**

```bash
git add views/rep_tools.py
git commit -m "feat: add Rep Tools view with Pre-Call Brief generator"
```

---

## Task 5: Pipeline review — tests + prompt + claude_client function

**Files:**
- Create: `prompts/pipeline_review.md`
- Modify: `claude_client.py`, `tests/test_claude_client_v2.py`

- [ ] **Step 1: Write the failing test — append to `tests/test_claude_client_v2.py`**

```python
PIPELINE_REVIEW_RESPONSE = {
    "pulse": "3 of 8 deals are high-risk this week. The biggest exposure is in Proposal stage — two deals have been stagnant for 18+ days. Focus this review on Marcus and Jen; their combined at-risk pipeline is $680K.",
    "reps": [
        {
            "rep_name": "Marcus Webb",
            "questions": [
                "What's the specific blocker keeping Apex Dynamics in Proposal for 3 weeks?",
                "Has Linktree's close date moved — and do they know it has?",
            ],
        },
        {
            "rep_name": "Jen Matsuda",
            "questions": [
                "Did the budget freeze conversation progress — or stall again?",
                "Is Sarah Chen still the champion or has someone else stepped up?",
            ],
        },
    ],
}


@patch("claude_client.Anthropic")
def test_generate_pipeline_review_returns_required_keys(mock_anthropic_cls, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "pipeline_review.md").write_text("Generate a pipeline review agenda.")
    monkeypatch.chdir(tmp_path)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_response(PIPELINE_REVIEW_RESPONSE)

    from importlib import reload
    import claude_client as cc
    reload(cc)

    rep_summaries = [
        {
            "rep_name": "Marcus Webb",
            "deals": [{"account_name": "Apex Dynamics", "stage": "Proposal", "risk_score": 84, "signal": "22 days stagnant"}],
        }
    ]
    result = cc.generate_pipeline_review(rep_summaries, model="claude-haiku-4-5-20251001")

    assert result is not None
    assert "pulse" in result
    assert "reps" in result
    assert isinstance(result["reps"], list)


@patch("claude_client.Anthropic")
def test_generate_pipeline_review_returns_none_without_api_key(mock_anthropic_cls, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from importlib import reload
    import claude_client as cc
    reload(cc)

    result = cc.generate_pipeline_review([], model="claude-haiku-4-5-20251001")
    assert result is None
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_claude_client_v2.py::test_generate_pipeline_review_returns_required_keys -v
```

Expected: `FAILED` — `AttributeError: module 'claude_client' has no attribute 'generate_pipeline_review'`

- [ ] **Step 3: Create `prompts/pipeline_review.md`**

```markdown
You are a sales manager preparing for a weekly pipeline review meeting. Given a summary of your team's deals grouped by rep, generate a structured meeting agenda as JSON.

Return ONLY a valid JSON object — no extra text, no markdown:
{
  "pulse": "2-3 sentence plain-English summary of the pipeline state. Include specific numbers (deal counts, dollar values, rep names). No filler.",
  "reps": [
    {
      "rep_name": "Full name",
      "questions": ["specific question grounded in their deals", "another specific question"]
    }
  ]
}

Rules:
- pulse: Name specific reps and specific risk patterns. Use the numbers provided. No generic statements.
- reps array: Include ONLY reps with at least one deal with risk_score >= 60. Reps with all-healthy pipelines are omitted.
- questions: 2-3 per rep. Must reference the specific deals or signals listed for that rep. Not generic sales manager questions.

TEAM PIPELINE DATA:
{rep_summaries}
```

- [ ] **Step 4: Add `generate_pipeline_review` to `claude_client.py`**

Append after `generate_pre_call_brief`:

```python
def generate_pipeline_review(rep_summaries: list, model: str = DEFAULT_MODEL) -> dict | None:
    """Generate a pipeline review meeting agenda.

    rep_summaries: list of dicts, each with keys: rep_name, deals (list of deal dicts).
    Returns dict with keys: pulse (str), reps (list of {rep_name, questions}).
    Returns None if API key missing or call fails.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

    prompt_template = _load_prompt("pipeline_review")
    if not prompt_template:
        return None

    lines = []
    for rep in rep_summaries:
        lines.append(f"\n{rep['rep_name']}:")
        for deal in rep.get("deals", []):
            lines.append(
                f"  - {deal['account_name']} | {deal['stage']} | "
                f"Score {deal['risk_score']}/100 | {deal.get('signal', '')}"
            )
    rep_block = "\n".join(lines) if lines else "No high-risk deals found."

    prompt = prompt_template.replace("{rep_summaries}", rep_block)

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
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
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_claude_client_v2.py -k "pipeline_review" -v
```

Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add prompts/pipeline_review.md claude_client.py tests/test_claude_client_v2.py
git commit -m "feat: add generate_pipeline_review to claude_client with tests and prompt"
```

---

## Task 6: Manager View module

**Files:**
- Create: `views/manager_view.py`

- [ ] **Step 1: Create `views/manager_view.py`**

```python
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


```

- [ ] **Step 2: Smoke-test Manager View in the browser**

```bash
streamlit run app.py
```

Navigate to "Manager View". Click "Generate Agenda". Verify:
- Pipeline Pulse banner renders in blue with a specific summary
- Reps with high-risk deals show deals + purple question boxes
- Reps with all-healthy pipeline show the one-liner
- Reps are sorted by avg risk score (highest risk rep first)

- [ ] **Step 3: Commit**

```bash
git add views/manager_view.py
git commit -m "feat: add Manager View with Pipeline Review Meeting Mode"
```

---

## Task 7: Analytics module — tests + implementation

**Files:**
- Create: `analytics.py`, `tests/test_analytics.py`

- [ ] **Step 1: Write failing tests in `tests/test_analytics.py`**

```python
import pandas as pd
import pytest
from datetime import date, timedelta

TODAY = date.today()


def make_scored_df():
    """5-deal test fixture matching score_deals() output schema."""
    return pd.DataFrame({
        "deal_id":            ["D001", "D002", "D003", "D004", "D005"],
        "stage":              ["Proposal", "Proposal", "Discovery", "Demo", "Negotiation"],
        "amount":             [100_000,   50_000,   200_000,  75_000,  150_000],
        "risk_score":         [85,        30,        75,       45,       20],
        "days_in_stage":      [30,        10,        25,       15,        5],
        "last_activity_date": [
            str(TODAY - timedelta(days=20)),   # 20d stale → act_pts high
            str(TODAY - timedelta(days=3)),
            str(TODAY - timedelta(days=16)),   # 16d stale
            str(TODAY - timedelta(days=8)),
            str(TODAY - timedelta(days=1)),
        ],
        "close_date":         [
            str(TODAY - timedelta(days=5)),    # past due
            str(TODAY + timedelta(days=30)),
            str(TODAY + timedelta(days=10)),
            str(TODAY + timedelta(days=60)),
            str(TODAY + timedelta(days=90)),
        ],
        "_stage_pts":         [40, 10, 38, 18,  5],
        "_act_pts":           [22,  5, 22, 14,  0],
        "_close_pts":         [30, 15, 25,  5,  0],
        "_stage_median":      [21, 21, 14, 14, 21],
        "owner":              ["Alice", "Bob", "Alice", "Charlie", "Bob"],
    })


def test_compute_high_risk_rate():
    from analytics import compute_high_risk_rate
    df = make_scored_df()
    # D001 (85) and D003 (75) are >= 70; all 5 are in open stages
    assert compute_high_risk_rate(df) == 40.0


def test_compute_high_risk_rate_empty():
    from analytics import compute_high_risk_rate
    df = make_scored_df()
    df["stage"] = "Closed Won"  # no open stages
    assert compute_high_risk_rate(df) == 0.0


def test_compute_avg_days_stagnant():
    from analytics import compute_avg_days_stagnant
    df = make_scored_df()
    # (30 + 10 + 25 + 15 + 5) / 5 = 17.0
    assert compute_avg_days_stagnant(df) == 17.0


def test_compute_at_risk_pipeline():
    from analytics import compute_at_risk_pipeline
    df = make_scored_df()
    # D001 ($100K, score 85) + D003 ($200K, score 75) = $300K
    assert compute_at_risk_pipeline(df) == 300_000.0


def test_compute_proposal_health_rate():
    from analytics import compute_proposal_health_rate
    df = make_scored_df()
    # Proposal deals: D001 (score 85, NOT healthy) + D002 (score 30, healthy)
    # 1/2 = 50.0%
    assert compute_proposal_health_rate(df) == 50.0


def test_compute_proposal_health_rate_no_proposal_deals():
    from analytics import compute_proposal_health_rate
    df = make_scored_df()
    df["stage"] = "Discovery"
    assert compute_proposal_health_rate(df) == 0.0


def test_compute_signal_counts_non_transcript_signals():
    from analytics import compute_signal_counts
    df = make_scored_df()
    counts = compute_signal_counts(df, transcripts_dir="nonexistent_dir")
    # Stage stagnation (_stage_pts == 40): D001 (40) and D003 (38 — not 40, so only D001)
    assert counts["Stage stagnation ≥2× median"] == 1
    # No activity 14+ days: D001 (20d) and D003 (16d)
    assert counts["No activity in 14+ days"] == 2
    # Past due close: D001 (5d past)
    assert counts["Close date past due"] == 1
    # Transcript signals — no transcripts dir, should be 0
    assert counts["Budget objection (transcript)"] == 0
    assert counts["Competitor mentioned (transcript)"] == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_analytics.py -v
```

Expected: All 7 tests `FAILED` — `ModuleNotFoundError: No module named 'analytics'`

- [ ] **Step 3: Create `analytics.py`**

```python
import re
from datetime import date
from pathlib import Path

import pandas as pd

OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}
TODAY = date.today()


def compute_high_risk_rate(df: pd.DataFrame) -> float:
    open_df = df[df["stage"].isin(OPEN_STAGES)]
    if len(open_df) == 0:
        return 0.0
    return round(len(open_df[open_df["risk_score"] >= 70]) / len(open_df) * 100, 1)


def compute_avg_days_stagnant(df: pd.DataFrame) -> float:
    open_df = df[df["stage"].isin(OPEN_STAGES)]
    if len(open_df) == 0:
        return 0.0
    return round(float(open_df["days_in_stage"].mean()), 1)


def compute_at_risk_pipeline(df: pd.DataFrame) -> float:
    open_df = df[df["stage"].isin(OPEN_STAGES)]
    return float(open_df[open_df["risk_score"] >= 70]["amount"].sum())


def compute_proposal_health_rate(df: pd.DataFrame) -> float:
    proposal_df = df[df["stage"] == "Proposal"]
    if len(proposal_df) == 0:
        return 0.0
    return round(len(proposal_df[proposal_df["risk_score"] < 40]) / len(proposal_df) * 100, 1)


def compute_signal_counts(df: pd.DataFrame, transcripts_dir: str = "data/sample/transcripts") -> dict:
    """Count how many open deals exhibit each risk signal."""
    open_df = df[df["stage"].isin(OPEN_STAGES)].copy()

    # Stage stagnation >= 2× median: _stage_pts at max (40 pts = 2× threshold)
    stagnation_count = int((open_df.get("_stage_pts", pd.Series(0, index=open_df.index)) >= 40).sum())

    # No activity in 14+ days
    open_df["_last_act_dt"] = pd.to_datetime(open_df["last_activity_date"], errors="coerce")
    inactivity_count = int(
        ((pd.Timestamp.today() - open_df["_last_act_dt"]).dt.days >= 14).sum()
    )

    # Close date past due
    open_df["_close_dt"] = pd.to_datetime(open_df["close_date"], errors="coerce")
    pastdue_count = int((open_df["_close_dt"] < pd.Timestamp.today()).sum())

    # Transcript keyword signals
    budget_count = 0
    competitor_count = 0
    tx_path = Path(transcripts_dir)
    if tx_path.exists():
        for _, row in open_df.iterrows():
            matches = list(tx_path.glob(f"{row['deal_id']}_*.txt"))
            if not matches:
                continue
            text = matches[0].read_text(encoding="utf-8").lower()
            if re.search(r"\b(budget|freeze|cost|pricing|expensive)\b", text):
                budget_count += 1
            if re.search(r"\b(competitor|competing|alternative|versus|vs\.?)\b", text):
                competitor_count += 1

    return {
        "Stage stagnation ≥2× median": stagnation_count,
        "No activity in 14+ days": inactivity_count,
        "Close date past due": pastdue_count,
        "Budget objection (transcript)": budget_count,
        "Competitor mentioned (transcript)": competitor_count,
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_analytics.py -v
```

Expected: All 7 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add analytics.py tests/test_analytics.py
git commit -m "feat: add analytics module with KPI computations and tests"
```

---

## Task 8: Strategic insight — tests + prompt + claude_client function

**Files:**
- Create: `prompts/strategic_insight.md`
- Modify: `claude_client.py`, `tests/test_claude_client_v2.py`

- [ ] **Step 1: Write the failing test — append to `tests/test_claude_client_v2.py`**

```python
STRATEGIC_INSIGHT_TEXT = (
    "Stage stagnation is the dominant risk signal this month — 14 deals are stuck beyond "
    "2× the historical median for their stage, concentrated in Proposal (9 of 14). "
    "Budget objections are surfacing early in cycles, which historically correlates with longer deal cycles. "
    "Recommend a messaging review on how ROI is quantified in early calls."
)


@patch("claude_client.Anthropic")
def test_generate_strategic_insight_returns_string(mock_anthropic_cls, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "strategic_insight.md").write_text("Generate a strategic insight.")
    monkeypatch.chdir(tmp_path)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=STRATEGIC_INSIGHT_TEXT)]
    mock_client.messages.create.return_value = mock_msg

    from importlib import reload
    import claude_client as cc
    reload(cc)

    signal_counts = {"Stage stagnation ≥2× median": 14, "No activity in 14+ days": 11}
    rep_profiles = [{"rep_name": "Marcus Webb", "avg_risk": 78.0, "deal_count": 3}]

    result = cc.generate_strategic_insight(signal_counts, rep_profiles, model="claude-haiku-4-5-20251001")

    assert isinstance(result, str)
    assert len(result) > 50


@patch("claude_client.Anthropic")
def test_generate_strategic_insight_returns_none_without_api_key(mock_anthropic_cls, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from importlib import reload
    import claude_client as cc
    reload(cc)

    result = cc.generate_strategic_insight({}, [], model="claude-haiku-4-5-20251001")
    assert result is None
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/test_claude_client_v2.py::test_generate_strategic_insight_returns_string -v
```

Expected: `FAILED` — `AttributeError: module 'claude_client' has no attribute 'generate_strategic_insight'`

- [ ] **Step 3: Create `prompts/strategic_insight.md`**

```markdown
You are a revenue operations analyst presenting to a VP of Sales or CRO. Given pipeline signal data and rep performance profiles, write a strategic insight.

Write a single paragraph of 3-5 sentences. No JSON, no markdown, no bullet points — plain prose only.

Include:
1. The dominant risk pattern (most frequent signal and its count)
2. Where it is concentrated (stage, rep, or deal size)
3. What this likely indicates about a process or messaging gap
4. One specific strategic recommendation

Rules:
- Use the numbers provided. Be specific.
- No filler: no "It is important to note", no "Overall the pipeline shows".
- Write as if presenting to a CRO who has 60 seconds to read this.

PIPELINE SIGNAL DATA:
{signal_counts}

REP PERFORMANCE PROFILES:
{rep_profiles}
```

- [ ] **Step 4: Add `generate_strategic_insight` to `claude_client.py`**

Append after `generate_pipeline_review`:

```python
def generate_strategic_insight(
    signal_counts: dict, rep_profiles: list, model: str = DEFAULT_MODEL
) -> str | None:
    """Generate a plain-text strategic insight paragraph for the Leader Dashboard.

    signal_counts: dict of {signal_name: deal_count}.
    rep_profiles: list of dicts with rep_name, avg_risk, deal_count.
    Returns a plain-text paragraph string, or None on failure.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

    prompt_template = _load_prompt("strategic_insight")
    if not prompt_template:
        return None

    signal_lines = "\n".join(f"- {k}: {v} deals" for k, v in signal_counts.items())
    rep_lines = "\n".join(
        f"- {r['rep_name']}: avg risk {r['avg_risk']:.0f}/100, {r['deal_count']} open deals"
        for r in rep_profiles
    )

    prompt = (
        prompt_template
        .replace("{signal_counts}", signal_lines or "No signal data available.")
        .replace("{rep_profiles}", rep_lines or "No rep data available.")
    )

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None
```

- [ ] **Step 5: Run all tests to confirm they pass**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/ -v
```

Expected: All tests PASSED (7 analytics + 7 claude_client).

- [ ] **Step 6: Commit**

```bash
git add prompts/strategic_insight.md claude_client.py tests/test_claude_client_v2.py
git commit -m "feat: add generate_strategic_insight to claude_client with tests and prompt"
```

---

## Task 9: Leader Dashboard view module

**Files:**
- Create: `views/leader_dashboard.py`

- [ ] **Step 1: Create `views/leader_dashboard.py`**

```python
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

    prev = st.session_state[snapshot_key]

    # ── KPI cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    def _delta_str(curr, prev_val, higher_is_worse=True):
        if curr == prev_val:
            return None
        diff = curr - prev_val
        sign = "↑" if diff > 0 else "↓"
        if higher_is_worse:
            color = "#ef4444" if diff > 0 else "#22c55e"
        else:
            color = "#22c55e" if diff > 0 else "#ef4444"
        return f'<span style="color:{color};font-size:0.75rem">{sign} {abs(diff):.1f}</span>'

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
```

- [ ] **Step 2: Smoke-test Leader Dashboard**

```bash
streamlit run app.py
```

Navigate to "Leader Dashboard". Verify:
- 4 KPI cards render with correct values from sample data
- Signal frequency bar chart renders (horizontal bars, color-coded)
- Rep risk profile bar chart renders
- "Refresh Insight" button generates a Claude insight paragraph in green panel
- On first load with no prior snapshot, metrics show no trend arrows (only values)
- Navigating away and back: KPI values are stable, insight is cached

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/julian/dev/RevOps_Portfolio/deal-triage
python -m pytest tests/ -v
```

Expected: All 14 tests PASSED.

- [ ] **Step 4: Commit**

```bash
git add views/leader_dashboard.py
git commit -m "feat: add Leader Dashboard with Win/Loss Signal Intelligence"
```

---

## Task 10: End-to-end verification

- [ ] **Step 1: Full smoke test — all four pages**

```bash
streamlit run app.py
```

Run through this checklist:

| Check | Expected |
|---|---|
| Sidebar shows 4 nav options | Pipeline · Rep Tools · Manager View · Leader Dashboard |
| Pipeline page loads | Identical to v1.5 — metrics, chart, table, analysis all work |
| Upload custom CSV | Works on Pipeline page, data flows to all other pages |
| Rep Tools — deal with transcript | Brief generates; context/objections/agenda/questions all populate |
| Rep Tools — deal without transcript | Brief generates; context says "No transcript available" |
| Rep Tools — deal analyzed on Pipeline first | Brief references existing analysis context |
| Manager View — Generate Agenda | Pulse banner + per-rep sections sorted by risk; healthy reps show one-liner |
| Leader Dashboard — KPIs | Values match manual counts from sample data |
| Leader Dashboard — Refresh Insight | Green insight panel renders with deal-specific patterns |
| Navigation — Pipeline analyses persist | Analyze on Pipeline; switch to Rep Tools; existing analyses available |

- [ ] **Step 2: Run full test suite one final time**

```bash
python -m pytest tests/ -v
```

Expected: 14 tests PASSED, 0 failed.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: v2 complete — rep brief, manager review, leader dashboard with sidebar nav"
```

---

## Verification (spec cross-check)

| Spec requirement | Task |
|---|---|
| Sidebar nav radio — Pipeline · Rep Tools · Manager View · Leader Dashboard | Task 1 |
| views/ package (not pages/ — avoids Streamlit native conflict) | Task 2 |
| generate_pre_call_brief — 4-section JSON | Task 3 |
| Rep Tools: deal selector, brief panels (slate/amber/green/purple) | Task 4 |
| generate_pipeline_review — pulse + rep questions | Task 5 |
| Manager View: pulse banner, per-rep sections, urgency sort | Task 6 |
| analytics.py KPI functions (pure, unit-tested) | Task 7 |
| generate_strategic_insight — plain-text paragraph | Task 8 |
| Leader Dashboard: 4 KPIs, signal chart, rep chart, insight | Task 9 |
| Session state sharing — Pipeline analyses flow to Rep Tools | Task 1 + 4 |
| No transcript fallback in rep brief | Task 4 |
| Snapshot trend indicators (—  on first visit) | Task 9 |
