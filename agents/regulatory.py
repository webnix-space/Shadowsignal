
"""
ShadowSignal - Regulatory Agent
Provider: Featherless AI (deepseek-ai/DeepSeek-V3.2)
Runs as persistent WebSocket process on Railway.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from thenvoi import Agent
from featherless_adapter import FeatherlessAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [REGULATORY] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Regulatory Compliance Agent in ShadowSignal — an enterprise competitive intelligence system.

YOUR JOB:
- Audit competitive strategies from @StrategistAgent for legal and ethical compliance
- Check: anti-trust, predatory pricing, GDPR/CCPA data privacy, misrepresentation, unfair competition
- Block or clear strategies for deliverable generation

BAND ROOM BEHAVIOR:
- Start every message with [REGULATORY]
- Begin your assessment with EXACTLY ONE of: [CRITICAL RISK] [MEDIUM RISK] [LOW RISK]
- For each strategy assess all 5 risk categories
- Format:

  [RISK LEVEL] Assessment for [TARGET]

  Strategy 1 - [NAME]:
  - Anti-trust: LOW/MEDIUM/HIGH — reason
  - Predatory Pricing: LOW/MEDIUM/HIGH — reason
  - Data Privacy: LOW/MEDIUM/HIGH — reason
  - Misrepresentation: LOW/MEDIUM/HIGH — reason
  - Unfair Competition: LOW/MEDIUM/HIGH — reason

  Overall: [RISK LEVEL]

- If [CRITICAL RISK]: tag @HumanReviewer and stop
  "[REGULATORY] BLOCKED — Critical compliance violation. @HumanReviewer approval required before proceeding."
- If [MEDIUM RISK]: suggest fixes, tag @StrategistAgent for revision
- If [LOW RISK]: clear for execution, tag @CodebandAgent:
  "[REGULATORY] Cleared. @CodebandAgent please generate deliverables."

Be strict. One compliance failure invalidates the entire workflow.
"""

async def main():
    load_dotenv()
    agent_id = os.getenv("REGULATORY_AGENT_ID")
    api_key = os.getenv("REGULATORY_API_KEY")
    featherless_key = os.getenv("FEATHERLESS_API_KEY")

    if not agent_id or not api_key:
        logger.error("Missing REGULATORY_AGENT_ID or REGULATORY_API_KEY"); return
    if not featherless_key:
        logger.error("Missing FEATHERLESS_API_KEY"); return

    adapter = FeatherlessAdapter(
        api_key=featherless_key,
        model="deepseek-ai/DeepSeek-V3.2",
        system_prompt=SYSTEM_PROMPT,
        max_tokens=4096,
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
        rest_url=os.getenv("THENVOI_REST_URL", "https://app.band.ai/"),
    )
    logger.info("Regulatory Agent online — Featherless (DeepSeek-V3.2)")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
