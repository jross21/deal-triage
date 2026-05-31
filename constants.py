"""Shared constants — single source of truth for stages, thresholds, and tiers.

Imported across app.py, scoring.py, analytics.py, and the views so that risk
definitions stay consistent. Previously these were redefined in five files and
the "high risk" cutoff disagreed between the Manager View (60) and everywhere
else (70).
"""

# Open pipeline stages — Closed Won/Lost are excluded from scoring.
OPEN_STAGES = {"Discovery", "Demo", "Proposal", "Negotiation"}

# Fallback per-stage day thresholds, used until a stage has enough deals to
# compute its own median (see MIN_BENCHMARK_SAMPLE).
STAGE_THRESHOLDS = {"Discovery": 14, "Demo": 14, "Proposal": 21, "Negotiation": 21}

# Minimum deals in a stage before its computed median overrides the default.
MIN_BENCHMARK_SAMPLE = 5

# Number of top at-risk deals surfaced for Claude analysis.
TOP_N = 10

# Composite risk-score tier cutoffs (0–100).
HIGH_RISK_THRESHOLD = 70
MEDIUM_RISK_THRESHOLD = 40
