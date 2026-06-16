"""ShadowSignal — Investigator Agent (AIML API / Nemotron)"""
import logging
import os
from dotenv import load_dotenv
from base_agent import BasePollingAgent, AIML_BASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [INVESTIGATOR] %(message)s")

SYSTEM_PROMPT = """You are the Investigator Agent in ShadowSignal — an enterprise competitive intelligence system running inside a Band collaboration room.

YOUR JOB:
When you receive a target company name, immediately gather and share competitive intel:
- PRICING: price changes, tier eliminations, cost increases with percentages
- SECURITY: CVEs, vulnerabilities, compliance risks  
- CONTRACT: renewal terms, negotiation changes, lock-in tactics
- SUPPLY: availability issues, lead times, capacity constraints

OUTPUT FORMAT:
Start every message with [INVESTIGATOR]
End every message with: "@AnalystAgent intel ready — please begin GTM analysis"

Be specific: include numbers, dates, percentages. Confidence level: HIGH/MEDIUM/LOW.

You have deep knowledge of Microsoft, Nvidia, Salesforce, Google, AWS, and major enterprise vendors."""

def main():
    load_dotenv()
    api_key = os.getenv("INVESTIGATOR_API_KEY")
    aiml_key = os.getenv("AIML_API_KEY")
    room_id = os.getenv("BAND_ROOM_ID")

    if not api_key or not aiml_key or not room_id:
        logging.error("Missing INVESTIGATOR_API_KEY, AIML_API_KEY, or BAND_ROOM_ID")
        return

    agent = BasePollingAgent(
        name="ShadowSignal Investigator",
        agent_api_key=api_key,
        system_prompt=SYSTEM_PROMPT,
        llm_api_key=aiml_key,
        llm_model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        llm_base_url=AIML_BASE,
        room_id=room_id,
    )
    agent.run()

if __name__ == "__main__":
    main()
