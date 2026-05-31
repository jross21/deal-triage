import json
from datetime import datetime
from pathlib import Path

FEEDBACK_PATH = Path("data/feedback/feedback.json")


def record_feedback(deal: dict, confidence: str, verdict: str) -> None:
    """Append a feedback record to the local JSON store.

    verdict: 'positive' or 'negative'
    """
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)

    records = load_feedback()
    records.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "deal_id": str(deal.get("deal_id", "")),
        "account_name": str(deal.get("account_name", "")),
        "stage": str(deal.get("stage", "")),
        "risk_score": int(deal.get("risk_score", 0)),
        "confidence": confidence,
        "feedback": verdict,
    })

    FEEDBACK_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def load_feedback() -> list:
    """Return all stored feedback records, or an empty list if none exist."""
    if not FEEDBACK_PATH.exists():
        return []
    try:
        return json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


TIERS = ("High", "Medium", "Low")


def summarize_feedback() -> dict:
    """Aggregate stored feedback into overall and per-tier helpful rates.

    Returns:
        {
          "total": int,
          "positive": int,
          "helpful_rate": float | None,   # % positive overall, None if no data
          "by_tier": {
              "High":   {"total": int, "positive": int, "helpful_rate": float | None},
              "Medium": {...},
              "Low":    {...},
          },
        }
    helpful_rate is None when a bucket has no records (avoids a misleading 0%).
    """
    records = load_feedback()

    def _rate(positive: int, total: int):
        return round(positive / total * 100, 1) if total else None

    by_tier = {}
    for tier in TIERS:
        tier_records = [r for r in records if r.get("confidence") == tier]
        pos = sum(1 for r in tier_records if r.get("feedback") == "positive")
        by_tier[tier] = {
            "total": len(tier_records),
            "positive": pos,
            "helpful_rate": _rate(pos, len(tier_records)),
        }

    total = len(records)
    positive = sum(1 for r in records if r.get("feedback") == "positive")
    return {
        "total": total,
        "positive": positive,
        "helpful_rate": _rate(positive, total),
        "by_tier": by_tier,
    }
