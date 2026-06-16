"""ShadowSignal — GTM Analyst Agent (AIML API / Nemotron)"""
import logging
import os
from dotenv import load_dotenv
from base_agent import BasePollingAgent, AIML_BASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ANALYST] %(message)s")

SYSTEM_PROMPT = """You are the GTM Analyst Agent in ShadowSignal — an enterprise competitive intelligence system running inside a Band collaboration room.

YOUR JOB:
When @AnalystAgent is mentioned or Investigator drops intel, produce structured GTM analysis.

OUTPUT FORMAT:
Start every message with [ANALYST]

IMPACT SCORE: X/100
TREND: up/down/stable
THREAT LEVEL: low/medium/high/critical
CONFIDENCE: X%

KEY FINDINGS:
- Finding with specific data point
- Finding with specific data point
- Finding with specific data point

RECOMMENDED ACTIONS:
- Action with timeline
- Action with timeline

End with: "@StrategistAgent analysis complete — please generate counter-play strategies"

If intel is insufficient, ask: "@InvestigatorAgent need more data on [specific gap]"
"""

def main():
    load_dotenv()
    api_key = os.getenv("ANALYST_API_KEY")
    aiml_key = os.getenv("AIML_API_KEY")
    room_id = os.getenv("BAND_ROOM_ID")

    if not api_key or not aiml_key or not room_id:
        logging.error("Missing ANALYST_API_KEY, AIML_API_KEY, or BAND_ROOM_ID")
        return

    agent = BasePollingAgent(
        name="ShadowSignal Analyst",
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
