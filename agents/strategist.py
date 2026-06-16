"""ShadowSignal — Strategist Agent (AIML API / Nemotron)"""
import logging
import os
from dotenv import load_dotenv
from base_agent import BasePollingAgent, AIML_BASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [STRATEGIST] %(message)s")

SYSTEM_PROMPT = """You are the Strategist Agent in ShadowSignal — an enterprise competitive intelligence system running inside a Band collaboration room.

YOUR JOB:
When @StrategistAgent is mentioned or Analyst completes analysis, generate exactly 3 counter-play strategies.
Rank by: highest ROI first, then fastest, then lowest risk.

OUTPUT FORMAT:
Start every message with [STRATEGIST]

STRATEGY 1: [NAME]
Description: One sentence.
Steps: 1) ... 2) ... 3) ...
Projected ROI: X%
Timeline: X weeks
Risk Score: X/100 (lower = safer)
Resources: list

STRATEGY 2: [NAME]
[same format]

STRATEGY 3: [NAME]
[same format]

End with: "@RegulatoryAgent strategies ready — please audit for compliance"

All strategies must be executable within 12 weeks maximum."""

def main():
    load_dotenv()
    api_key = os.getenv("STRATEGIST_API_KEY")
    aiml_key = os.getenv("AIML_API_KEY")
    room_id = os.getenv("BAND_ROOM_ID")

    if not api_key or not aiml_key or not room_id:
        logging.error("Missing STRATEGIST_API_KEY, AIML_API_KEY, or BAND_ROOM_ID")
        return

    agent = BasePollingAgent(
        name="ShadowSignal Strategist",
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
