import re

import pandas as pd

from constants import OPEN_STAGES
from transcripts import find_transcript


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
    for _, row in open_df.iterrows():
        text = find_transcript(row["deal_id"], directory=transcripts_dir).lower()
        if not text:
            continue
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
