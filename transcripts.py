"""Call-transcript lookup.

Single helper replacing the duplicated glob logic previously in app.py
(find_transcript), views/rep_tools.py (_load_transcript, truncated to 2500),
and analytics.py (inline glob in compute_signal_counts).
"""

from pathlib import Path

TRANSCRIPT_DIR = Path("data/sample/transcripts")


def find_transcript(deal_id, max_chars: int | None = None, directory=None) -> str:
    """Return the transcript text for a deal, or "" if none exists.

    deal_id is coerced to str. When max_chars is set, the text is truncated
    (rep_tools historically used a 2500-char excerpt). directory overrides the
    default transcript folder (used by analytics for testability).
    """
    base = Path(directory) if directory is not None else TRANSCRIPT_DIR
    if not base.exists():
        return ""
    matches = list(base.glob(f"{deal_id}_*.txt"))
    if not matches:
        return ""
    text = matches[0].read_text(encoding="utf-8")
    return text[:max_chars] if max_chars else text
