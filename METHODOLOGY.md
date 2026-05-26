# Deal Risk Methodology

> **Note for teams using this in production:** This document uses demo-realistic placeholder values based on a synthetic 100-deal pipeline with 6 account executives across 10 industries. Stage medians, deal examples, and rep names are illustrative. Before deploying this tool for your team, update the stage benchmarks, deal examples, and organizational context to reflect your actual CRM data. The scoring weights and confidence thresholds are a starting point — tune them against your historical win/loss data.

---

## Why This Document Exists

Every sales team has a version of this knowledge locked inside the heads of the most experienced managers. They walk into a pipeline review and within 90 seconds they can tell you which deals are real and which ones are going to slip. They're reading a combination of signals that most CRM dashboards don't surface: time patterns, engagement gaps, the quality of a next step, and the subtext of a call transcript.

This tool encodes that judgment into a scoring model and gives it to Claude to augment with the kind of analysis a seasoned manager would offer in a one-on-one coaching session. This document explains how the model works, why each signal was chosen, what it misses, and how to adapt it to your team.

---

## 1. Why Deals Slip

Before building a risk model, it helps to understand the actual mechanics of deal slippage. In B2B SaaS, deals almost always slip for one of three reasons:

**Time.** The deal has been in the same stage too long. Every sales process has a natural rhythm — prospects move through Discovery and Demo relatively quickly when there's genuine interest, and slow down in Proposal and Negotiation when approvals get complex. When a deal lingers far beyond the team's historical median for its stage, it's a signal that something has stalled. The champion has gone quiet. The economic buyer hasn't engaged. The evaluation is dragging because there's no urgency to close.

**Engagement.** The last logged activity is old. This is one of the most reliable slip predictors in the data, and it's also one of the most ignored. A 21-day silence in a deal that was previously moving weekly is meaningful. It doesn't necessarily mean the deal is dead — sometimes prospects go dark before a budget cycle or a leadership change — but it means the AE has lost the thread, and the deal is drifting.

**Urgency.** The close date is past or imminent, but the deal hasn't progressed to match. A close date that's 8 days away on a deal still in Proposal stage is a red flag. Either the close date was never realistic (sandbagging or wishful thinking in the CRM), or the prospect's timeline has shifted and the AE hasn't updated the forecast accordingly. Either way, the close date pressure signals a mismatch between the forecast and reality.

These three signals — time, engagement, urgency — form the foundation of the scoring model.

---

## 2. Reading Stage Velocity

The stage stagnation score (up to 40 points) compares each deal's days in current stage against the team's historical median for that stage.

In this demo pipeline, the medians are:

| Stage | Median Days |
|-------|-------------|
| Discovery | 7 days |
| Demo | 9 days |
| Proposal | 14 days |
| Negotiation | 18 days |

These medians are computed dynamically from all deals in the uploaded CSV — both open and closed. This matters because it grounds the benchmark in your team's actual velocity rather than industry averages. A team that runs 45-day sales cycles will have very different stage medians than one running 14-day cycles, and the model adapts automatically.

The scoring is linear: a deal at the median scores 0 stage points. A deal at 2× the median scores 20 points. A deal at 4× the median scores the maximum 40 points. This avoids cliff effects where a deal jumps from 0 to maximum risk at a single threshold.

**What "too long" actually means:** In this sample pipeline, Harbor Systems (DEAL-0001) has been in Demo for 73 days against a 9-day median — 8.1× the benchmark. That's not a deal that's just taking its time. That's a deal where something fundamental has changed: the champion may have lost internal support, the evaluation may have expanded beyond the original scope, or the AE may have been avoiding a difficult conversation about stalled momentum.

**Deal size adjustment:** Large deals take longer. A $450K deal in Negotiation will naturally run longer than a $42K deal in the same stage. The current model doesn't adjust for deal size, which means it will flag enterprise deals as higher risk than they actually are. Teams with wide deal size variance should consider segmenting benchmarks by deal tier (e.g., separate medians for deals above and below $100K).

---

## 3. Activity Recency as a Trust Signal

The activity score (up to 30 points) measures days since the last logged activity — any call, email, meeting, or note recorded in the CRM.

| Days Since Last Activity | Points |
|--------------------------|--------|
| 0–6 days | 0–13 (linear) |
| 7–13 days | 14 |
| 14–20 days | 22 |
| 21+ days | 30 (maximum) |

Activity recency is a proxy for engagement momentum. A deal with daily activity is actively worked. A deal with 3 weeks of silence is drifting — and in competitive deals, drifting means losing.

**The nuance the score misses:** Not all silences are equal. There's a difference between an AE-led silence (the AE hasn't followed up, often because the deal is uncomfortable) and a prospect-led silence (the champion has gone quiet because of internal dynamics). The former is fixable with a proactive outreach. The latter is a signal that the internal champion may have lost budget, authority, or enthusiasm for the project.

Call transcripts often reveal which type of silence you're dealing with. In Precision Analytics (DEAL-0008), the champion explicitly mentioned that "our CFO wants to see the business case from IT before we move forward" — a classic approval chain delay, not AE disengagement. The score treats this the same as a neglected deal, but Claude's analysis surfaces the distinction.

**The 7-day threshold matters:** The linear scale from 0–6 days reflects normal deal cadence. Most active deals have some activity weekly. Deals that cross 7 days start showing early-stage drift. Deals beyond 14 days are materially at risk of losing momentum, and deals at 21+ days have almost certainly lost the thread of the last conversation.

---

## 4. Close Date Pressure

The close date score (up to 30 points) measures urgency based on how close or overdue the forecast date is.

| Close Date | Points |
|------------|--------|
| Past due | 30 |
| < 14 days away | 25 |
| 15–30 days | 15 |
| 31–60 days | 5 |
| 60+ days | 0 |

**Past-due deals aren't always dead.** A past-due close date is a signal that the forecast was wrong, not necessarily that the deal is lost. The most common scenarios: (1) the AE needs to have a direct conversation about updated timeline and get a new date, (2) the champion has been unable to get internal approval and needs a different approach, or (3) the deal is genuinely stuck and the AE needs a re-qualification conversation with the economic buyer.

The model assigns maximum close date pressure to past-due deals because the CRM data is unreliable until the date gets updated. The AE's first action on any past-due deal in the top 10 is to have a direct conversation about the revised timeline and update the forecast accordingly.

**The 30-day window is where most slippage happens.** Deals with 15–30 days to close are in the zone where forecast accuracy matters most. If the stage and activity signals are also elevated in this window, the deal needs immediate attention — not a gentle nudge but a direct executive sponsorship call or champion coaching session.

---

## 5. What the Heuristics Miss

The three-signal model is deliberately simple. It can be computed from any CRM export in seconds, and it surfaces the right deals for human review about 70–80% of the time. But it misses the signals that only appear in conversations:

**Champion health.** The most important single factor in B2B SaaS deals is whether your champion has organizational credibility and executive access. A champion who is mid-level, in a department with no budget authority, or who has recently changed roles is a fragile foundation regardless of how quickly the deal moves through stages. Transcripts often reveal this: champions who hedge on whether the CEO is "bought in," who mention that "legal will need to weigh in" as a surprise late in the process, or who start using passive voice about internal support ("there's some interest from the team") are showing cracks.

**Competitive dynamics.** Stage velocity and activity recency don't know if a competitor just entered the deal. A sudden slowdown in a previously fast-moving deal often coincides with a competitive evaluation that the prospect didn't disclose. Transcripts are the only place this surfaces in the data — and even then, prospects often obscure competitive conversations. When Claude's analysis flags a "build vs. buy tension" or a competitor mention in the quotes, it's worth treating as a high-priority signal even if the heuristic score is moderate.

**Political dynamics.** Deals that stall in Proposal or Negotiation often stall because of internal politics the AE can't see: a reorganization, a budget reforecast, a new executive who wants to evaluate the decision independently. These dynamics show up in transcripts as vague delays, sudden additions to the stakeholder list, or champions who become less available. The buying process analysis in Claude's High-confidence output is specifically designed to surface this.

---

## 6. How to Use Claude's Analysis

Claude's output is tiered by confidence to match the depth of analysis to the strength of available data.

**Low confidence** means the heuristic signals are mild or the data is thin. The brief is a focused 2–3 sentence summary with one concrete action. Don't over-index on Low-confidence analyses — they're flags, not verdicts. The main value is surfacing deals that might otherwise stay invisible until the quarter-end scramble.

**Medium confidence** means one or two real signals are present. The brief goes deeper and the risk signals list names the specific issues. These deals typically need one targeted intervention — usually a direct conversation that the analysis will describe specifically.

**High confidence** means multiple max signals are present AND a transcript provides direct evidence. This is where the tool delivers its highest value. The executive summary gives you the bottom line. The risk signals table connects each concern to specific data. The buying process analysis reads the subtext — what is actually happening in this account beneath the CRM records. The recommended actions are prioritized and sequenced, not a generic "follow up" directive.

The **quotes** section shows verbatim transcript excerpts that Claude identified as risk evidence. These are the specific moments in the conversation where the deal risk became visible. For an AE coaching session, these quotes are the foundation of the conversation: "In your last call, the prospect said X — what did you do with that?"

---

## 7. Customizing for Your Team

**Adjusting scoring weights:** The current weights (Stage 40 / Activity 30 / Close 30) reflect a philosophy that stage stagnation is the strongest leading indicator of slippage. If your team's data suggests activity recency is more predictive, increase its weight. Edit `compute_risk_breakdown()` in `app.py`. The three components should sum to 100.

**Recalibrating stage medians:** The model computes medians automatically from the uploaded CSV. If your historical data is thin (fewer than 5 deals per stage), the model falls back to hardcoded defaults in `STAGE_THRESHOLDS`. Update those defaults in `app.py` to match your team's typical cycle times. Adding more historical data to the CSV improves benchmark accuracy.

**Adjusting the High-risk threshold:** Deals scoring ≥ 70 are labeled "High" risk in the pipeline chart. If your team has a different tolerance for false positives, adjust `_risk_tier()` in `app.py`.

**Updating the prompt:** The most impactful customization is updating `prompts/deal_risk_explanation.md` to reflect your team's specific sales motion, product category, and common objection patterns. A prompt that mentions your specific competitors, your typical approval process, and your product's common evaluation criteria will produce sharper, more actionable analysis than a generic B2B SaaS prompt.

**Using feedback data:** Feedback is stored in `data/feedback/feedback.json`. After running the tool for a few weeks, look at whether High-confidence analyses are rated helpful more often than Low-confidence ones, and whether certain deal stages or industries consistently get negative ratings. This is the data you need to tune the prompt and scoring weights over time.
