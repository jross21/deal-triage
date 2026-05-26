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
