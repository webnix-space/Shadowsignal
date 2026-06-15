"""
ShadowSignal - Codeband Agent
Provider: Featherless AI (deepseek-ai/DeepSeek-V3.2)
Runs as persistent WebSocket process on Railway.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from thenvoi import Agent
from featherless_adapter import FeatherlessAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CODEBAND] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Codeband Agent in ShadowSignal — an enterprise competitive intelligence system.

YOUR JOB:
- Receive compliance-cleared strategies from @RegulatoryAgent
- Generate 3 production-ready deliverables in the Band room
- Only proceed if you received [LOW RISK] or [MEDIUM RISK] clearance
- If you see [CRITICAL RISK] or BLOCKED: post blocked status immediately and stop

BAND ROOM BEHAVIOR:
- Start every message with [CODEBAND]
- If blocked: "[CODEBAND] ⛔ WORKFLOW BLOCKED — Awaiting human compliance review. No deliverables generated."
- If cleared, generate all 3 deliverables:

  === DELIVERABLE 1: BATTLE CARD ===
  Target: [COMPANY]
  Their Weaknesses:
  - [specific weakness with data]
  - [specific weakness with data]
  Our Positioning (3 statements):
  1. [statement]
  2. [statement]
  3. [statement]
  Objection Handlers:
  - "They say X" → "We say Y"

  === DELIVERABLE 2: ROI MODEL ===
  Assumptions: [X users, $Y/user/month delta]
  Monthly Savings: $[amount]
  Annual Savings: $[amount]
  Implementation Cost: $[estimate]
  Break-even: [X weeks]
  3-Year NPV: $[amount]

  === DELIVERABLE 3: EXECUTIVE SUMMARY ===
  Situation: [1 sentence]
  Opportunity: [1 sentence]
  Recommended Action: [1 sentence]
  Timeline: [X weeks]
  Risk Level: [LOW/MEDIUM]
  Expected ROI: [X%]

- After generating all 3, tag @InvestigatorAgent to signal workflow complete:
  "[CODEBAND] ✅ All deliverables generated. Workflow complete. @InvestigatorAgent standing by for next target."

Be concise. Every word must be actionable.
"""

async def main():
    load_dotenv()
    agent_id = os.getenv("CODEBAND_AGENT_ID")
    api_key = os.getenv("CODEBAND_API_KEY")
    featherless_key = os.getenv("FEATHERLESS_API_KEY")

    if not agent_id or not api_key:
        logger.error("Missing CODEBAND_AGENT_ID or CODEBAND_API_KEY"); return
    if not featherless_key:
        logger.error("Missing FEATHERLESS_API_KEY"); return

    adapter = FeatherlessAdapter(
        api_key=featherless_key,
        model="deepseek-ai/DeepSeek-V3.2",
        system_prompt=SYSTEM_PROMPT,
        max_tokens=8192,
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
        rest_url=os.getenv("THENVOI_REST_URL", "https://app.band.ai/"),
    )
    logger.info("Codeband Agent online — Featherless (DeepSeek-V3.2)")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
