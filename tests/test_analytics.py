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
    # Stage stagnation (_stage_pts == 40): D001 (40) only (D003 has 38, not 40)
    assert counts["Stage stagnation ≥2× median"] == 1
    # No activity 14+ days: D001 (20d) and D003 (16d)
    assert counts["No activity in 14+ days"] == 2
    # Past due close: D001 (5d past)
    assert counts["Close date past due"] == 1
    # Transcript signals — no transcripts dir, should be 0
    assert counts["Budget objection (transcript)"] == 0
    assert counts["Competitor mentioned (transcript)"] == 0
