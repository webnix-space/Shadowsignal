"""
Base polling agent using Band REST API directly.
Fixed to handle actual Band API response structure.
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
    payload = {"model": model, "messages": messages, "max_tokens": 2048}
    resp = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def safe_get(obj, *keys, default=None):
    """Safely traverse nested dict/list."""
    for key in keys:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return default
    return obj if obj is not None else default


def extract_mentions(content: str, participants: list) -> list:
    """Find @mentions in content and return mention objects."""
    if not content or not participants:
        return []
    mentions = []
    for p in participants:
        if not isinstance(p, dict):
            continue
        agent_id = p.get("id") or safe_get(p, "agent", "id")
        name = p.get("name", "")
        handle = p.get("handle", "")
        if not agent_id:
            continue
        # Check various mention formats
        if any([
            name and f"@{name}" in content,
            handle and f"@{handle}" in content,
            name and name in content and "@" in content,
        ]):
            mentions.append({"id": agent_id, "name": name, "handle": handle or name})
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
        try:
            me = self.client.me()
            # Handle both possible response shapes
            if isinstance(me, dict):
                self.my_id = me.get("id") or safe_get(me, "agent", "id")
            logger.info(f"[{self.name}] Connected. ID: {self.my_id}")
        except Exception as e:
            logger.error(f"[{self.name}] Band connection failed: {e}")
            return

        try:
            participants_resp = self.client.get_participants(self.room_id)
            # Participants may be wrapped in a key
            if isinstance(participants_resp, list):
                self.participants_cache = participants_resp
            elif isinstance(participants_resp, dict):
                self.participants_cache = (
                    participants_resp.get("participants") or
                    participants_resp.get("data") or
                    list(participants_resp.values())[0] if participants_resp else []
                )
            logger.info(f"[{self.name}] {len(self.participants_cache)} participants in room")
        except Exception as e:
            logger.warning(f"[{self.name}] Could not fetch participants: {e}")

        logger.info(f"[{self.name}] Polling room {self.room_id}...")

        while True:
            try:
                msg = self.client.get_next_message(self.room_id)
                if msg is not None:
                    self._handle_message(msg)
                else:
                    time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.info(f"[{self.name}] Shutting down.")
                break
            except Exception as e:
                logger.error(f"[{self.name}] Poll error: {e}")
                time.sleep(POLL_INTERVAL)

    def _handle_message(self, msg):
        # Log the raw message shape for debugging
        logger.info(f"[{self.name}] Raw msg type: {type(msg).__name__}, keys: {list(msg.keys()) if isinstance(msg, dict) else 'N/A'}")

        if not isinstance(msg, dict):
            logger.warning(f"[{self.name}] Unexpected message type: {type(msg)}")
            return

        # Extract fields - handle multiple possible structures
        message_id = (
            msg.get("id") or
            safe_get(msg, "message", "id") or
            ""
        )

        # Content might be nested
        content = (
            msg.get("content") or
            safe_get(msg, "message", "content") or
            safe_get(msg, "data", "content") or
            ""
        )

        # Sender might be nested
        sender_obj = msg.get("sender") or msg.get("author") or {}
        if isinstance(sender_obj, dict):
            sender_name = sender_obj.get("name", "unknown")
            sender_id = sender_obj.get("id", "")
        else:
            sender_name = str(sender_obj) if sender_obj else "unknown"
            sender_id = ""

        # Skip own messages
        if self.my_id and sender_id == self.my_id:
            if message_id:
                try:
                    self.client.mark_processed(self.room_id, message_id)
                except Exception:
                    pass
            return

        content_str = str(content) if content else ""
        logger.info(f"[{self.name}] From {sender_name}: {content_str[:100]}")

        if message_id:
            try:
                self.client.mark_processing(self.room_id, message_id)
            except Exception as e:
                logger.warning(f"[{self.name}] mark_processing failed: {e}")

        try:
            self.history.append({
                "role": "user",
                "content": f"[{sender_name}]: {content_str}"
            })

            reply = call_llm(
                messages=self.history,
                api_key=self.llm_api_key,
                model=self.llm_model,
                base_url=self.llm_base_url,
            )

            if not reply:
                reply = f"[{self.name.split()[-1].upper()}] Processing complete."

            self.history.append({"role": "assistant", "content": reply})

            # Try to send with mentions
            mentions = extract_mentions(reply, self.participants_cache)
            logger.info(f"[{self.name}] Reply ready, {len(mentions)} mentions found")

            try:
                if mentions:
                    self.client.send_message(self.room_id, reply, mentions)
                else:
                    # Post as event — no mention required
                    self.client.post_event(self.room_id, reply, message_type="thought")
            except Exception as send_err:
                logger.error(f"[{self.name}] Send failed: {send_err}")
                # Fallback: try as event
                try:
                    self.client.post_event(self.room_id, reply[:500], message_type="thought")
                except Exception:
                    pass

            if message_id:
                try:
                    self.client.mark_processed(self.room_id, message_id)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"[{self.name}] Processing error: {e}")
            if message_id:
                try:
                    self.client.mark_failed(self.room_id, message_id, str(e))
                except Exception:
                    pass
