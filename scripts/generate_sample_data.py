#!/usr/bin/env python3
"""Generate reproducible synthetic sample data for deal-triage.

Run from the deal-triage project root:
    python3 scripts/generate_sample_data.py

Outputs:
    data/sample/opportunities.csv          — 100-row deal CSV
    data/sample/transcripts/*.txt          — 15 call transcript snippets
"""

import csv
import math
import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
TODAY = date(2026, 5, 24)

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "sample"
TRANSCRIPT_DIR = OUT_DIR / "transcripts"

CSV_FIELDS = [
    "deal_id", "account_name", "stage", "amount", "close_date",
    "days_in_stage", "last_activity_date", "next_step", "owner",
    "industry", "employee_count",
]

# ---------------------------------------------------------------------------
# Name / value pools
# ---------------------------------------------------------------------------
_PREFIXES = [
    "Apex", "Vanta", "Prism", "Nexus", "Forge", "Lattice", "Kova", "Stratum",
    "Cipher", "Pylon", "Relay", "Mosaic", "Axiom", "Cobalt", "Meridian", "Vertex",
    "Dune", "Orca", "Fable", "Helix", "Quorum", "Nimbus", "Drift", "Ardent",
    "Ember", "Flint", "Onyx", "Parcel", "Revel", "Seraph", "Sable", "Tidal",
    "Umbra", "Vesper", "Wren", "Zinc", "Torque", "Sequin", "Raft", "Quillen",
    "Crest", "Basalt", "Cerulean", "Dusk", "Fulcrum", "Glyph", "Harbor",
    "Indigo", "Jasper", "Kelvin",
]

_SUFFIXES = [
    "Systems", "Technologies", "Solutions", "Labs", "Works", "Analytics",
    "Platforms", "Networks", "Dynamics", "Ventures", "Capital", "Group",
    "Partners", "Services", "Cloud", "Data", "AI", "Robotics", "Media",
    "Health", "Commerce", "Fintech", "Software", "Digital", "Ops",
]

_INDUSTRIES = [
    "FinTech", "HealthTech", "HR Tech", "MarTech", "EdTech",
    "Retail Tech", "Logistics", "Manufacturing", "Cybersecurity", "PropTech",
]

_OWNERS = [
    "Jordan Avery", "Sam Chu", "Morgan Ellis",
    "Riley Osei", "Casey Park", "Alex Tremblay",
]

_HEALTHY_NEXT_STEPS = [
    "Send procurement contract",
    "Schedule technical deep-dive with IT team",
    "Deliver ROI analysis to CFO",
    "Legal review kickoff — send MSA",
    "Book executive sponsor alignment call",
    "Share implementation timeline with champion",
    "Complete security questionnaire",
    "Finalize SLA terms and send redline",
]

_AMBIGUOUS_NEXT_STEPS = [
    "Follow up on proposal",
    "Check in after internal review",
    "Wait for budget approval",
    "Reconnect in two weeks",
]

_ATRISK_NEXT_STEPS = ["Follow up", "TBD", "", "Check in", "Reconnect next week", ""]

# Per-stage tier pools — guarantees transcript targets exist regardless of shuffle.
# Totals: 42 healthy, 14 at_risk, 14 ambiguous across 70 open deals.
_STAGE_TIER_POOLS = {
    "Discovery":   ["healthy"] * 12 + ["at_risk"] * 4 + ["ambiguous"] * 4,
    "Demo":        ["healthy"] * 12 + ["at_risk"] * 4 + ["ambiguous"] * 4,
    "Proposal":    ["healthy"] * 10 + ["at_risk"] * 4 + ["ambiguous"] * 4,
    "Negotiation": ["healthy"] * 8  + ["at_risk"] * 2 + ["ambiguous"] * 2,
}

# ---------------------------------------------------------------------------
# Deal generation helpers
# ---------------------------------------------------------------------------

def _deal_size():
    """Lognormal distribution clipped to [$10K, $500K], rounded to $5K."""
    while True:
        v = math.exp(random.gauss(10.8, 0.9))
        if 10_000 <= v <= 500_000:
            return round(v / 5_000) * 5_000


def _employee_count():
    tier = random.choices(["smb", "mid", "ent"], weights=[40, 40, 20])[0]
    ranges = {"smb": (50, 200), "mid": (201, 1_000), "ent": (1_001, 10_000)}
    lo, hi = ranges[tier]
    return random.randint(lo, hi)


def _make_deal(idx, account_name, stage, tier):
    owner = random.choice(_OWNERS)
    industry = random.choice(_INDUSTRIES)
    emp = _employee_count()
    amount = _deal_size()

    if tier == "at_risk":
        days_in = random.randint(36, 90)
        act_ago = random.randint(22, 60)
        close_off = random.randint(-30, 14)
        nxt = random.choice(_ATRISK_NEXT_STEPS)
    elif tier == "healthy":
        days_in = random.randint(1, 11)
        act_ago = random.randint(0, 6)
        close_off = random.randint(21, 84)
        nxt = random.choice(_HEALTHY_NEXT_STEPS)
    elif tier == "ambiguous":
        days_in = random.randint(14, 35)
        act_ago = random.randint(7, 20)
        close_off = random.randint(7, 28)
        nxt = random.choice(_AMBIGUOUS_NEXT_STEPS)
    elif tier == "closed_won":
        days_in = random.randint(5, 60)
        act_ago = random.randint(5, 90)
        close_off = random.randint(-60, -1)
        nxt = "Kickoff scheduled"
    else:  # closed_lost
        days_in = random.randint(5, 60)
        act_ago = random.randint(10, 90)
        close_off = random.randint(-90, -10)
        nxt = ""

    return {
        "deal_id": f"DEAL-{idx + 1:04d}",
        "account_name": account_name,
        "stage": stage,
        "amount": amount,
        "close_date": (TODAY + timedelta(days=close_off)).isoformat(),
        "days_in_stage": days_in,
        "last_activity_date": (TODAY - timedelta(days=act_ago)).isoformat(),
        "next_step": nxt,
        "owner": owner,
        "industry": industry,
        "employee_count": emp,
        "_tier": tier,  # internal only — excluded from CSV
    }


def generate_deals():
    """Return 100 deal dicts. Reproducible with SEED=42."""
    random.seed(SEED)

    pairs = [(p, s) for p in _PREFIXES for s in _SUFFIXES]
    random.shuffle(pairs)
    accounts = [f"{p} {s}" for p, s in pairs[:100]]

    stages = (
        ["Discovery"] * 20 + ["Demo"] * 20 + ["Proposal"] * 18
        + ["Negotiation"] * 12 + ["Closed Won"] * 15 + ["Closed Lost"] * 15
    )
    random.shuffle(stages)

    tier_pools = {s: list(tiers) for s, tiers in _STAGE_TIER_POOLS.items()}
    for pool in tier_pools.values():
        random.shuffle(pool)
    stage_idx = defaultdict(int)

    def _next_tier(stage):
        if stage == "Closed Won":
            return "closed_won"
        if stage == "Closed Lost":
            return "closed_lost"
        i = stage_idx[stage]
        stage_idx[stage] += 1
        return tier_pools[stage][i]

    return [_make_deal(i, acc, st, _next_tier(st)) for i, (acc, st) in enumerate(zip(accounts, stages))]


# ---------------------------------------------------------------------------
# Transcript specs
# Each entry targets a deal by (tier, stage, idx-within-group).
# Body templates accept {ae_name} and {account_name} substitution.
# ---------------------------------------------------------------------------

_TRANSCRIPTS = [
    # 1 — Buying signal: strong / healthy Discovery
    {
        "tier": "healthy", "stage": "Discovery", "idx": 0,
        "call_date": "2026-04-08",
        "prospect": ("Sarah Okonkwo", "VP of Revenue Operations"),
        "body": """\
{ae_name}: Thanks for making time today. I wanted to check in after you had a chance to review the overview doc.

Sarah Okonkwo: Honestly, this is exactly what we've been looking for. The pipeline scoring piece — I've been doing that manually in a spreadsheet and it takes my team half a day every week. The fact that you're pulling in activity signals automatically is a game-changer for us.

{ae_name}: Is this something you'd want to bring in before your Q3 planning cycle?

Sarah Okonkwo: A hundred percent. I talked to our CRO about it last night and he said, and I'm quoting here, "if it does what you say it does, just do it." I need to loop in our IT team on the Gong integration — do you have a security overview doc I can share with them?

{ae_name}: Absolutely, I'll send that over today. And I can set up a thirty-minute call with our solutions engineer if that would help move things along faster.

Sarah Okonkwo: Yes, let me pull in our head of IT and we can find a time next week. I also want to make sure procurement gets looped in early — what's the typical contract length?

{ae_name}: Standard is annual with an option for multi-year at a slight discount. I can include a few scenarios in the proposal so your team has options to bring to finance.

Sarah Okonkwo: Perfect. Send the security doc, the proposal scenarios, and let's book that IT call. I want to have something in front of my boss before the end of the month.""",
    },

    # 2 — Buying signal: strong / healthy Demo
    {
        "tier": "healthy", "stage": "Demo", "idx": 0,
        "call_date": "2026-04-15",
        "prospect": ("Marcus Delgado", "Director of Sales Operations"),
        "body": """\
{ae_name}: Now that you've seen the deal scoring dashboard live — what's your reaction?

Marcus Delgado: I love it. The visual is clean, but what I really care about is the reasoning underneath. When you showed how it weighs days-in-stage against the close date, that's exactly the kind of thing my team argues about in our Monday pipeline reviews.

{ae_name}: Does your VP have visibility into that review process?

Marcus Delgado: She does. I already forwarded her the recording from our first call. She watched it and her note to me was "get this done." So I have full sponsorship at the VP level — I just need to get our head of sales ops aligned, and I think she'll be easy once she sees the Salesforce integration.

{ae_name}: Want to pull her into a follow-up session?

Marcus Delgado: Yeah, let me set that up for next week. I also want to run this by our RevOps analyst — she's the one who'd actually own the day-to-day — and I suspect she'll have opinions about the field mapping. Can we get a sandbox to play with?

{ae_name}: I'll provision a trial environment with your Salesforce schema today. You'll have it by EOD.

Marcus Delgado: That's perfect. Honestly, at this point the question for us is implementation timing, not whether we're doing this. I want to be live before our big sales kickoff in August.""",
    },

    # 3 — Buying signal: moderate / healthy Proposal
    {
        "tier": "healthy", "stage": "Proposal", "idx": 0,
        "call_date": "2026-05-02",
        "prospect": ("Priya Sharma", "Head of Revenue Operations"),
        "body": """\
{ae_name}: I sent over the proposal last Thursday. Had a chance to look through it?

Priya Sharma: I did, and overall it looks solid. The pricing is in the range we expected. I have a few questions before I take it to my manager — mainly around the SLA section.

{ae_name}: Sure, what's on your mind?

Priya Sharma: The 99.5% uptime commitment — is that measured monthly or annually? And what does the remediation look like if you miss it? We're in HealthTech, so our compliance team will ask about data residency and incident response times.

{ae_name}: Monthly measurement, and the remediation is a service credit prorated to the downtime. For data residency, we're SOC 2 Type II certified and our data stays in US regions by default — I can get you the full compliance package.

Priya Sharma: That's helpful. The other thing is implementation — the proposal mentions a four-week onboarding. Is there a faster path if we're willing to do more of the legwork ourselves?

{ae_name}: We can usually get customers to first value in two weeks if you have a dedicated internal project contact. I can structure the proposal to offer both timelines so your team can choose.

Priya Sharma: I like that. One more thing — do you have any customers in our space I could talk to? A reference call would go a long way with my manager.

{ae_name}: I'll line up two references this week.""",
    },

    # 4 — Buying signal: strong / healthy Negotiation
    {
        "tier": "healthy", "stage": "Negotiation", "idx": 0,
        "call_date": "2026-05-10",
        "prospect": ("David Chen", "VP of Sales"),
        "body": """\
{ae_name}: Where are we on the legal redline? Our team sent the MSA back two weeks ago.

David Chen: Legal just finished their review this morning. They have three comments — two are minor, and one is around the liability cap that they want to discuss.

{ae_name}: Happy to get our legal teams on a call. What cap are they proposing?

David Chen: They want it at 2x annual contract value rather than 1x. I told them it's standard in SaaS and to pick their battles.

{ae_name}: We see 2x come up occasionally. There's flexibility if we're doing a multi-year term.

David Chen: We're planning on three years, so that should help. Look, I want to be transparent with you — I've already gone to my CFO with a "we're doing this" recommendation. Legal is the last gate. If we can clear this, I'm ready to sign. What's the fastest way to get a call on the calendar with both legal teams?

{ae_name}: I'll send a calendar invite within the hour for later this week.

David Chen: Perfect. And can you send me a clean order form with the three-year pricing so I have something to show my CFO while legal wraps up? I want to keep the momentum going.

{ae_name}: Sending both right now.""",
    },

    # 5 — Price objection / at-risk Proposal
    {
        "tier": "at_risk", "stage": "Proposal", "idx": 0,
        "call_date": "2026-04-20",
        "prospect": ("Kenji Watanabe", "RevOps Manager"),
        "body": """\
{ae_name}: Did you and your CFO have a chance to review the proposal?

Kenji Watanabe: We did. I want to be direct with you — the CFO's reaction was that the price is too high. He compared it to what we're paying for our current stack and said we need to come down by at least twenty percent to make this work.

{ae_name}: I appreciate you being straight with me. Can you help me understand what he's benchmarking against?

Kenji Watanabe: He pulled up a couple of alternatives online. I don't think he looked deeply at them, but the number he had in his head was significantly lower than what you quoted. I believe in the product — I've been your champion internally — but I can't take a proposal to finance at this price without a fight.

{ae_name}: Is this a budget ceiling issue or a perception-of-value issue? Because those require different conversations.

Kenji Watanabe: Both, honestly. The budget is real — we're in a hiring freeze and every purchase over a certain threshold requires CFO signature. But it's also partly perception. If I could show him a clear ROI case, I think he'd be more open.

{ae_name}: Let me put together a detailed ROI model based on your current pipeline volume and show what the efficiency gain is worth in recovered revenue. Would that help?

Kenji Watanabe: It might. But I'd need it by Friday — he's reviewing all Q2 software spend next week and if we miss that window, this goes to Q3.""",
    },

    # 6 — Timing objection / at-risk Negotiation
    {
        "tier": "at_risk", "stage": "Negotiation", "idx": 0,
        "call_date": "2026-05-14",
        "prospect": ("Lisa Ferreira", "VP of Operations"),
        "body": """\
{ae_name}: I've been trying to reach you this week — glad we could finally connect. Where are we with the contract?

Lisa Ferreira: I'm sorry I've been radio silent. I have some bad news. Finance just put a freeze on all new software commitments over twenty-five thousand dollars until July first. It's company-wide — nothing to do with you or the product. We were literally a week away from signing.

{ae_name}: I'm sorry to hear that. Is this a hard stop, or is there any path to an exception?

Lisa Ferreira: I tried. I went to my CFO directly and she said no exceptions. She's under pressure from the board to tighten up Q2 spend.

{ae_name}: Do you see this moving in Q3?

Lisa Ferreira: That's my expectation. Our next planning cycle starts in June for a July budget refresh. I want to make sure we stay at the top of the list — can you hold the pricing?

{ae_name}: Let me see what I can do. Can we put a tentative kickoff date in Q3 on the calendar to hold the intent, even if it's not binding?

Lisa Ferreira: That's a good idea. Let's say August first as a target. I'll document that internally so it's on record. I genuinely want to do this — I just need the clock to tick.""",
    },

    # 7 — Price + timing combined / ambiguous Proposal
    {
        "tier": "ambiguous", "stage": "Proposal", "idx": 0,
        "call_date": "2026-05-05",
        "prospect": ("Tom Whitfield", "Director of Revenue"),
        "body": """\
{ae_name}: Thanks for making time. I wanted to follow up on the proposal I sent last week.

Tom Whitfield: Yeah, I've been meaning to get back to you. A few things came up. First, the pricing — we're evaluating a few options right now and yours is on the higher end. I'm not saying it's a dealbreaker, but I need to justify the delta to my management team, and right now the ROI story isn't fully baked.

{ae_name}: What would make the ROI story stronger for your team?

Tom Whitfield: Honestly, a concrete number. We lose deals, but I don't have a precise figure on how much of that is pipeline visibility versus rep execution. If I could show that your product would've caught, say, five percent more slipping deals, that's real money.

{ae_name}: I can work with you to model that. What's your current average deal size and close rate by stage?

Tom Whitfield: I can probably dig that up. The other issue is timing — we're heading into a product launch in Q2 and my team is going to be stretched thin. Onboarding something new right now feels risky.

{ae_name}: What if we pushed the implementation start to after the launch? We could sign now, lock in current pricing, and start onboarding in Q3.

Tom Whitfield: Maybe. Let me think about it. I need to make sure I'm not agreeing to something my team can't actually absorb. Can you send me a revised timeline that starts in July?""",
    },

    # 8 — Price objection: build vs. buy / at-risk Demo
    {
        "tier": "at_risk", "stage": "Demo", "idx": 0,
        "call_date": "2026-04-28",
        "prospect": ("Mira Kovacs", "Head of Sales Strategy"),
        "body": """\
{ae_name}: Thanks for the demo time. What were your thoughts after seeing the product?

Mira Kovacs: Honestly, the product is well-built and the UX is clean. My concern is I took it to our engineering team and they pushed back pretty hard. Their position is that we could build something like this internally in about six weeks.

{ae_name}: What would they scope in?

Mira Kovacs: Basic scoring logic on CRM fields, a simple dashboard, maybe some automated alerts. They're not planning to do the natural language explanations part — our CTO thinks that's a nice-to-have.

{ae_name}: So if their build takes six weeks and costs the equivalent of two to three months of engineer time — does that compare favorably to an annual subscription?

Mira Kovacs: On paper, yes. But I'm skeptical of the timeline. We've had "six-week internal projects" that turned into eight-month projects. The real question my team is asking is whether your product does things we genuinely couldn't replicate.

{ae_name}: The integrations take months to get right — Gong, HubSpot, pipeline stage history, data normalization. That's the part that usually breaks internal builds. I can walk your CTO through the architecture if that would help frame the comparison.

Mira Kovacs: That might be worth doing. I'm not ready to close the door on this. Can you send me a build-vs-buy comparison doc I could share internally?""",
    },

    # 9 — Champion problem: VP not sold / at-risk Negotiation
    {
        "tier": "at_risk", "stage": "Negotiation", "idx": 1,
        "call_date": "2026-05-12",
        "prospect": ("Raj Anand", "Senior Director of Revenue"),
        "body": """\
{ae_name}: We've had a few missed connections — glad we could get on the calendar. Where are we internally?

Raj Anand: Look, I'm going to be honest with you. My VP pulled me into a meeting last week and basically said she's not sold. She wants to run a more formal evaluation process, which means bringing in two other vendors for demos.

{ae_name}: That's frustrating, especially at this stage. Is there context on what triggered this?

Raj Anand: There's a new SVP of Sales who started last month and he has strong opinions about the tools the sales team uses. He hadn't been in the loop on this evaluation and when he found out we were close to signing, he pumped the brakes. He wants to do his own due diligence.

{ae_name}: Has he articulated what he needs to see to be comfortable?

Raj Anand: Not clearly. I think he just wants to feel like he was part of the decision. I suggested setting up an exec briefing where you could walk him through the product directly — would you be willing to do that?

{ae_name}: Absolutely. Happy to come onsite if that's what it takes. What's his availability like?

Raj Anand: Let me check. He's a busy guy. I'll be honest — I'm not sure what his timeline pressure is. He might just slow this down. I'm still your advocate internally, but you should know the path to close just got longer.

{ae_name}: I appreciate you being direct. Let's get that briefing on the calendar and I'll bring our VP of Sales.""",
    },

    # 10 — Champion problem: boss wants competition / ambiguous Proposal
    {
        "tier": "ambiguous", "stage": "Proposal", "idx": 1,
        "call_date": "2026-05-07",
        "prospect": ("Claire Hutchinson", "Revenue Operations Lead"),
        "body": """\
{ae_name}: Following up on the proposal I sent. Any initial reactions?

Claire Hutchinson: So the proposal looks good on paper. I was actually excited about it. But then I showed it to my manager and she basically said she wants to see what else is out there before we commit.

{ae_name}: Did she say who she wants to evaluate?

Claire Hutchinson: She mentioned a couple of names. Nothing specific, she just doesn't want to feel like we jumped to the first vendor. Which is fair, I guess. I've seen this before — when she says she wants to "look at alternatives," sometimes that turns into a real process and sometimes she gets busy and we just come back to the original.

{ae_name}: What would make it easier for you to move forward?

Claire Hutchinson: Honestly, if I could show her some strong customer references — someone in our industry that we could actually call — that would go a long way. She trusts peer validation more than vendor decks.

{ae_name}: I can get you two reference customers in the same space. Would HR Tech or FinTech be more useful for her?

Claire Hutchinson: HR Tech would be perfect. We're in HR Tech and she'd find it credible.

{ae_name}: I'll line those up this week. And if it would help, I'm happy to jump on a call with her directly — sometimes it's useful to hear answers to tough questions live rather than through a deck.

Claire Hutchinson: That might be worth it. Let me ask her.""",
    },

    # 11 — Champion going quiet / at-risk Proposal (voicemail + follow-up email)
    {
        "tier": "at_risk", "stage": "Proposal", "idx": 1,
        "call_date": "2026-04-24",
        "prospect": None,
        "body": """\
[Voicemail — {ae_name} to Derek Malone, RevOps Director at {account_name}]

Hey Derek, this is {ae_name} calling for you. Just following up on the proposal I sent over about three weeks ago. I know you mentioned things were moving fast internally and you wanted to bring it to your director. Would love to hear where you landed.

If the timing has shifted or if there's anything I can do to help make the business case stronger, I'm happy to do that. Give me a call back when you get a chance, or shoot me an email and we can go from there. I'll also send a quick note with a summary of next steps so you have it in writing. Talk soon.

---

[Follow-up email — two weeks later, same deal]

Hi Derek,

Wanted to follow up on my voicemail. I realize your Q2 planning process may have shifted priorities around. A few things that might be useful:

1. Attached is a one-page ROI summary you can share internally without setting up a full demo.
2. I can make the contract start date flexible — we can sign now but push the implementation start by 30 days if that gives your team breathing room.
3. I have two reference customers in your space who are willing to do 20-minute calls on short notice.

No pressure — just want to make sure you have what you need to move forward when the time is right.

Best,
{ae_name}""",
    },

    # 12 — Competitor: Salesforce / ambiguous Negotiation
    {
        "tier": "ambiguous", "stage": "Negotiation", "idx": 0,
        "call_date": "2026-05-15",
        "prospect": ("Nathan Becker", "VP of Revenue"),
        "body": """\
{ae_name}: Where are we on the final decision? Last time we spoke, you said you were close.

Nathan Becker: We are close. But I have to tell you — Salesforce came back with a revised proposal last week. They're bundling their pipeline intelligence tool as part of our existing CRM renewal, which makes the pricing conversation very different.

{ae_name}: What's the bundle discount they're offering?

Nathan Becker: It's hard to compare because it's embedded in the platform renewal. My CFO's perspective is that it feels "free" since we're already paying for Salesforce. Which isn't really true, but that's how it reads on paper.

{ae_name}: Are their capabilities comparable to what I showed you?

Nathan Becker: Honestly, no. The Salesforce version is much more basic — no natural language explanations, no transcript integration, weaker heuristic logic. But my CFO doesn't care about those differences. He sees it as "good enough."

{ae_name}: What would it take to justify the additional spend internally?

Nathan Becker: I need to quantify the value gap. If I can show that your product would recover even two or three deals per quarter that their version would miss, that's a compelling ROI story. Can you help me build that case?

{ae_name}: Absolutely. Send me your average deal size and I'll model it out. I can also put together a direct feature comparison doc you can use internally.

Nathan Becker: Do that. I want to fight for this, but I need ammunition.""",
    },

    # 13 — Competitor: HubSpot / at-risk Demo
    {
        "tier": "at_risk", "stage": "Demo", "idx": 1,
        "call_date": "2026-05-01",
        "prospect": ("Alicia Torres", "Head of Operations"),
        "body": """\
{ae_name}: Before we dive into the demo — you mentioned on our last call that you'd looked at HubSpot. What was your take?

Alicia Torres: Their demo was actually pretty impressive. And the pricing came in under our budget ceiling, which matters.

{ae_name}: What stood out to you feature-wise?

Alicia Torres: The native CRM integration is seamless, which makes sense. And their deal health score is built right into the pipeline view — there's no separate dashboard to check. For my team, that's important because we're not going to log into another tool.

{ae_name}: How did their AI-generated explanations compare?

Alicia Torres: Honestly, they didn't show us that feature. I'm not sure if it exists at the same depth. What they focused on was workflow automation — when a deal goes at-risk, it automatically creates a task and notifies the AE.

{ae_name}: That's a feature we have as well — I should have led with that. Let me show you our integration layer. We sit on top of HubSpot natively, so you'd keep your current workflow and just add the intelligence layer on top.

Alicia Torres: That's actually news to me. If you integrate with HubSpot rather than replace it, that's a different conversation. Can you show me that specifically?

{ae_name}: Yes — pulling it up right now. I think this changes the picture significantly.

Alicia Torres: Maybe. I'm still evaluating, but I'm open.""",
    },

    # 14 — Competitor: custom build / healthy Proposal (CTO questions)
    {
        "tier": "healthy", "stage": "Proposal", "idx": 1,
        "call_date": "2026-05-08",
        "prospect": ("Yuki Nakamura", "Chief Revenue Officer"),
        "body": """\
{ae_name}: I know your CTO was going to weigh in on the proposal. Did you hear back from him?

Yuki Nakamura: I did. He's cautiously supportive, but he had a bunch of technical questions. His main thing is that he always prefers API access to a closed product. He said — and I'm paraphrasing — "before we buy a black box, I want to know we couldn't build this ourselves in a reasonable amount of time."

{ae_name}: That's a fair question. What's his team's bandwidth for a build right now?

Yuki Nakamura: Limited. They're in the middle of a platform migration and have capacity for maybe fifteen to twenty percent time on tooling projects. But he's still asking the question.

{ae_name}: We actually have a well-documented API and webhook layer. Some customers use us as a data layer and build their own front-end on top. Would it help if I set up a technical call so your CTO can ask questions directly?

Yuki Nakamura: Yeah, he'd probably love that actually. He's not trying to block the purchase — he just wants to understand the architecture.

{ae_name}: Happy to do it. I'll have our lead engineer on the call. What's the best time?

Yuki Nakamura: Next Tuesday afternoon works. Can you send over API documentation beforehand so he can come with specific questions?

{ae_name}: Already on it. I'll send a technical overview, the API reference, and a few examples of how customers have extended the platform.

Yuki Nakamura: Perfect. I think once he's satisfied, we're on track to close before end of quarter.""",
    },

    # 15 — Neutral status update / healthy Discovery
    {
        "tier": "healthy", "stage": "Discovery", "idx": 1,
        "call_date": "2026-04-22",
        "prospect": ("Brendan Walsh", "RevOps Manager"),
        "body": """\
{ae_name}: Hey, just a quick sync — I know we left last week's call with a few action items. Wanted to make sure we're both on the same page.

Brendan Walsh: Yeah, this is a good check-in. I went back to my team and shared the overview you sent. The feedback was pretty positive — people liked the concept. No major objections yet.

{ae_name}: That's good to hear. Did anyone have questions I should address?

Brendan Walsh: One of my ops analysts asked about the data model — specifically how it handles deals that have been re-staged retroactively in the CRM. Like if someone goes back and changes a close date after the fact, does that distort the scoring?

{ae_name}: Good catch — we handle that with event-log-based tracking rather than point-in-time snapshots. So retroactive edits don't corrupt the historical risk signal. I can send a technical note on that.

Brendan Walsh: That would be useful, yeah. Otherwise, I'm still working on scheduling time with our head of sales. He's been traveling. I'm targeting next week or the week after.

{ae_name}: No rush. Anything I can send that would make that intro conversation more productive?

Brendan Walsh: Maybe a one-pager — something short that explains the problem you solve before getting into features. He responds better to problem statements than product decks.

{ae_name}: I'll tailor something to that framing and send it over today.

Brendan Walsh: Perfect. Let's plan to reconnect once I've got him lined up. Should be within two weeks.""",
    },
]


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_csv(deals):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "opportunities.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deals)
    return path


def generate_transcripts(deals):
    groups = defaultdict(list)
    for deal in deals:
        groups[(deal["_tier"], deal["stage"])].append(deal)

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    for spec in _TRANSCRIPTS:
        deal = groups[(spec["tier"], spec["stage"])][spec["idx"]]
        ae = deal["owner"]
        acct = deal["account_name"]

        if spec["prospect"]:
            pname, ptitle = spec["prospect"]
            header = (
                f"Call Date: {spec['call_date']}\n"
                f"Account: {acct}\n"
                f"Participants: {ae} (AE), {pname} — {ptitle}, {acct}\n"
            )
        else:
            header = (
                f"Date: {spec['call_date']}\n"
                f"Account: {acct}\n"
                f"Type: Outbound voicemail + follow-up email\n"
            )

        body = spec["body"].replace("{ae_name}", ae).replace("{account_name}", acct)
        filename = f"{deal['deal_id']}_{spec['call_date']}.txt"
        (TRANSCRIPT_DIR / filename).write_text(header + "\n" + body + "\n", encoding="utf-8")
        label = spec["prospect"][0] if spec["prospect"] else "voicemail"
        print(f"  {filename}  ({spec['tier']} / {spec['stage']} — {label})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Generating 100 deals (seed=42)...")
    deals = generate_deals()

    csv_path = write_csv(deals)
    print(f"Wrote {csv_path}  ({len(deals)} rows)\n")

    stage_counts = Counter(d["stage"] for d in deals)
    tier_counts = Counter(d["_tier"] for d in deals)
    open_stages = ["Discovery", "Demo", "Proposal", "Negotiation"]
    closed_stages = ["Closed Won", "Closed Lost"]
    print("Stage distribution:")
    for s in open_stages + closed_stages:
        print(f"  {s}: {stage_counts[s]}")
    print(f"\nRisk tiers (open deals):")
    for t in ("healthy", "ambiguous", "at_risk"):
        print(f"  {t}: {tier_counts[t]}")

    print(f"\nWriting {len(_TRANSCRIPTS)} transcripts to {TRANSCRIPT_DIR}...")
    generate_transcripts(deals)
    print(f"\nDone.")


if __name__ == "__main__":
    main()
