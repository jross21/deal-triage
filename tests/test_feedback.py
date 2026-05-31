import json
from importlib import reload


def _load_feedback_module(tmp_path, monkeypatch):
    """Reload feedback with FEEDBACK_PATH pointed at a temp file."""
    monkeypatch.chdir(tmp_path)
    import feedback as fb
    reload(fb)
    fb.FEEDBACK_PATH = tmp_path / "feedback.json"
    return fb


def test_summarize_feedback_empty(tmp_path, monkeypatch):
    fb = _load_feedback_module(tmp_path, monkeypatch)
    summary = fb.summarize_feedback()
    assert summary["total"] == 0
    assert summary["helpful_rate"] is None
    for tier in fb.TIERS:
        assert summary["by_tier"][tier] == {"total": 0, "positive": 0, "helpful_rate": None}


def test_summarize_feedback_mixed(tmp_path, monkeypatch):
    fb = _load_feedback_module(tmp_path, monkeypatch)
    records = [
        {"confidence": "High", "feedback": "positive"},
        {"confidence": "High", "feedback": "positive"},
        {"confidence": "High", "feedback": "negative"},   # High: 2/3 = 66.7%
        {"confidence": "Low", "feedback": "negative"},
        {"confidence": "Low", "feedback": "negative"},     # Low: 0/2 = 0.0%
    ]
    fb.FEEDBACK_PATH.write_text(json.dumps(records), encoding="utf-8")

    summary = fb.summarize_feedback()
    assert summary["total"] == 5
    assert summary["positive"] == 2
    assert summary["helpful_rate"] == 40.0
    assert summary["by_tier"]["High"]["helpful_rate"] == 66.7
    assert summary["by_tier"]["Low"]["helpful_rate"] == 0.0
    assert summary["by_tier"]["Medium"]["helpful_rate"] is None   # no Medium records


def test_record_feedback_then_summarize(tmp_path, monkeypatch):
    fb = _load_feedback_module(tmp_path, monkeypatch)
    deal = {"deal_id": "D1", "account_name": "Acme", "stage": "Demo", "risk_score": 72}
    fb.record_feedback(deal, confidence="High", verdict="positive")
    fb.record_feedback(deal, confidence="High", verdict="negative")

    summary = fb.summarize_feedback()
    assert summary["by_tier"]["High"]["total"] == 2
    assert summary["by_tier"]["High"]["positive"] == 1
    assert summary["by_tier"]["High"]["helpful_rate"] == 50.0
