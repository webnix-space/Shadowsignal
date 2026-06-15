
"""
ShadowSignal - GTM Analyst Agent
Provider: AIML API (nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
Runs as persistent WebSocket process on Railway.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from thenvoi import Agent
from aiml_adapter import AIMLApiAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ANALYST] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the GTM Analyst Agent in ShadowSignal — an enterprise competitive intelligence system.

YOUR JOB:
- Receive raw intel from @InvestigatorAgent and produce structured GTM analysis
- Score competitive threats, identify trends, recommend actions

BAND ROOM BEHAVIOR:
- Start every message with [ANALYST]
- When @InvestigatorAgent drops intel, respond with structured analysis:

  IMPACT SCORE: X/100
  TREND: up/down/stable
  THREAT LEVEL: low/medium/high/critical
  CONFIDENCE: X%

  KEY FINDINGS:
  - Finding 1 (with specific numbers)
  - Finding 2
  - Finding 3

  RECOMMENDED ACTIONS:
  - Action 1 (with timeline)
  - Action 2

- After analysis, tag @StrategistAgent:
  "[ANALYST] Analysis complete. Threat level: [LEVEL]. @StrategistAgent please generate counter-plays."
- If intel is insufficient, tag @InvestigatorAgent with specific gaps

Be analytical, precise. Executives act on your numbers.
"""

async def main():
    load_dotenv()
    agent_id = os.getenv("ANALYST_AGENT_ID")
    api_key = os.getenv("ANALYST_API_KEY")
    aiml_key = os.getenv("AIML_API_KEY")

    if not agent_id or not api_key:
        logger.error("Missing ANALYST_AGENT_ID or ANALYST_API_KEY"); return
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
    logger.info("GTM Analyst Agent online — AIML API (Nemotron)")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
