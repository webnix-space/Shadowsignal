"""
Base polling agent — polls Band REST API for messages, processes them with an LLM,
sends reply back to the room. No WebSocket, no SDK required.
"""
import logging
import os
import time
import requests
from band_client import BandClient

logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
BAND_ROOM_ID = os.getenv("BAND_ROOM_ID", "")

AIML_BASE = "https://api.aimlapi.com/v1"
FEATHERLESS_BASE = "https://api.featherless.ai/v1"


def call_llm(messages: list, api_key: str, model: str, base_url: str) -> str:
    """Call any OpenAI-compatible LLM endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
    }
    resp = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


class BasePollingAgent:
    """
    Polls Band REST API for messages addressed to this agent,
    processes them with an LLM, sends reply back to the room.
    """

    def __init__(
        self,
        name: str,
        agent_api_key: str,
        system_prompt: str,
        llm_api_key: str,
        llm_model: str,
        llm_base_url: str,
        room_id: str = None,
    ):
        self.name = name
        self.client = BandClient(agent_api_key)
        self.system_prompt = system_prompt
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.room_id = room_id or BAND_ROOM_ID
        self.history = [{"role": "system", "content": system_prompt}]

    def run(self):
        """Main polling loop."""
        # Validate connection
        try:
            me = self.client.me()
            logger.info(f"[{self.name}] Connected to Band as: {me.get('name', 'unknown')}")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to connect to Band: {e}")
            return

        logger.info(f"[{self.name}] Polling room {self.room_id} every {POLL_INTERVAL}s...")

        while True:
            try:
                msg = self.client.get_next_message(self.room_id)
                if msg:
                    self._handle_message(msg)
                else:
                    time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.info(f"[{self.name}] Shutting down.")
                break
            except Exception as e:
                logger.error(f"[{self.name}] Polling error: {e}")
                time.sleep(POLL_INTERVAL)

    def _handle_message(self, msg: dict):
        message_id = msg.get("id", "")
        content = msg.get("content", "")
        sender = msg.get("sender", {}).get("name", "unknown")

        logger.info(f"[{self.name}] Message from {sender}: {content[:100]}")

        # Skip messages sent by this agent itself
        if sender == self.name:
            if message_id:
                self.client.mark_processed(message_id)
            return

        # Mark as processing
        if message_id:
            self.client.mark_processing(message_id)

        try:
            # Add to conversation history
            self.history.append({"role": "user", "content": f"[{sender}]: {content}"})

            # Call LLM
            reply = call_llm(
                messages=self.history,
                api_key=self.llm_api_key,
                model=self.llm_model,
                base_url=self.llm_base_url,
            )

            # Add reply to history
            self.history.append({"role": "assistant", "content": reply})

            # Send reply to Band room
            self.client.send_message(self.room_id, reply)
            logger.info(f"[{self.name}] Replied: {reply[:100]}")

            # Mark as processed
            if message_id:
                self.client.mark_processed(message_id)

        except Exception as e:
            logger.error(f"[{self.name}] Error processing message: {e}")
            if message_id:
                self.client.mark_failed(message_id, str(e))
