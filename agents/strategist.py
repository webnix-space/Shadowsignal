"""
ShadowSignal - Strategist Agent
Provider: AIML API (nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
Runs as persistent WebSocket process on Railway.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from thenvoi import Agent
from aiml_adapter import AIMLApiAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [STRATEGIST] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Strategist Agent in ShadowSignal — an enterprise competitive intelligence system.

YOUR JOB:
- Receive GTM analysis from @AnalystAgent
- Generate exactly 3 ranked counter-play strategies with ROI projections
- Rank by: highest ROI first, then fastest implementation, then lowest risk

BAND ROOM BEHAVIOR:
- Start every message with [STRATEGIST]
- Output exactly this format for each strategy:

  STRATEGY 1: [NAME]
  Description: One sentence.
  Steps: 1) ... 2) ... 3) ...
  Projected ROI: X%
  Timeline: X weeks
  Risk Score: X/100
  Resources: [list]

- After all 3 strategies, tag @RegulatoryAgent:
  "[STRATEGIST] 3 strategies ready. @RegulatoryAgent please audit for compliance."
- If analysis is unclear, challenge @AnalystAgent with specific questions

Every strategy must be executable within 12 weeks maximum.
"""

async def main():
    load_dotenv()
    agent_id = os.getenv("STRATEGIST_AGENT_ID")
    api_key = os.getenv("STRATEGIST_API_KEY")
    aiml_key = os.getenv("AIML_API_KEY")

    if not agent_id or not api_key:
        logger.error("Missing STRATEGIST_AGENT_ID or STRATEGIST_API_KEY"); return
    if not aiml_key:
        logger.error("Missing AIML_API_KEY"); return

    adapter = AIMLApiAdapter(
        api_key=aiml_key,
        model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
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
    logger.info("Strategist Agent online — AIML API (Nemotron)")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())

