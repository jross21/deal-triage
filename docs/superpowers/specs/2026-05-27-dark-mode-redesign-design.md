# Visual Redesign: Dark Mode + Theme Toggle

**Date:** 2026-05-27  
**Status:** Approved

---

## Context

The app's current light-mode design is functional but visually plain — flat metric cards, no chart wrapper, default Streamlit component colors bleeding through (blue info banners, standard gray buttons). The goal is a premium dark-mode aesthetic that fits a RevOps portfolio demo: polished, readable, enterprise-grade. A light/dark toggle is included so users can switch to the familiar light theme if they prefer.

All CSS lives in a single `st.markdown(..., unsafe_allow_html=True)` block in `app.py` (lines ~115–169). The theme toggle is implemented via `st.session_state` + conditional CSS injection — no external libraries needed.

---

## Design Decisions

| Question | Answer |
|----------|--------|
| Overall direction | Premium Dark (deep navy, not pure black) |
| Card treatment | Glowing accent borders — risk-colored on deal cards, subtle blue on neutral |
| UI accent | Sky blue (`#38bdf8`) for buttons, active states, links |
| Risk colors | Unchanged: red / amber / green |
| Sidebar | Stays dark in both themes (like most SaaS tools) |
| Background (dark) | `#0f172a` (slate-900) — lightened from initial proposal for readability |
| Background (light) | `#f8fafc` (current design, unchanged) |

---

## Color Tokens

### Dark Mode
| Token | Value | Usage |
|-------|-------|-------|
| `--bg-app` | `#0f172a` | Page background |
| `--bg-card` | `#1e293b` | Metric cards, chart card, table, deal headers |
| `--bg-card-alt` | `#162032` | Deal body, inputs |
| `--border` | `#334155` | Neutral borders |
| `--border-glow` | `#1e3a5f` | Card borders with blue hint |
| `--text-primary` | `#f1f5f9` | Headings, values |
| `--text-secondary` | `#94a3b8` | Body text, captions |
| `--text-muted` | `#475569` | Labels, table headers |
| `--accent` | `#38bdf8` | Active states, links, toggle |
| `--accent-dark` | `#0284c7` | Button gradient start |

### Light Mode (inherits current design)
| Token | Value | Usage |
|-------|-------|-------|
| `--bg-app` | `#f8fafc` | Page background |
| `--bg-card` | `#ffffff` | Cards |
| `--border` | `#e2e8f0` | Borders |
| `--text-primary` | `#0f172a` | Primary text |
| `--accent` | `#0284c7` | Buttons, active states |

---

## Component Changes

### Global shell
- `.stApp` background → `var(--bg-app)`
- `.main .block-container` → unchanged (max-width 1080px, padding)
- Hide Streamlit chrome → unchanged

### Metric cards (`[data-testid="stMetric"]`)
- Background: `var(--bg-card)`
- Border: `1px solid var(--border-glow)` + `box-shadow: 0 0 0 1px rgba(56,189,248,0.05), 0 2px 8px rgba(0,0,0,0.15)`
- Label color: `var(--text-secondary)`
- Value color: `var(--text-primary)`
- Dark hover: border brightens to `rgba(56,189,248,0.2)`

### Pipeline Health chart
- Wrap in a `st.markdown()` div card before/after the `st.altair_chart()` call:
  ```python
  st.markdown('<div class="chart-card">', unsafe_allow_html=True)
  st.altair_chart(...)
  st.markdown('</div>', unsafe_allow_html=True)
  ```
- Card: `background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem`
- Altair chart background → set `config=alt.Config(background='transparent', view=alt.ViewConfig(stroke='transparent'))`

### Info banner
- Replace default `st.info()` with `st.markdown()` using custom class `.info-banner`
- Dark: sky-blue tinted bg/border/text
- Light: existing blue (`#eff6ff` / `#bfdbfe` / `#1d4ed8`)

### "Analyze with Claude" button
- Add `.stButton > button[kind="primary"]` override:
  - `background: linear-gradient(135deg, #0284c7, #38bdf8)`
  - `box-shadow: 0 0 16px rgba(56,189,248,0.2)`
  - `border: none; color: white; font-weight: 700`

### Deal expanders (`[data-testid="stExpander"]`)
- Base: `background: var(--bg-card); border-radius: 10px`
- High-risk deals: inject wrapper div with class `.deal-high` → `border: 1px solid rgba(239,68,68,0.3); box-shadow: 0 0 20px rgba(239,68,68,0.08)`
- Medium-risk deals: `.deal-medium` → `border: 1px solid rgba(245,158,11,0.25); box-shadow: 0 0 16px rgba(245,158,11,0.06)`
- Low-risk deals: `.deal-low` → standard border only

**Implementation:** In the per-deal render loop, wrap `st.expander(...)` context with a `st.markdown(f'<div class="deal-{tier}">', unsafe_allow_html=True)` before and `</div>` after. Requires the expander to be inside the div — test that Streamlit renders this correctly (may need `st.container()` wrapper).

### Confidence badges
- Dark mode: translucent pill — `rgba(239,68,68,0.15)` bg, `1px solid rgba(239,68,68,0.3)` border, `#f87171` text
- Light mode: existing solid pills (unchanged)

### Transcript quote boxes
- Dark: `background: rgba(239,68,68,0.06)` (same left-border red accent)
- Light: `background: #fef2f2` (unchanged)

### Sidebar
- Always dark (`#0c1425` bg, stays regardless of theme toggle)
- Dropdowns: `background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08)`

### Feedback buttons
- Styled as dark outlined buttons: `background: var(--bg-card); border: 1px solid var(--border); color: var(--text-muted)`
- "Draft follow-up" gets sky-blue tint: `background: var(--info-bg); border-color: var(--info-border); color: var(--accent-text)`

---

## Theme Toggle Implementation

Streamlit doesn't support CSS custom properties switching natively, so we use Python-level branching:

```python
# In sidebar
dark_mode = st.sidebar.toggle("🌙 Dark mode", value=True, key="dark_mode")

# Build CSS block
theme = DARK_CSS if dark_mode else LIGHT_CSS
st.markdown(f"<style>{theme}</style>", unsafe_allow_html=True)
```

Structure:
- `DARK_CSS`: Full CSS block targeting `[data-testid="*"]` selectors with dark values
- `LIGHT_CSS`: Full CSS block with light values (close to current design but with the new button/accent styles)
- Both blocks are constants defined near the top of `app.py`, replacing the current single `<style>` block

The sidebar itself is always styled dark (a separate `SIDEBAR_CSS` constant injected unconditionally).

**Default:** Dark mode on (`value=True`).

---

## Files to Modify

- **`app.py`** — all changes:
  - Lines ~115–169: Replace single CSS block with `DARK_CSS`, `LIGHT_CSS`, `SIDEBAR_CSS` constants + toggle-driven injection
  - Sidebar section: Add `st.toggle()` for theme switching
  - Chart render: Wrap with card div + pass `alt.Config(background='transparent')` to Altair
  - `st.info()` banner: Replace with `st.markdown()` custom div
  - Per-deal expander loop: Add risk-tier wrapper divs for glow borders

---

## Verification

1. Run `streamlit run app.py` and confirm dark mode loads by default
2. Toggle to light mode — verify all components switch cleanly, sidebar stays dark
3. Check deal expanders: high-risk cards should have red glow, medium amber, low neutral
4. Click "Analyze with Claude" — button should show sky-blue gradient with glow
5. Verify chart renders on transparent background inside dark card wrapper
6. Check info banner uses theme-appropriate colors in both modes
7. Resize to ~900px width — confirm layout doesn't break
