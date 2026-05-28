# Deal Triage v2 — Feature Design Spec

**Date:** 2026-05-28  
**Status:** Approved for implementation

---

## Context

Deal Triage v1.5 is a strong portfolio project with a pipeline health dashboard, heuristic risk scoring, and Claude-powered per-deal analysis. It demonstrates both technical depth (Claude integration, modular architecture) and AE domain expertise (scoring methodology, buying process analysis).

The next step is making it feel like a real product three distinct personas would actually use: reps preparing for calls, managers running pipeline reviews, and leaders reading the health of the business. v2 adds one high-value experience for each — all three powered by the same underlying scoring and Claude integration already in place.

---

## Decisions Summary

| Question | Decision |
|---|---|
| Improvement theme | Deeper deal intelligence (A) + manager/leader views (B) + AI sophistication (C) |
| Scope model | One killer experience per audience |
| Rep experience | Pre-Call Brief Generator |
| Manager experience | Pipeline Review Meeting Mode |
| Leader experience | Win/Loss Signal Dashboard |
| Navigation | Sidebar nav (radio) — Pipeline · Rep Tools · Manager View · Leader Dashboard |
| Architecture | Single `app.py` router + three page modules in `pages/` |

---

## Architecture

`app.py` stays the entry point and becomes a thin router. No existing logic moves.

### New files

```
pages/
  rep_tools.py          # render(df, explanations, model)
  manager_view.py       # render(df, explanations, model)
  leader_dashboard.py   # render(df, model)

prompts/
  pre_call_brief.md     # Rep brief Claude prompt
  pipeline_review.md    # Manager agenda Claude prompt
  strategic_insight.md  # Leader insight Claude prompt
```

### Sidebar navigation

`app.py` adds a `st.radio` nav at the top of the sidebar:

```python
page = st.sidebar.radio("View", ["Pipeline", "Rep Tools", "Manager View", "Leader Dashboard"])
```

The existing pipeline content renders when `page == "Pipeline"`. Other values dispatch to the corresponding module's `render()` function, passing `df`, `st.session_state.explanations`, and the selected model.

### Session state sharing

Claude analyses computed on the Pipeline page are stored in `st.session_state.explanations` (already the case in v1.5). Rep Tools reads from this dict — if a deal has already been analyzed, the brief can reference that analysis. No extra API calls needed for deals already processed.

### `claude_client.py` additions

Three new functions alongside the existing two:

- `generate_pre_call_brief(row, transcript, model)` → dict with 4 keys: `context`, `objections`, `agenda`, `questions`
- `generate_pipeline_review(rep_summaries, model)` → dict with `pulse` and `reps` (list)
- `generate_strategic_insight(signal_counts, rep_profiles, model)` → string paragraph

---

## Feature 1: Rep Tools — Pre-Call Brief

### Entry point

`pages/rep_tools.py` — `render(df, explanations, model)`

### UX

A deal selector dropdown (all open deals, sorted by risk score desc) and a **Generate Brief** button. Below: the four-panel brief.

### Brief panels

| Panel | Color | Content |
|---|---|---|
| Context from Most Recent Call | Neutral slate (#f8fafc / #cbd5e1) | 2–3 sentence summary of last transcript. Falls back to "No transcript available — brief based on CRM signals only." |
| Open Objections | Amber (#fef9f0 / #fde68a) | Bulleted list. Each objection has: verbatim quote (if transcript), label (Budget / Timing / Technical / Stakeholder), status (Unresolved). If no objections found: "No objections identified in available data." |
| Recommended Agenda | Green (#f0fdf4 / #86efac) | Ordered list of 2–3 action items for the next call, grounded in the deal's specific risk signals. |
| 3 Questions to Ask | Purple (#faf5ff / #d8b4fe) | Verbatim questions Claude recommends. Specific to this deal — not generic sales questions. |

### Claude prompt (`prompts/pre_call_brief.md`)

Receives: deal CRM row, risk score breakdown, transcript excerpt (first 2500 chars if available), existing analysis from `explanations` dict if present.

Returns: JSON with keys `context`, `objections` (list of `{quote, label, status}`), `agenda` (list of strings), `questions` (list of strings).

### Edge cases

- No transcript: brief still generates, context panel shows a muted note, objections may be empty
- Deal already analyzed on Pipeline page: pass existing analysis into prompt context to avoid contradictions

---

## Feature 2: Manager View — Pipeline Review Meeting Mode

### Entry point

`pages/manager_view.py` — `render(df, explanations, model)`

### UX

A **Generate Agenda** button. Below: Pipeline Pulse banner, then per-rep sections sorted by urgency (highest avg risk score first).

### Pipeline Pulse banner

Blue (#f0f7ff / #93c5fd). 2–3 sentences. Claude writes this from the aggregate signal data: how many high-risk deals, where concentration is, which reps need attention. Specific numbers, not filler.

### Per-rep sections

Each rep gets a card with:
- Header: name · deal count · total pipeline value · risk badge (High Risk / Medium / All Green)
- **Deals to Inspect**: list of deals above risk threshold (≥60), showing name · stage · key risk flag · score
- **Suggested Questions** (purple, matching Rep Tools palette): 2–3 questions specific to that rep's at-risk deals, grounded in what the signals show
- **Reps with no high-risk deals**: single muted line — "No high-risk deals. Keep it brief — acknowledge momentum and move on."

### Claude prompt (`prompts/pipeline_review.md`)

Receives: a compact rep-grouped summary (rep name, deals with scores and key signals). Does NOT receive full individual analyses — keeps prompt lean. Claude returns JSON: `pulse` (string) + `reps` (list of `{rep_name, questions: list}`).

Questions are merged with the heuristic deal data (scores, stages, flags) which are computed locally — Claude only generates the qualitative coaching questions.

---

## Feature 3: Leader View — Win/Loss Signal Dashboard

### Entry point

`pages/leader_dashboard.py` — `render(df, model)`

### UX

No button — renders immediately from the loaded dataset. Four KPI cards at top, two-column charts below, Claude insight at the bottom.

### KPI cards (4)

All derived from `score_deals()` output — no new Claude calls:

| Card | Computation |
|---|---|
| High-Risk Rate | % of open deals with score ≥70 |
| Avg Days Stagnant | Mean `days_in_stage` across open deals |
| At-Risk Pipeline Value | Sum of `amount` for deals with score ≥70 |
| Proposal Health Rate | % of Proposal-stage deals with score <40 (low-risk proxy; labeled "Proposal Health %" in UI) |

Trend indicators: on first visit to the Leader Dashboard, the current values are stored as `st.session_state.leader_snapshot`. On subsequent visits within the session, trend arrows and deltas are computed against that snapshot. On first visit, trend indicators render as "—" (no baseline yet).

### Signal frequency chart

Horizontal bar chart (Altair, matching existing pipeline chart style). Counts per signal type across all open deals:
- Stage stagnation >2× median
- No activity in 14+ days
- Close date past due
- Budget objection (transcript keyword match)
- Competitor mentioned (transcript keyword match)

Transcript keyword matching is a lightweight local scan — no Claude call.

### Rep portfolio risk profiles

Horizontal bar chart. Each rep: avg risk score across their open deals. Color-coded by tier. Sorted descending.

### Claude Strategic Insight

Green panel (#f0fdf4 / #86efac). One paragraph. Claude receives: signal frequency counts, rep avg scores, deal count and pipeline value by stage. Returns a plain-English pattern observation + one strategic recommendation. Cached in `st.session_state.strategic_insight` — only regenerated if user clicks **Refresh Insight**.

New Claude prompt: `prompts/strategic_insight.md`.

---

## What stays the same

- Pipeline page: untouched — scoring, analysis, email draft, feedback, export all unchanged
- `feedback.py`: unchanged
- `claude_client.py`: two existing functions unchanged, three new ones added
- Sample data (100 deals, 15 transcripts): works for all three views without modification
- `.gitignore`, `METHODOLOGY.md`, `requirements.txt`: no changes needed

---

## Verification

1. Run `streamlit run app.py` — sidebar nav shows all four pages
2. Upload sample CSV — Pipeline page renders identically to v1.5
3. Rep Tools: select a deal with a transcript → Generate Brief → all four panels render with deal-specific content
4. Rep Tools: select a deal without a transcript → brief generates with fallback note in context panel
5. Manager View: Generate Agenda → Pipeline Pulse renders, rep sections sorted by risk, healthy reps show one-liner
6. Leader Dashboard: renders without button press, KPIs correct, charts render, Claude insight generates and caches
7. Navigate between pages — existing Pipeline analyses persist in session state
