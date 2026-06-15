"""
ShadowSignal - Investigator Agent
Provider: AIML API (nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
Runs as persistent WebSocket process on Railway.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from thenvoi import Agent
from thenvoi.adapters import LangGraphAdapter
from thenvoi.config import load_agent_config
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from aiml_adapter import AIMLApiAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [INVESTIGATOR] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Investigator Agent in ShadowSignal — an enterprise competitive intelligence system.

YOUR JOB:
- When someone sends a target company name, immediately gather competitive intel on it
- Focus on: pricing changes, security vulnerabilities, contract terms, supply chain issues
- Structure findings with categories: PRICING / SECURITY / CONTRACT / SUPPLY

BAND ROOM BEHAVIOR:
- Start every message with [INVESTIGATOR]
- After depositing intel, use thenvoi_send_message to tag @AnalystAgent:
  "[INVESTIGATOR] Intel ready for [TARGET]. @AnalystAgent please begin GTM analysis."
- Be specific: numbers, dates, percentages matter
- Include impact estimates and urgency: IMMEDIATE / Q3 2026 / WATCH
- Note confidence: HIGH / MEDIUM / LOW

You have deep knowledge of enterprise software, cloud infrastructure, and cybersecurity markets.
"""

async def main():
    load_dotenv()
    agent_id = os.getenv("INVESTIGATOR_AGENT_ID")
    api_key = os.getenv("INVESTIGATOR_API_KEY")
    aiml_key = os.getenv("AIML_API_KEY")

    if not agent_id or not api_key:
        logger.error("Missing INVESTIGATOR_AGENT_ID or INVESTIGATOR_API_KEY"); return
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
    logger.info("Investigator Agent online — AIML API (Nemotron)")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())

