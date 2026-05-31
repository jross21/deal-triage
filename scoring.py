"""Deal risk scoring engine.

Extracted from app.py so the core logic can be imported and unit-tested without
booting Streamlit. Pure functions over a pandas DataFrame / row dicts.

Composite score (0–100) per open deal:
  - stage stagnation vs the team's own median   → up to 40 pts
  - activity recency (staleness)                 → up to 30 pts
  - close-date pressure                          → up to 30 pts
"""

from datetime import date

from constants import (
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    MIN_BENCHMARK_SAMPLE,
    OPEN_STAGES,
    STAGE_THRESHOLDS,
)


def risk_tier(score) -> str:
    """Map a composite score to a High/Medium/Low tier label."""
    if score >= HIGH_RISK_THRESHOLD:
        return "High"
    if score >= MEDIUM_RISK_THRESHOLD:
        return "Medium"
    return "Low"


def compute_stage_benchmarks(df):
    """Compute median days_in_stage per stage from full pipeline history."""
    benchmarks = dict(STAGE_THRESHOLDS)
    for stage, group in df.groupby("stage"):
        if len(group) >= MIN_BENCHMARK_SAMPLE:
            try:
                median = int(group["days_in_stage"].median())
                if median > 0:
                    benchmarks[stage] = median
            except (TypeError, ValueError):
                pass
    return benchmarks


def compute_risk_breakdown(row, benchmarks=None, today=None):
    """Return (total_score, breakdown_dict) for a deal row."""
    today = today or date.today()
    stage = row.get("stage", "")
    threshold = (benchmarks or STAGE_THRESHOLDS).get(stage, 14)

    try:
        days_in = int(row.get("days_in_stage", 0))
    except (ValueError, TypeError):
        days_in = 0
    stage_pts = min(40, int(days_in / threshold * 20))

    try:
        last_act = date.fromisoformat(str(row["last_activity_date"]))
        stale = max(0, (today - last_act).days)
        if stale >= 21:
            act_pts = 30
        elif stale >= 14:
            act_pts = 22
        elif stale >= 7:
            act_pts = 14
        else:
            act_pts = int(stale / 7 * 14)
    except (ValueError, TypeError, KeyError):
        act_pts = 15

    try:
        close = date.fromisoformat(str(row["close_date"]))
        days_until = (close - today).days
        if days_until < 0:
            close_pts = 30
        elif days_until < 14:
            close_pts = 25
        elif days_until <= 30:
            close_pts = 15
        elif days_until <= 60:
            close_pts = 5
        else:
            close_pts = 0
    except (ValueError, TypeError, KeyError):
        close_pts = 10

    total = min(100, stage_pts + act_pts + close_pts)
    return total, {"stage_pts": stage_pts, "act_pts": act_pts, "close_pts": close_pts}


def score_deals(df, today=None):
    """Filter to open stages, score all deals, return sorted descending."""
    benchmarks = compute_stage_benchmarks(df)
    open_df = df[df["stage"].isin(OPEN_STAGES)].copy()
    results = open_df.apply(
        lambda r: compute_risk_breakdown(r.to_dict(), benchmarks, today), axis=1
    )
    open_df["risk_score"]    = results.apply(lambda x: x[0])
    open_df["_stage_pts"]    = results.apply(lambda x: x[1]["stage_pts"])
    open_df["_act_pts"]      = results.apply(lambda x: x[1]["act_pts"])
    open_df["_close_pts"]    = results.apply(lambda x: x[1]["close_pts"])
    open_df["_stage_median"] = open_df["stage"].map(benchmarks)
    return open_df.sort_values("risk_score", ascending=False).reset_index(drop=True)
