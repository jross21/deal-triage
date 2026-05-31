from datetime import date, timedelta

import pandas as pd

from constants import MEDIUM_RISK_THRESHOLD, STAGE_THRESHOLDS
from scoring import (
    compute_risk_breakdown,
    compute_stage_benchmarks,
    risk_tier,
    score_deals,
)

TODAY = date(2026, 5, 31)


def _row(**overrides):
    base = {
        "stage": "Proposal",
        "days_in_stage": 0,
        "last_activity_date": str(TODAY),
        "close_date": str(TODAY + timedelta(days=90)),
    }
    base.update(overrides)
    return base


# ── risk_tier boundaries ────────────────────────────────────────────────────

def test_risk_tier_boundaries():
    assert risk_tier(70) == "High"
    assert risk_tier(69) == "Medium"
    assert risk_tier(40) == "Medium"
    assert risk_tier(39) == "Low"
    assert risk_tier(0) == "Low"


# ── close-date pressure ─────────────────────────────────────────────────────

def test_close_pressure_past_due_is_max():
    _, bd = compute_risk_breakdown(
        _row(close_date=str(TODAY - timedelta(days=1))), today=TODAY
    )
    assert bd["close_pts"] == 30


def test_close_pressure_tiers():
    def close_pts(days):
        _, bd = compute_risk_breakdown(
            _row(close_date=str(TODAY + timedelta(days=days))), today=TODAY
        )
        return bd["close_pts"]

    assert close_pts(10) == 25   # < 14
    assert close_pts(25) == 15   # <= 30
    assert close_pts(45) == 5    # <= 60
    assert close_pts(90) == 0    # > 60


def test_close_pressure_bad_date_uses_fallback():
    _, bd = compute_risk_breakdown(_row(close_date="not-a-date"), today=TODAY)
    assert bd["close_pts"] == 10


# ── activity recency ────────────────────────────────────────────────────────

def test_activity_tiers():
    def act_pts(days):
        _, bd = compute_risk_breakdown(
            _row(last_activity_date=str(TODAY - timedelta(days=days))), today=TODAY
        )
        return bd["act_pts"]

    assert act_pts(0) == 0
    assert act_pts(7) == 14
    assert act_pts(14) == 22
    assert act_pts(21) == 30
    assert act_pts(40) == 30   # capped


def test_activity_missing_uses_fallback():
    row = _row()
    del row["last_activity_date"]
    _, bd = compute_risk_breakdown(row, today=TODAY)
    assert bd["act_pts"] == 15


# ── stage stagnation ────────────────────────────────────────────────────────

def test_stage_pts_caps_at_40():
    # Proposal default threshold is 21; 10x median should still cap at 40.
    _, bd = compute_risk_breakdown(_row(stage="Proposal", days_in_stage=210), today=TODAY)
    assert bd["stage_pts"] == 40


def test_stage_pts_scales_with_median():
    # days_in == threshold → 20 pts (half of max).
    threshold = STAGE_THRESHOLDS["Proposal"]
    _, bd = compute_risk_breakdown(
        _row(stage="Proposal", days_in_stage=threshold), today=TODAY
    )
    assert bd["stage_pts"] == 20


def test_total_capped_at_100():
    total, _ = compute_risk_breakdown(
        _row(
            stage="Proposal",
            days_in_stage=999,
            last_activity_date=str(TODAY - timedelta(days=60)),
            close_date=str(TODAY - timedelta(days=5)),
        ),
        today=TODAY,
    )
    assert total == 100


# ── benchmarks ──────────────────────────────────────────────────────────────

def test_benchmarks_use_median_when_enough_samples():
    df = pd.DataFrame({
        "stage": ["Demo"] * 5,
        "days_in_stage": [10, 20, 30, 40, 50],
    })
    benchmarks = compute_stage_benchmarks(df)
    assert benchmarks["Demo"] == 30   # median of the five


def test_benchmarks_fall_back_below_min_sample():
    df = pd.DataFrame({
        "stage": ["Demo"] * 3,
        "days_in_stage": [10, 20, 30],
    })
    benchmarks = compute_stage_benchmarks(df)
    assert benchmarks["Demo"] == STAGE_THRESHOLDS["Demo"]   # default, not median


# ── score_deals ─────────────────────────────────────────────────────────────

def test_score_deals_filters_closed_and_sorts_desc():
    df = pd.DataFrame({
        "deal_id": ["A", "B", "C"],
        "stage": ["Proposal", "Closed Won", "Discovery"],
        "days_in_stage": [60, 5, 5],
        "last_activity_date": [
            str(TODAY - timedelta(days=30)),
            str(TODAY),
            str(TODAY),
        ],
        "close_date": [
            str(TODAY - timedelta(days=5)),
            str(TODAY + timedelta(days=10)),
            str(TODAY + timedelta(days=90)),
        ],
    })
    scored = score_deals(df, today=TODAY)
    assert list(scored["deal_id"]) == ["A", "C"]            # B (Closed Won) dropped
    assert scored.iloc[0]["risk_score"] >= scored.iloc[1]["risk_score"]
    # breakdown columns populated
    for col in ("_stage_pts", "_act_pts", "_close_pts", "_stage_median"):
        assert col in scored.columns
