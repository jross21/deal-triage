import json
import logging
import os
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger(__name__)

PROMPT_DIR = Path("prompts")
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_FOLLOWUP_SYSTEM = (
    "You are a B2B SaaS account executive. "
    "Write a brief, direct follow-up email based on the deal context below. "
    "Format: Subject: <subject line>, then a blank line, then 3-4 sentences of body. "
    "No filler phrases like 'I hope this finds you well.' Sound human and specific to this deal."
)

# Lazily-created module-level client so we don't re-instantiate per call.
_CLIENT: Anthropic | None = None


def _client() -> Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = Anthropic()
    return _CLIENT


def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _complete(prompt: str, model: str, max_tokens: int, system=None) -> str | None:
    """Single entry point for a text completion. Returns stripped text or None.

    Logs the failure instead of swallowing it silently. `system` may be a plain
    string or a list of content blocks (used for prompt caching).
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system
        response = _client().messages.create(**kwargs)
        return response.content[0].text.strip()
    except Exception:
        logger.exception("Claude completion failed (model=%s)", model)
        return None


def _complete_json(prompt: str, model: str, max_tokens: int, system=None) -> dict | None:
    """Completion that expects a JSON object. Extracts the outermost {...}."""
    text = _complete(prompt, model, max_tokens, system=system)
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        logger.warning("Claude response contained no JSON object (model=%s)", model)
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        logger.exception("Failed to parse JSON from Claude response (model=%s)", model)
        return None


def _estimate_tier(row: dict, has_transcript: bool) -> str:
    """Pre-estimate confidence tier to set max_tokens before the API call."""
    score = int(row.get("risk_score", 0))
    if score >= 70 and has_transcript:
        return "High"
    if score < 45 or not has_transcript:
        return "Low"
    return "Medium"


def analyze_deal(row: dict, transcript: str = "", model: str = DEFAULT_MODEL) -> dict | None:
    """Call Claude to produce a tiered risk analysis for a deal.

    Returns a dict whose keys vary by confidence tier:
      Low:    {confidence, quotes, brief, next_action}
      Medium: {confidence, quotes, brief, risk_signals, next_action}
      High:   {confidence, quotes, executive_summary, risk_signals,
               buying_process_analysis, recommended_actions}
    Returns None if the API key is missing or the call fails.
    """
    prompt_template = _load_prompt("deal_risk_explanation")
    if not prompt_template:
        return None

    stage_median = int(row.get("_stage_median") or 14)
    deal_data = "\n".join([
        f"- Account: {row['account_name']}",
        f"- Stage: {row['stage']}",
        f"- Amount: ${int(row['amount']):,}",
        f"- Close Date: {row['close_date']}",
        f"- Days in Stage: {row['days_in_stage']}",
        f"- Last Activity: {row['last_activity_date']}",
        f"- Next Step: {row.get('next_step') or 'None'}",
        f"- Owner: {row['owner']}",
        f"- Industry: {row['industry']}",
        f"- Employee Count: {int(row['employee_count']):,}",
        f"- Risk Score: {row['risk_score']}/100",
        f"- Score breakdown: Stage {row.get('_stage_pts', 0)}/40 · "
        f"Activity {row.get('_act_pts', 0)}/30 · Close {row.get('_close_pts', 0)}/30",
        f"- Stage benchmark: {stage_median} days median for {row['stage']}",
    ])

    transcript_section = (
        f"\nCall transcript excerpt:\n{transcript[:2500]}" if transcript else ""
    )

    # Split the template into a static instruction prefix (sent as a cached
    # system block, identical across all deals in a batch) and the per-deal
    # data (the user message). The prompt file's data placeholders live under
    # the "Deal data:" marker, so split there.
    marker = "Deal data:"
    idx = prompt_template.find(marker)
    if idx != -1:
        instructions = prompt_template[:idx].rstrip()
        data_template = prompt_template[idx:]
    else:
        instructions = prompt_template
        data_template = "{deal_data}{transcript_section}"

    user_content = (
        data_template
        .replace("{deal_data}", deal_data)
        .replace("{transcript_section}", transcript_section)
    )
    # NOTE: prompt caching only activates once the system prefix exceeds the
    # model minimum (Sonnet 4.6: 2048 tokens, Haiku 4.5: 4096). Today's
    # instruction block is below that, so this is a harmless no-op that starts
    # paying off automatically if the prompt grows.
    system = [{"type": "text", "text": instructions, "cache_control": {"type": "ephemeral"}}]

    tier = _estimate_tier(row, bool(transcript))
    max_tokens = 1024 if tier == "High" else 512
    return _complete_json(user_content, model, max_tokens, system=system)


def generate_followup_email(row: dict, analysis: dict, model: str = DEFAULT_MODEL) -> str | None:
    """Draft a follow-up email for the AE based on deal context and Claude analysis.

    Returns plain text with 'Subject: ...' on the first line, or None on failure.
    """
    confidence = analysis.get("confidence", "")
    if confidence == "High":
        context_block = analysis.get("buying_process_analysis", "")
        action = (analysis.get("recommended_actions") or [{}])[0].get("action", "")
    else:
        context_block = analysis.get("brief", "")
        action = analysis.get("next_action", "")

    user_content = "\n".join([
        f"Account: {row['account_name']}",
        f"Stage: {row['stage']}",
        f"Days in stage: {row['days_in_stage']}",
        f"Close date: {row['close_date']}",
        f"Next step on file: {row.get('next_step') or 'None'}",
        f"Risk context: {context_block}",
        f"Recommended action: {action}",
    ])

    return _complete(user_content, model, max_tokens=300, system=_FOLLOWUP_SYSTEM)


def generate_pre_call_brief(
    row, transcript: str = "", model: str = DEFAULT_MODEL, existing_analysis: dict = None
) -> dict | None:
    """Generate a pre-call brief for a deal.

    Returns dict with keys: context, objections, agenda, questions.
    Returns None if API key missing or call fails.
    """
    prompt_template = _load_prompt("pre_call_brief")
    if not prompt_template:
        return None

    deal_data = "\n".join([
        f"- Account: {row['account_name']}",
        f"- Stage: {row['stage']}",
        f"- Amount: ${int(row['amount']):,}",
        f"- Close Date: {row['close_date']}",
        f"- Days in Stage: {row['days_in_stage']}",
        f"- Last Activity: {row['last_activity_date']}",
        f"- Next Step: {row.get('next_step') or 'None'}",
        f"- Owner: {row['owner']}",
        f"- Industry: {row['industry']}",
        f"- Risk Score: {row.get('risk_score', 0)}/100",
        f"- Score breakdown: Stage {row.get('_stage_pts', 0)}/40 · "
        f"Activity {row.get('_act_pts', 0)}/30 · Close {row.get('_close_pts', 0)}/30",
    ])

    if existing_analysis:
        deal_data += f"\n- Prior analysis summary: {existing_analysis.get('executive_summary') or existing_analysis.get('brief') or ''}"

    transcript_section = (
        f"\nCALL TRANSCRIPT EXCERPT:\n{transcript[:2500]}" if transcript else ""
    )

    prompt = prompt_template.replace("{deal_data}", deal_data)
    if "{transcript_section}" in prompt:
        prompt = prompt.replace("{transcript_section}", transcript_section)
    elif transcript_section:
        prompt += transcript_section

    return _complete_json(prompt, model, max_tokens=800)


def generate_pipeline_review(rep_summaries: list, model: str = DEFAULT_MODEL) -> dict | None:
    """Generate a pipeline review meeting agenda.

    rep_summaries: list of dicts, each with keys: rep_name, deals (list of deal dicts).
    Returns dict with keys: pulse (str), reps (list of {rep_name, questions}).
    Returns None if API key missing or call fails.
    """
    prompt_template = _load_prompt("pipeline_review")
    if not prompt_template:
        return None

    lines = []
    for rep in rep_summaries:
        lines.append(f"\n{rep['rep_name']}:")
        for deal in rep.get("deals", []):
            lines.append(
                f"  - {deal['account_name']} | {deal['stage']} | "
                f"Score {deal['risk_score']}/100 | {deal.get('signal', '')}"
            )
    rep_block = "\n".join(lines) if lines else "No high-risk deals found."

    prompt = prompt_template.replace("{rep_summaries}", rep_block)
    return _complete_json(prompt, model, max_tokens=1024)


def generate_strategic_insight(
    signal_counts: dict, rep_profiles: list, model: str = DEFAULT_MODEL
) -> str | None:
    """Generate a plain-text strategic insight paragraph for the Leader Dashboard.

    signal_counts: dict of {signal_name: deal_count}.
    rep_profiles: list of dicts with rep_name, avg_risk, deal_count.
    Returns a plain-text paragraph string, or None on failure.
    """
    prompt_template = _load_prompt("strategic_insight")
    if not prompt_template:
        return None

    signal_lines = "\n".join(f"- {k}: {v} deals" for k, v in signal_counts.items())
    rep_lines = "\n".join(
        f"- {r['rep_name']}: avg risk {r['avg_risk']:.0f}/100, {r['deal_count']} open deals"
        for r in rep_profiles
    )

    prompt = (
        prompt_template
        .replace("{signal_counts}", signal_lines or "No signal data available.")
        .replace("{rep_profiles}", rep_lines or "No rep data available.")
    )

    return _complete(prompt, model, max_tokens=300)
