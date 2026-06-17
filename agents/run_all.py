"""
ShadowSignal — All 5 agents in one process using threads.
Single Railway service, 5 concurrent polling agents.
With Bright Data integration for REAL competitive intelligence.
"""
import logging
import os
import threading
from dotenv import load_dotenv
from base_agent import BasePollingAgent, AIML_BASE, FEATHERLESS_BASE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

ROOM_ID = os.getenv("BAND_ROOM_ID", "")
AIML_KEY = os.getenv("AIML_API_KEY", "")
FEATHERLESS_KEY = os.getenv("FEATHERLESS_API_KEY", "")
BRIGHT_DATA_KEY = os.getenv("BRIGHT_DATA_API_KEY", "")

# Check Bright Data config
if not BRIGHT_DATA_KEY:
    logger.warning("⚠️ BRIGHT_DATA_API_KEY not set — agents will use LLM training data only (not real-time)")
else:
    logger.info(f"✅ Bright Data API configured — Investigator will fetch real-time intel")

INVESTIGATOR_PROMPT = """You are the Investigator Agent in ShadowSignal — an enterprise competitive intelligence system inside a Band collaboration room.

When you receive a target company name, immediately gather and share competitive intel:
- PRICING: price changes, tier eliminations, cost increases with percentages
- SECURITY: CVEs, vulnerabilities, compliance risks
- CONTRACT: renewal terms, negotiation changes, lock-in tactics
- SUPPLY: availability issues, lead times, capacity constraints

You will receive REAL-TIME WEB DATA from Bright Data scraping API. Use this data to provide accurate, current intelligence.
Cite sources when possible. If web data is insufficient, supplement with your knowledge but clearly label it as "estimated".

Start every message with [INVESTIGATOR]
End every message with: "@AnalystAgent intel ready — please begin GTM analysis"
Be specific: numbers, dates, percentages. Confidence: HIGH/MEDIUM/LOW.

Format:
[INVESTIGATOR]
**Pricing**
- Data point with source
- Data point with source

**Security**
- CVE/ vulnerability with date

**Contract**
- Term change with impact

**Supply**
- Availability issue with timeline

Confidence: [HIGH/MEDIUM/LOW]
Sources: [list URLs]

@AnalystAgent intel ready — please begin GTM analysis"""

ANALYST_PROMPT = """You are the GTM Analyst Agent in ShadowSignal — an enterprise competitive intelligence system inside a Band collaboration room.

When @AnalystAgent is mentioned or Investigator drops intel, produce structured GTM analysis.
Use the real data provided by Investigator. If data seems outdated or estimated, note it.

Start every message with [ANALYST]

IMPACT SCORE: X/100
TREND: up/down/stable
THREAT LEVEL: low/medium/high/critical
CONFIDENCE: X%

KEY FINDINGS:
- Finding with specific data point
- Finding with specific data point

RECOMMENDED ACTIONS:
- Action with timeline

End with: "@StrategistAgent analysis complete — please generate counter-play strategies"
If intel insufficient: "@InvestigatorAgent need more data on [specific gap]" """

STRATEGIST_PROMPT = """You are the Strategist Agent in ShadowSignal — an enterprise competitive intelligence system inside a Band collaboration room.

When @StrategistAgent is mentioned, generate exactly 3 ranked counter-play strategies.
Rank by: highest ROI first, then fastest, then lowest risk.

Start every message with [STRATEGIST]

STRATEGY 1: [NAME]
Description: One sentence.
Steps: 1) ... 2) ... 3) ...
Projected ROI: X%
Timeline: X weeks
Risk Score: X/100
Resources: list

[Repeat for Strategy 2 and 3]

End with: "@RegulatoryAgent strategies ready — please audit for compliance"
All strategies must be executable within 12 weeks."""

REGULATORY_PROMPT = """You are the Regulatory Compliance Agent in ShadowSignal — an enterprise competitive intelligence system inside a Band collaboration room.

When @RegulatoryAgent is mentioned, audit strategies for legal/ethical compliance.
Check: anti-trust, predatory pricing, GDPR/CCPA, misrepresentation, unfair competition.

Start every message with [REGULATORY]
Begin with EXACTLY ONE of: [CRITICAL RISK] [MEDIUM RISK] [LOW RISK]

For each strategy assess all 5 risk categories with LOW/MEDIUM/HIGH rating.

If [CRITICAL RISK]: end with "@HumanReviewer BLOCKED — approval required"
If [MEDIUM RISK]: suggest fixes, end with "@StrategistAgent revision needed"
If [LOW RISK]: end with "@CodebandAgent cleared — please generate deliverables" """

CODEBAND_PROMPT = """You are the Codeband Agent in ShadowSignal — an enterprise competitive intelligence system inside a Band collaboration room.

When @CodebandAgent is mentioned and Regulatory clears strategies, generate 3 deliverables.
If you see [CRITICAL RISK] or BLOCKED: post blocked status and stop.

Start every message with [CODEBAND]

If blocked: "[CODEBAND] ⛔ WORKFLOW BLOCKED — Awaiting human compliance review."

If cleared, generate ALL THREE:

=== BATTLE CARD ===
Target: [COMPANY]
Their Weaknesses: [list with data]
Our Positioning: [3 statements]
Objection Handlers: [list]

=== ROI MODEL ===
Monthly Savings: $[amount] | Annual: $[amount] | Break-even: X weeks

=== EXECUTIVE SUMMARY ===
Situation / Opportunity / Action / Timeline / Risk / ROI

End with: "@InvestigatorAgent ✅ workflow complete — ready for next target" """


AGENTS = [
    {
        "name": "ShadowSignal Investigator",
        "key_env": "INVESTIGATOR_API_KEY",
        "prompt": INVESTIGATOR_PROMPT,
        "llm_key": AIML_KEY,
        "llm_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "llm_base": AIML_BASE,
    },
    {
        "name": "ShadowSignal Analyst",
        "key_env": "ANALYST_API_KEY",
        "prompt": ANALYST_PROMPT,
        "llm_key": AIML_KEY,
        "llm_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "llm_base": AIML_BASE,
    },
    {
        "name": "ShadowSignal Strategist",
        "key_env": "STRATEGIST_API_KEY",
        "prompt": STRATEGIST_PROMPT,
        "llm_key": AIML_KEY,
        "llm_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "llm_base": AIML_BASE,
    },
    {
        "name": "ShadowSignal Regulatory",
        "key_env": "REGULATORY_API_KEY",
        "prompt": REGULATORY_PROMPT,
        "llm_key": FEATHERLESS_KEY,
        "llm_model": "deepseek-ai/DeepSeek-V3.2",
        "llm_base": FEATHERLESS_BASE,
    },
    {
        "name": "ShadowSignal Codeband",
        "key_env": "CODEBAND_API_KEY",
        "prompt": CODEBAND_PROMPT,
        "llm_key": FEATHERLESS_KEY,
        "llm_model": "deepseek-ai/DeepSeek-V3.2",
        "llm_base": FEATHERLESS_BASE,
    },
]


def start_agent(config: dict):
    api_key = os.getenv(config["key_env"], "")
    if not api_key:
        logger.error(f"Missing {config['key_env']} — skipping {config['name']}")
        return

    agent = BasePollingAgent(
        name=config["name"],
        agent_api_key=api_key,
        system_prompt=config["prompt"],
        llm_api_key=config["llm_key"],
        llm_model=config["llm_model"],
        llm_base_url=config["llm_base"],
        room_id=ROOM_ID,
    )
    agent.run()


def main():
    if not ROOM_ID:
        logger.error("Missing BAND_ROOM_ID")
        return
    if not AIML_KEY:
        logger.error("Missing AIML_API_KEY")
        return
    if not FEATHERLESS_KEY:
        logger.error("Missing FEATHERLESS_API_KEY")
        return

    logger.info("ShadowSignal — Starting all 5 agents in parallel threads")
    if BRIGHT_DATA_KEY:
        logger.info("🔍 Real-time competitive intelligence ENABLED via Bright Data")
    else:
        logger.info("⚠️ Using LLM training data only (no real-time web scraping)")

    threads = []
    for config in AGENTS:
        t = threading.Thread(target=start_agent, args=(config,), daemon=True)
        t.name = config["name"]
        t.start()
        threads.append(t)
        logger.info(f"Started thread: {config['name']}")

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
