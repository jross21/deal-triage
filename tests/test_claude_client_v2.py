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
