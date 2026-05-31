import json
from importlib import reload
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

SAMPLE_ROW = pd.Series({
    "deal_id": "DEAL-0001",
    "account_name": "Harbor Systems",
    "stage": "Proposal",
    "amount": 142000,
    "close_date": "2026-06-14",
    "days_in_stage": 18,
    "last_activity_date": "2026-05-16",
    "next_step": "Follow up with Sarah Chen",
    "owner": "Jen Matsuda",
    "industry": "FinTech",
    "employee_count": 500,
    "risk_score": 79,
    "_stage_pts": 34,
    "_act_pts": 22,
    "_close_pts": 15,
    "_stage_median": 21,
})

BRIEF_RESPONSE = {
    "context": "Discovery call 11 days ago. Sarah Chen (CFO) flagged a budget freeze through Q3.",
    "objections": [
        {"quote": "We've paused non-essential spend through Q3.", "label": "Budget", "status": "Unresolved"},
        {"quote": "", "label": "Stakeholder", "status": "Unresolved"},
    ],
    "agenda": [
        "Reopen the budget conversation — probe whether freeze applies to this category",
        "Get IT stakeholder on the call or schedule a separate technical review",
    ],
    "questions": [
        "Has anything changed on the budget side since we last spoke?",
        "Who on the IT side needs to be comfortable before you move forward?",
        "What would need to be true for you to sign before end of quarter?",
    ],
}


def _make_mock_response(payload: dict):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(payload))]
    return mock_msg


ANALYZE_RESPONSE = {
    "confidence": "Low",
    "quotes": [],
    "brief": "Deal is mid-cycle with no acute signals.",
    "next_action": "Confirm the economic buyer is engaged before the next call.",
}


def test_analyze_deal_uses_cached_system_block_and_data_in_user_message(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    # Mirror the real template's instruction/data boundary at "Deal data:".
    (prompt_dir / "deal_risk_explanation.md").write_text(
        "You are a RevOps analyst. Assess the deal.\n\nDeal data:\n{deal_data}{transcript_section}"
    )
    monkeypatch.chdir(tmp_path)

    import claude_client as cc
    reload(cc)

    with patch("claude_client.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(ANALYZE_RESPONSE)

        result = cc.analyze_deal(SAMPLE_ROW.to_dict(), transcript="Budget freeze mentioned.",
                                 model="claude-haiku-4-5-20251001")

    assert result == ANALYZE_RESPONSE
    kwargs = mock_client.messages.create.call_args.kwargs
    # Static instructions go in a cached system block...
    system = kwargs["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "RevOps analyst" in system[0]["text"]
    assert "Deal data:" not in system[0]["text"]
    # ...and the per-deal data + transcript go in the user message.
    user_content = kwargs["messages"][0]["content"]
    assert "Harbor Systems" in user_content
    assert "Budget freeze mentioned." in user_content


def test_generate_pre_call_brief_returns_required_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # Create minimal prompt file
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "pre_call_brief.md").write_text("Generate a pre-call brief.")
    monkeypatch.chdir(tmp_path)

    import claude_client as cc
    reload(cc)

    with patch("claude_client.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(BRIEF_RESPONSE)

        result = cc.generate_pre_call_brief(SAMPLE_ROW, transcript="", model="claude-haiku-4-5-20251001")

    assert result is not None
    assert "context" in result
    assert "objections" in result
    assert "agenda" in result
    assert "questions" in result
    assert isinstance(result["objections"], list)
    assert isinstance(result["agenda"], list)
    assert isinstance(result["questions"], list)


def test_generate_pre_call_brief_passes_transcript_to_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "pre_call_brief.md").write_text("Generate a pre-call brief.")
    monkeypatch.chdir(tmp_path)

    import claude_client as cc
    reload(cc)

    with patch("claude_client.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(BRIEF_RESPONSE)

        cc.generate_pre_call_brief(SAMPLE_ROW, transcript="Budget freeze mentioned.", model="claude-haiku-4-5-20251001")

        call_args = mock_client.messages.create.call_args
        prompt_text = call_args.kwargs["messages"][0]["content"]
        assert "Budget freeze mentioned." in prompt_text


def test_generate_pre_call_brief_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import claude_client as cc
    reload(cc)

    result = cc.generate_pre_call_brief(SAMPLE_ROW, transcript="", model="claude-haiku-4-5-20251001")
    assert result is None


PIPELINE_REVIEW_RESPONSE = {
    "pulse": "3 of 8 deals are high-risk this week. The biggest exposure is in Proposal stage — two deals have been stagnant for 18+ days. Focus this review on Marcus and Jen; their combined at-risk pipeline is $680K.",
    "reps": [
        {
            "rep_name": "Marcus Webb",
            "questions": [
                "What's the specific blocker keeping Apex Dynamics in Proposal for 3 weeks?",
                "Has Linktree's close date moved — and do they know it has?",
            ],
        },
        {
            "rep_name": "Jen Matsuda",
            "questions": [
                "Did the budget freeze conversation progress — or stall again?",
                "Is Sarah Chen still the champion or has someone else stepped up?",
            ],
        },
    ],
}


def test_generate_pipeline_review_returns_required_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "pipeline_review.md").write_text("Generate a pipeline review agenda.")
    monkeypatch.chdir(tmp_path)

    import claude_client as cc
    reload(cc)

    with patch("claude_client.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(PIPELINE_REVIEW_RESPONSE)

        rep_summaries = [
            {
                "rep_name": "Marcus Webb",
                "deals": [{"account_name": "Apex Dynamics", "stage": "Proposal", "risk_score": 84, "signal": "22 days stagnant"}],
            }
        ]
        result = cc.generate_pipeline_review(rep_summaries, model="claude-haiku-4-5-20251001")

    assert result is not None
    assert "pulse" in result
    assert "reps" in result
    assert isinstance(result["reps"], list)


def test_generate_pipeline_review_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import claude_client as cc
    reload(cc)

    result = cc.generate_pipeline_review([], model="claude-haiku-4-5-20251001")
    assert result is None


STRATEGIC_INSIGHT_TEXT = (
    "Stage stagnation is the dominant risk signal this month — 14 deals are stuck beyond "
    "2× the historical median for their stage, concentrated in Proposal (9 of 14). "
    "Budget objections are surfacing early in cycles, which historically correlates with longer deal cycles. "
    "Recommend a messaging review on how ROI is quantified in early calls."
)


def test_generate_strategic_insight_returns_string(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "strategic_insight.md").write_text("Generate a strategic insight.")
    monkeypatch.chdir(tmp_path)

    from unittest.mock import MagicMock
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=STRATEGIC_INSIGHT_TEXT)]
    mock_client.messages.create.return_value = mock_msg

    from importlib import reload
    import claude_client as cc
    reload(cc)

    with patch("claude_client.Anthropic") as mock_cls:
        mock_cls.return_value = mock_client
        signal_counts = {"Stage stagnation ≥2× median": 14, "No activity in 14+ days": 11}
        rep_profiles = [{"rep_name": "Marcus Webb", "avg_risk": 78.0, "deal_count": 3}]
        result = cc.generate_strategic_insight(signal_counts, rep_profiles, model="claude-haiku-4-5-20251001")

    assert isinstance(result, str)
    assert len(result) > 50


def test_generate_strategic_insight_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from importlib import reload
    import claude_client as cc
    reload(cc)

    result = cc.generate_strategic_insight({}, [], model="claude-haiku-4-5-20251001")
    assert result is None
