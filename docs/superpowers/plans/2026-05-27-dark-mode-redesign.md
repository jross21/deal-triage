# Dark Mode Redesign + Theme Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a premium dark mode (navy bg, sky-blue accent, risk-colored glowing expander borders) with a light/dark toggle switch in the sidebar.

**Architecture:** All styling lives in a single `app.py` CSS block (lines 115–169). Replace it with three string constants — `CSS_SIDEBAR` (always dark), `CSS_SHARED` (both themes), `CSS_DARK` / `CSS_LIGHT` (theme-specific) — injected conditionally based on a `st.toggle()` in the sidebar. The toggle writes to `st.session_state["dark_mode"]`, which is read at the top of the script before CSS injection on every rerun. Per-deal expander glow borders use CSS `:has()` selectors injected from inside each expander.

**Tech Stack:** Streamlit, Python, Altair, inline CSS via `st.markdown(unsafe_allow_html=True)`

---

## File Map

| File | Changes |
|------|---------|
| `app.py` | All changes: CSS constants, toggle wiring, chart wrapper, info banners, expander borders, inline HTML theme updates |
| `.streamlit/config.toml` | No changes — `primaryColor = "#dc2626"` stays (drives risk progress bars) |

---

## Task 1: CSS Architecture — constants + toggle wiring

**Files:**
- Modify: `app.py:113–169` (replace CSS block) and `app.py:312–316` (sidebar section)

- [ ] **Step 1: Replace the CSS block (lines 115–169) with theme constants + conditional injection**

  Replace from `st.set_page_config(...)` down to the end of the `</style>` block (lines 113–169) with:

  ```python
  st.set_page_config(page_title="Deal Triage", layout="wide")

  # Read theme preference persisted by the toggle widget (default: dark)
  dark_mode = st.session_state.get("dark_mode", True)

  # ── CSS constants ──────────────────────────────────────────────────────────

  CSS_SIDEBAR = """
  [data-testid="stSidebar"] { background: #0c1425 !important; }
  [data-testid="stSidebar"] label {
      color: #94a3b8 !important; font-size: 0.65rem !important;
      text-transform: uppercase; letter-spacing: 0.1em;
  }
  [data-testid="stSidebar"] .stSelectbox > div > div {
      background: rgba(255,255,255,0.05) !important;
      border-color: rgba(255,255,255,0.1) !important;
      color: #94a3b8 !important;
  }
  [data-testid="stSidebar"] p, [data-testid="stSidebar"] div { color: #475569; }
  [data-testid="stSidebar"] .stToggle label { font-size: 0.75rem !important; color: #94a3b8 !important; }
  """

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

  CSS_DARK = """
  .stApp { background: #0f172a !important; }
  [data-testid="stMetric"] {
      background: #1e293b !important; border: 1px solid #334155 !important;
      border-radius: 10px !important; padding: 1rem 1.25rem !important;
      box-shadow: 0 0 0 1px rgba(56,189,248,0.05), 0 2px 8px rgba(0,0,0,0.3) !important;
  }
  [data-testid="stMetricLabel"] > div { color: #94a3b8 !important; }
  [data-testid="stMetricValue"] > div { color: #f1f5f9 !important; }
  [data-testid="stExpander"] {
      background: #1e293b !important; border: 1px solid #334155 !important;
      border-radius: 10px !important;
  }
  [data-testid="stExpander"] summary { color: #f1f5f9 !important; }
  [data-baseweb="tab-list"] { border-bottom-color: #1e293b !important; }
  [data-baseweb="tab"] { color: #475569 !important; }
  [aria-selected="true"][data-baseweb="tab"] { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }
  [data-testid="stBaseButton-primary"] > button {
      background: linear-gradient(135deg, #0284c7, #38bdf8) !important;
      border: none !important; color: white !important; font-weight: 700 !important;
      box-shadow: 0 0 16px rgba(56,189,248,0.25) !important;
  }
  .chart-card {
      background: #1e293b; border: 1px solid #334155; border-radius: 10px;
      padding: 1rem 1.25rem 0.25rem; margin-bottom: 1rem;
  }
  .info-banner {
      background: rgba(56,189,248,0.07); border: 1px solid rgba(56,189,248,0.18);
      border-radius: 8px; padding: 0.65rem 1rem; color: #7dd3fc;
      font-size: 0.875rem; margin-bottom: 1rem;
  }
  .badge-high   { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
  .badge-medium { background: rgba(245,158,11,0.12); color: #fbbf24; border: 1px solid rgba(245,158,11,0.25); }
  .badge-low    { background: rgba(34,197,94,0.12);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
  """

  CSS_LIGHT = """
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

  # Inject all CSS
  st.markdown(
      f"<style>{CSS_SIDEBAR}{CSS_SHARED}{CSS_DARK if dark_mode else CSS_LIGHT}</style>",
      unsafe_allow_html=True,
  )
  ```

- [ ] **Step 2: Add theme toggle to the sidebar**

  In the sidebar section (currently around line 312, after the `model_choice` selectbox and before the version markdown), add:

  ```python
  st.sidebar.divider()
  st.sidebar.toggle("🌙  Dark mode", value=dark_mode, key="dark_mode")
  ```

  The `key="dark_mode"` causes Streamlit to write the toggle's value to `st.session_state["dark_mode"]` automatically on each interaction, which the read at the top of the script picks up on the next rerun.

- [ ] **Step 3: Start the app and verify the toggle works**

  ```bash
  cd /Users/julian/dev/RevOps_Portfolio/deal-triage
  streamlit run app.py
  ```

  Expected:
  - App opens in dark mode by default (navy background, slate-800 cards)
  - Clicking the toggle in the sidebar switches to light mode and back
  - Sidebar always stays dark in both modes
  - "Analyze with Claude" button is sky-blue gradient in both modes

- [ ] **Step 4: Commit**

  ```bash
  git add app.py
  git commit -m "feat: CSS architecture — dark/light theme constants + toggle"
  ```

---

## Task 2: Wrap chart in card + transparent background

**Files:**
- Modify: `app.py` — chart section (currently around lines 349–371)

- [ ] **Step 1: Wrap the chart with a card div and make the Altair background transparent**

  Find this block (around line 349):
  ```python
  st.subheader("Pipeline Health")
  ```

  Replace the entire chart section (from `st.subheader("Pipeline Health")` through `st.altair_chart(pipeline_chart, use_container_width=True)`) with:

  ```python
  st.subheader("Pipeline Health")
  st.markdown('<div class="chart-card">', unsafe_allow_html=True)

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
      .configure(background="transparent")
  )
  st.altair_chart(pipeline_chart, use_container_width=True)
  st.markdown('</div>', unsafe_allow_html=True)
  ```

  Note: `.configure(background="transparent")` must be the last call on the chart object. It cannot be chained before `.encode()` or `.properties()`.

- [ ] **Step 2: Verify in browser**

  In dark mode: the chart should appear inside a slate-800 rounded card with no white background bleeding through. In light mode: white card with a subtle shadow.

- [ ] **Step 3: Commit**

  ```bash
  git add app.py
  git commit -m "feat: wrap pipeline chart in themed card, transparent bg"
  ```

---

## Task 3: Replace info banners with theme-aware custom HTML

**Files:**
- Modify: `app.py` — two `st.info()` call sites

The app has two `st.info()` calls that render in Streamlit's default blue regardless of theme:
1. Line ~252: "Showing sample data…"
2. Line ~441: "AI explanations disabled…"

- [ ] **Step 1: Replace the sample data info banner**

  Find (around line 252):
  ```python
  st.info("Showing sample data — upload your own CSV above to analyze real deals.")
  ```

  Replace with:
  ```python
  st.markdown(
      '<div class="info-banner">ℹ️&nbsp; Showing sample data — upload your own CSV above to analyze real deals.</div>',
      unsafe_allow_html=True,
  )
  ```

- [ ] **Step 2: Replace the "no API key" info banner**

  Find (around line 441):
  ```python
  st.info(
      "**AI explanations disabled.** Add `ANTHROPIC_API_KEY=your_key` to `.env` "
      "and restart to enable Claude-powered risk analysis."
  )
  ```

  Replace with:
  ```python
  st.markdown(
      '<div class="info-banner">⚠️&nbsp; <strong>AI explanations disabled.</strong> '
      'Add <code>ANTHROPIC_API_KEY=your_key</code> to <code>.env</code> and restart to enable Claude-powered risk analysis.</div>',
      unsafe_allow_html=True,
  )
  ```

- [ ] **Step 3: Also replace the empty-owner info banner**

  Find (around line 297):
  ```python
  st.info(
      f"No at-risk deals for **{selected_owner}** — "
      ...
  )
  ```

  Replace with:
  ```python
  st.markdown(
      f'<div class="info-banner">ℹ️&nbsp; No at-risk deals for <strong>{selected_owner}</strong> — '
      f'{owner_total} open deal{"s" if owner_total != 1 else ""} all scoring below 40.</div>',
      unsafe_allow_html=True,
  )
  ```

- [ ] **Step 4: Verify in browser**

  Toggle between dark and light — all three banners should use the appropriate themed color (sky-blue tint in dark, standard blue in light). No default Streamlit blue banners should appear.

- [ ] **Step 5: Commit**

  ```bash
  git add app.py
  git commit -m "feat: theme-aware info banners replace st.info()"
  ```

---

## Task 4: Deal expander risk-tier glow borders

**Files:**
- Modify: `app.py` — deal expander loop (around lines 481–490) and constants section

The approach uses CSS `:has()` selectors injected from inside each expander. A hidden `<span>` with a unique `data-deal-id` attribute is the first element inside each expander body. The injected `<style>` tag uses `:has([data-deal-id="..."])` to reach back up and style the parent expander. `:has()` is supported in all modern browsers (Chrome 105+, Firefox 121+, Safari 15.4+).

- [ ] **Step 1: Add tier border CSS constants near the top of app.py (after OPEN_STAGES)**

  After the line `OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}`, add:

  ```python
  # Per-tier expander border styles (dark mode / light mode)
  _TIER_BORDER = {
      "dark": {
          "high":   "border:1px solid rgba(239,68,68,0.35)!important;box-shadow:0 0 20px rgba(239,68,68,0.1),0 2px 8px rgba(0,0,0,0.3)!important;",
          "medium": "border:1px solid rgba(245,158,11,0.3)!important;box-shadow:0 0 16px rgba(245,158,11,0.08),0 2px 8px rgba(0,0,0,0.3)!important;",
          "low":    "border:1px solid #334155!important;box-shadow:0 2px 8px rgba(0,0,0,0.2)!important;",
      },
      "light": {
          "high":   "border:1px solid #fca5a5!important;box-shadow:0 2px 8px rgba(239,68,68,0.1)!important;",
          "medium": "border:1px solid #fde68a!important;box-shadow:0 2px 8px rgba(245,158,11,0.08)!important;",
          "low":    "border:1px solid #e2e8f0!important;",
      },
  }
  ```

- [ ] **Step 2: Inject the per-deal border style as the first thing inside each expander**

  Find the expander loop opening (around line 490):
  ```python
  with st.expander(label, expanded=(rank == 1)):
  ```

  Add these two lines immediately after the `with st.expander(...):`  line (as the first thing inside the `with` block, before `# Zone 1: CRM signals`):

  ```python
  with st.expander(label, expanded=(rank == 1)):
      # Inject risk-tier border via :has() selector scoped to this deal's unique ID
      _theme_key = "dark" if dark_mode else "light"
      _tier_key = _risk_tier(row["risk_score"]).lower()
      _border_css = _TIER_BORDER[_theme_key][_tier_key]
      st.markdown(
          f'<style>[data-testid="stExpander"]:has([data-deal-id="{row["deal_id"]}"]) '
          f'{{ {_border_css} }}</style>'
          f'<span data-deal-id="{row["deal_id"]}" style="display:none"></span>',
          unsafe_allow_html=True,
      )

      # Zone 1: CRM signals
      m1, m2, m3 = st.columns(3)
      ...
  ```

- [ ] **Step 3: Verify in browser**

  Open the app. In dark mode:
  - High-risk deal expanders (score ≥ 70) should have a faint red glowing border
  - Medium-risk (score 40–69) should have a faint amber border
  - Low-risk (score < 40) should have a standard slate-700 border

  Toggle to light mode — borders switch to soft red/amber/gray without glow.

  If the `:has()` selector doesn't apply (check browser devtools), fall back to this alternative — inject a style before each expander using nth-of-type counting:

  ```python
  # Fallback: before the with st.expander() call, inject nth-child targeting
  # Count = rank + 1 because onboarding expander is :nth-of-type(1)
  st.markdown(
      f'<style>[data-testid="stExpander"]:nth-of-type({rank + 1}) '
      f'{{ {_border_css} }}</style>',
      unsafe_allow_html=True,
  )
  with st.expander(label, expanded=(rank == 1)):
      ...
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add app.py
  git commit -m "feat: risk-tier glow borders on deal expanders via :has() selectors"
  ```

---

## Task 5: Update inline HTML styles to respect theme

**Files:**
- Modify: `app.py` — inline HTML blocks inside the deal expander loop

Three inline HTML strings in the deal loop use hardcoded light-mode colors. Update them to use Python f-string variables that branch on `dark_mode`.

- [ ] **Step 1: Update transcript quote boxes**

  Find the quote rendering block (around line 557):
  ```python
  for quote in quotes:
      st.markdown(
          f"""<div style="border-left:3px solid #dc2626;padding:8px 14px;
          background:#fef2f2;margin:6px 0 10px 0;border-radius:0 4px 4px 0">
          ...
          </div>""",
          unsafe_allow_html=True,
      )
  ```

  Replace with:
  ```python
  _quote_bg = "rgba(239,68,68,0.06)" if dark_mode else "#fef2f2"
  _quote_text_color = "#94a3b8" if dark_mode else "#374151"
  _quote_attr_color = "#475569" if dark_mode else "#9ca3af"
  for quote in quotes:
      st.markdown(
          f"""<div style="border-left:3px solid #dc2626;padding:8px 14px;
          background:{_quote_bg};margin:6px 0 10px 0;border-radius:0 4px 4px 0">
          <span style="font-style:italic;color:{_quote_text_color}">"{quote}"</span><br>
          <span style="font-size:0.72rem;color:{_quote_attr_color};margin-top:3px;display:block">— Call transcript</span>
          </div>""",
          unsafe_allow_html=True,
      )
  ```

- [ ] **Step 2: Update buying process analysis box**

  Find the BPA block (around line 583):
  ```python
  if bpa:
      st.markdown(
          f"""<div style="background:#f8fafc;border:1px solid #e2e8f0;
          border-radius:8px;padding:12px 16px;margin:10px 0">
          <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;
          color:#64748b;font-weight:600;margin-bottom:6px">Buying Process Analysis</div>
          <div style="color:#1e293b;line-height:1.6">{bpa}</div>
          </div>""",
          unsafe_allow_html=True,
      )
  ```

  Replace with:
  ```python
  if bpa:
      _bpa_bg      = "#1e293b"  if dark_mode else "#f8fafc"
      _bpa_border  = "#334155"  if dark_mode else "#e2e8f0"
      _bpa_label   = "#475569"  if dark_mode else "#64748b"
      _bpa_text    = "#94a3b8"  if dark_mode else "#1e293b"
      st.markdown(
          f"""<div style="background:{_bpa_bg};border:1px solid {_bpa_border};
          border-radius:8px;padding:12px 16px;margin:10px 0">
          <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;
          color:{_bpa_label};font-weight:600;margin-bottom:6px">Buying Process Analysis</div>
          <div style="color:{_bpa_text};line-height:1.6">{bpa}</div>
          </div>""",
          unsafe_allow_html=True,
      )
  ```

- [ ] **Step 3: Update the page header HTML**

  Find the header block (around line 172):
  ```python
  st.markdown("""
  <div style="padding:0 0 1.5rem 0">
    <div style="font-size:1.75rem;font-weight:800;color:#0f172a;...">Deal Triage</div>
    <div style="color:#64748b;...">Surface and act...</div>
  </div>
  """, unsafe_allow_html=True)
  ```

  Replace with:
  ```python
  _title_color    = "#f1f5f9" if dark_mode else "#0f172a"
  _subtitle_color = "#64748b"
  st.markdown(f"""
  <div style="padding:0 0 1.5rem 0">
    <div style="font-size:1.75rem;font-weight:800;color:{_title_color};letter-spacing:-0.02em;line-height:1.2">Deal Triage</div>
    <div style="color:{_subtitle_color};margin-top:0.35rem;font-size:0.9rem">Surface and act on the deals most likely to slip this quarter.</div>
  </div>
  """, unsafe_allow_html=True)
  ```

- [ ] **Step 4: Verify in browser**

  Toggle between dark and light modes. Check:
  - Transcript quote boxes: dark red-tinted bg in dark, light red bg in light
  - BPA box: slate-800 bg in dark, white-ish bg in light
  - Page title: near-white in dark, near-black in light

- [ ] **Step 5: Commit**

  ```bash
  git add app.py
  git commit -m "feat: inline HTML styles branch on dark_mode variable"
  ```

---

## Task 6: Final polish + full verification

**Files:**
- Modify: `app.py` — sidebar version label

- [ ] **Step 1: Update the sidebar version label to use the sky-blue accent**

  Find (around line 312):
  ```python
  st.sidebar.markdown(
      "<div style='padding-top:2rem;color:#475569;font-size:0.65rem;"
      "text-transform:uppercase;letter-spacing:0.07em'>Deal Triage · v1.5</div>",
      unsafe_allow_html=True,
  )
  ```

  Replace with:
  ```python
  st.sidebar.markdown(
      "<div style='padding-top:1rem;color:#334155;font-size:0.65rem;"
      "text-transform:uppercase;letter-spacing:0.07em'>Deal Triage · v1.5</div>",
      unsafe_allow_html=True,
  )
  ```

- [ ] **Step 2: Full end-to-end visual verification checklist**

  Run `streamlit run app.py` and verify each item:

  **Dark mode (default):**
  - [ ] Page background is slate-900 (`#0f172a`), not pure black
  - [ ] Sidebar is slightly darker than main bg (`#0c1425`)
  - [ ] Three metric cards: slate-800 bg, subtle blue-glow border
  - [ ] Pipeline Health chart sits inside a slate-800 card, no white background
  - [ ] Info banner (sample data notice) is sky-blue tinted
  - [ ] "Analyze with Claude" button is a sky-blue gradient with soft glow
  - [ ] Deal expanders: high-risk = red border glow, medium = amber border glow, low = neutral border
  - [ ] Inside deal expanders: transcript quote boxes have dark translucent red bg
  - [ ] Inside deal expanders: BPA box has slate-800 bg

  **Light mode (after toggling):**
  - [ ] Page background switches to `#f8fafc`
  - [ ] Sidebar stays dark
  - [ ] Metric cards: white bg, `#e2e8f0` border
  - [ ] Chart sits in a white card with subtle shadow
  - [ ] Info banner is standard blue
  - [ ] Deal expanders: high-risk = soft red border, medium = soft amber border
  - [ ] Confidence badges: solid colored pills (red/amber/green)

  **Interaction:**
  - [ ] Toggling dark/light and back doesn't break any session state (analysis results persist)
  - [ ] Filtering by owner still works in both themes
  - [ ] Uploading a CSV still works

- [ ] **Step 3: Final commit**

  ```bash
  git add app.py
  git commit -m "feat: dark mode redesign — navy theme, sky-blue accent, risk-tier expander borders, theme toggle"
  ```

---

## Self-Review

**Spec coverage:**
- ✅ Premium dark (navy bg `#0f172a`, `#1e293b` cards) — Task 1
- ✅ Glowing accent borders on deal cards — Task 4
- ✅ Sky blue (#38bdf8) for buttons/active states — Task 1 (CSS_DARK/LIGHT)
- ✅ Risk colors unchanged — not modified
- ✅ Sidebar always dark — Task 1 (CSS_SIDEBAR injected unconditionally)
- ✅ Light/dark toggle in sidebar — Task 1
- ✅ Chart wrapped in card — Task 2
- ✅ Info banners theme-aware — Task 3
- ✅ Inline HTML (quotes, BPA) theme-aware — Task 5

**No placeholders.** All CSS values, selectors, and Python code are concrete and complete.

**Type consistency.** `dark_mode` is a `bool` read consistently throughout. `_risk_tier()` already exists in the file. `_TIER_BORDER` keys match the tier strings returned by `_risk_tier().lower()` ("high", "medium", "low").
