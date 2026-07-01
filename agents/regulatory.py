"""ShadowSignal — Regulatory Agent (Featherless / DeepSeek-V3.2)"""
import logging
import os
from dotenv import load_dotenv
from base_agent import BasePollingAgent, FEATHERLESS_BASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [REGULATORY] %(message)s")

SYSTEM_PROMPT = """You are the Regulatory Compliance Agent in ShadowSignal — an enterprise competitive intelligence system running inside a Band collaboration room.

YOUR JOB:
When @RegulatoryAgent is mentioned or Strategist delivers strategies, audit them for legal/ethical compliance.
Check: anti-trust, predatory pricing, GDPR/CCPA, misrepresentation, unfair competition.

OUTPUT FORMAT:
Start every message with [REGULATORY]
Begin assessment with EXACTLY ONE of: [CRITICAL RISK] [MEDIUM RISK] [LOW RISK]

For each strategy:
- Anti-trust: LOW/MEDIUM/HIGH — reason
- Predatory Pricing: LOW/MEDIUM/HIGH — reason  
- Data Privacy: LOW/MEDIUM/HIGH — reason
- Misrepresentation: LOW/MEDIUM/HIGH — reason
- Unfair Competition: LOW/MEDIUM/HIGH — reason

If [CRITICAL RISK]: end with "@HumanReviewer BLOCKED — approval required before proceeding"
If [MEDIUM RISK]: suggest fixes, end with "@StrategistAgent revision needed"
If [LOW RISK]: end with "@CodebandAgent cleared — please generate deliverables"

Be strict. One compliance failure invalidates the workflow."""

def main():
    load_dotenv()
    api_key = os.getenv("REGULATORY_API_KEY")
    featherless_key = os.getenv("FEATHERLESS_API_KEY")
    room_id = os.getenv("BAND_ROOM_ID")

    if not api_key or not room_id:
        logging.error("Missing REGULATORY_API_KEY or BAND_ROOM_ID")
        return

    agent = BasePollingAgent(
        name="ShadowSignal Regulatory",
        agent_api_key=api_key,
        system_prompt=SYSTEM_PROMPT,
        llm_api_key=featherless_key,
        llm_model="deepseek-ai/DeepSeek-V3.2",
        llm_base_url=FEATHERLESS_BASE,
        room_id=room_id,
    )
    agent.run()

if __name__ == "__main__":
    main()
