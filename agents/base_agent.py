"""
Base polling agent using Band REST API directly.
Key facts from docs:
- Auth: X-API-Key header
- Messages require @mentions with mention objects
- Agents only receive messages where they are @mentioned
- /messages/next for startup sync, not continuous polling
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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "max_tokens": 4096}
    resp = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def extract_mentions(content: str, participants: list) -> list:
    """
    Find @mentions in content and return mention objects.
    participants = list of participant dicts from Band API.
    """
    mentions = []
    for p in participants:
        name = p.get("name", "")
        handle = p.get("handle", "")
        agent_id = p.get("id", "")
        if not agent_id:
            continue
        if (name and f"@{name}" in content) or (handle and f"@{handle}" in content):
            mentions.append({"id": agent_id, "name": name, "handle": handle})
    return mentions


class BasePollingAgent:
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
        self.my_id = None
        self.participants_cache = []

    def run(self):
        # Validate connection
        try:
            me = self.client.me()
            self.my_id = me.get("id")
            logger.info(f"[{self.name}] Connected. Agent ID: {self.my_id}")
        except Exception as e:
            logger.error(f"[{self.name}] Band connection failed: {e}")
            return

        # Cache participants
        try:
            self.participants_cache = self.client.get_participants(self.room_id)
            logger.info(f"[{self.name}] Room has {len(self.participants_cache)} participants")
        except Exception as e:
            logger.warning(f"[{self.name}] Could not fetch participants: {e}")

        logger.info(f"[{self.name}] Polling room {self.room_id}...")

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
                logger.error(f"[{self.name}] Error: {e}")
                time.sleep(POLL_INTERVAL)

    def _handle_message(self, msg: dict):
        message_id = msg.get("id", "")
        content = msg.get("content", "")
        sender = msg.get("sender", {}).get("name", "unknown")
        sender_id = msg.get("sender", {}).get("id", "")

        # Skip our own messages
        if sender_id == self.my_id:
            if message_id:
                self.client.mark_processed(self.room_id, message_id)
            return

        logger.info(f"[{self.name}] From {sender}: {content[:120]}")

        if message_id:
            self.client.mark_processing(self.room_id, message_id)

        try:
            self.history.append({"role": "user", "content": f"[{sender}]: {content}"})

            reply = call_llm(
                messages=self.history,
                api_key=self.llm_api_key,
                model=self.llm_model,
                base_url=self.llm_base_url,
            )

            self.history.append({"role": "assistant", "content": reply})

            # Extract mentions from reply
            mentions = extract_mentions(reply, self.participants_cache)

            if mentions:
                # Send as message with mentions
                self.client.send_message(self.room_id, reply, mentions)
            else:
                # No mentions found — post as event so it still appears in room
                self.client.post_event(self.room_id, reply, message_type="thought")

            logger.info(f"[{self.name}] Sent reply with {len(mentions)} mentions")

            if message_id:
                self.client.mark_processed(self.room_id, message_id)

        except Exception as e:
            logger.error(f"[{self.name}] Processing error: {e}")
            if message_id:
                self.client.mark_failed(self.room_id, message_id, str(e))
