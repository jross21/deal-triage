import json
import os
from pathlib import Path

from anthropic import Anthropic

PROMPT_DIR = Path("prompts")
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_FOLLOWUP_SYSTEM = (
    "You are a B2B SaaS account executive. "
    "Write a brief, direct follow-up email based on the deal context below. "
    "Format: Subject: <subject line>, then a blank line, then 3-4 sentences of body. "
    "No filler phrases like 'I hope this finds you well.' Sound human and specific to this deal."
)


def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


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
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

    prompt_template = _load_prompt("deal_risk_explanation")
    if not prompt_template:
        return None

    from datetime import date
    TODAY = date.today()

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

    prompt = (
        prompt_template
        .replace("{deal_data}", deal_data)
        .replace("{transcript_section}", transcript_section)
    )

    tier = _estimate_tier(row, bool(transcript))
    max_tokens = 1024 if tier == "High" else 512

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(text[start:end])
    except Exception:
        return None


def generate_followup_email(row: dict, analysis: dict, model: str = DEFAULT_MODEL) -> str | None:
    """Draft a follow-up email for the AE based on deal context and Claude analysis.

    Returns plain text with 'Subject: ...' on the first line, or None on failure.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

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

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=300,
            system=_FOLLOWUP_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None


def generate_pre_call_brief(
    row, transcript: str = "", model: str = DEFAULT_MODEL, existing_analysis: dict = None
) -> dict | None:
    """Generate a pre-call brief for a deal.

    Returns dict with keys: context, objections, agenda, questions.
    Returns None if API key missing or call fails.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

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

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(text[start:end])
    except Exception:
        return None


def generate_pipeline_review(rep_summaries: list, model: str = DEFAULT_MODEL) -> dict | None:
    """Generate a pipeline review meeting agenda.

    rep_summaries: list of dicts, each with keys: rep_name, deals (list of deal dicts).
    Returns dict with keys: pulse (str), reps (list of {rep_name, questions}).
    Returns None if API key missing or call fails.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

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

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(text[start:end])
    except Exception:
        return None


def generate_strategic_insight(
    signal_counts: dict, rep_profiles: list, model: str = DEFAULT_MODEL
) -> str | None:
    """Generate a plain-text strategic insight paragraph for the Leader Dashboard.

    signal_counts: dict of {signal_name: deal_count}.
    rep_profiles: list of dicts with rep_name, avg_risk, deal_count.
    Returns a plain-text paragraph string, or None on failure.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None

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

    try:
        client = Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None
