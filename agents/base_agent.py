"""
Base polling agent using Band REST API directly.
Fixed: self-message loop prevention + proper handoff tracking.
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

# Track processed message IDs to prevent loops
processed_ids = set()


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
    return resp.json()["choices"][0]["message"]["content"]


def safe_get(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return obj if obj is not None else default


def extract_mentions(content: str, participants: list) -> list:
    if not content or not participants:
        return []
    mentions = []
    content_lower = content.lower()
    for p in participants:
        if not isinstance(p, dict):
            continue
        agent_id = p.get("id") or safe_get(p, "agent", "id")
        name = p.get("name", "")
        handle = p.get("handle", "")
        if not agent_id:
            continue
        # Check if this participant is mentioned
        checks = []
        if name:
            checks.append(f"@{name}".lower() in content_lower)
            checks.append(name.lower() in content_lower and "@" in content)
        if handle:
            checks.append(f"@{handle}".lower() in content_lower)
        if any(checks):
            mentions.append({
                "id": agent_id,
                "name": name,
                "handle": handle or name.lower().replace(" ", "-")
            })
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
        self.my_name = name
        self.participants_cache = []
        self.locally_processed = set()  # Per-agent processed IDs

    def run(self):
        try:
            me = self.client.me()
            logger.info(f"[{self.name}] /me response: {me}")
            if isinstance(me, dict):
                self.my_id = (
                    me.get("id") or
                    safe_get(me, "agent", "id") or
                    safe_get(me, "data", "id")
                )
                # Also grab name from response
                api_name = me.get("name") or safe_get(me, "agent", "name")
                if api_name:
                    self.my_name = api_name
            logger.info(f"[{self.name}] Connected. ID={self.my_id} Name={self.my_name}")
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            return

        try:
            participants_resp = self.client.get_participants(self.room_id)
            logger.info(f"[{self.name}] Participants response type: {type(participants_resp)}")
            if isinstance(participants_resp, list):
                self.participants_cache = participants_resp
            elif isinstance(participants_resp, dict):
                for key in ["participants", "data", "members", "agents"]:
                    if key in participants_resp:
                        self.participants_cache = participants_resp[key]
                        break
            logger.info(f"[{self.name}] {len(self.participants_cache)} participants cached")
            # Log participant IDs for debugging
            for p in self.participants_cache:
                if isinstance(p, dict):
                    logger.info(f"  Participant: {p.get('name')} id={p.get('id')} handle={p.get('handle')}")
        except Exception as e:
            logger.warning(f"[{self.name}] Participants fetch failed: {e}")

        logger.info(f"[{self.name}] Starting poll loop for room {self.room_id}")

        while True:
            try:
                msg = self.client.get_next_message(self.room_id)
                if msg is not None:
                    self._handle_message(msg)
                else:
                    time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Poll error: {e}")
                time.sleep(POLL_INTERVAL)

    def _handle_message(self, msg):
        if not isinstance(msg, dict):
            logger.warning(f"[{self.name}] Non-dict message: {type(msg)} = {msg}")
            return

        # Extract message ID
        message_id = (
            msg.get("id") or
            safe_get(msg, "message", "id") or
            safe_get(msg, "data", "id") or
            ""
        )

        # Skip if already processed locally
        if message_id and message_id in self.locally_processed:
            logger.info(f"[{self.name}] Skipping already-processed: {message_id}")
            return

        # Extract content
        content = (
            msg.get("content") or
            safe_get(msg, "message", "content") or
            safe_get(msg, "data", "content") or
            ""
        )
        content = str(content) if content else ""

        # Extract sender
        sender_obj = msg.get("sender") or msg.get("author") or msg.get("user") or {}
        if isinstance(sender_obj, dict):
            sender_id = sender_obj.get("id", "")
            sender_name = sender_obj.get("name", "unknown")
            sender_handle = sender_obj.get("handle", "")
        else:
            sender_id = ""
            sender_name = str(sender_obj) if sender_obj else "unknown"
            sender_handle = ""

        logger.info(f"[{self.name}] Message id={message_id} from_id={sender_id} my_id={self.my_id} content={content[:80]}")

        # Skip own messages — check by ID AND name
        is_own = False
        if self.my_id and sender_id and sender_id == self.my_id:
            is_own = True
        if sender_name and self.my_name and sender_name.lower() == self.my_name.lower():
            is_own = True
        if sender_handle and self.my_name and sender_handle.lower() in self.my_name.lower():
            is_own = True

        if is_own:
            logger.info(f"[{self.name}] Skipping own message")
            if message_id:
                self.locally_processed.add(message_id)
                try:
                    self.client.mark_processed(self.room_id, message_id)
                except Exception:
                    pass
            return

        # Mark processing
        if message_id:
            self.locally_processed.add(message_id)
            try:
                self.client.mark_processing(self.room_id, message_id)
            except Exception as e:
                logger.warning(f"[{self.name}] mark_processing failed: {e}")

        try:
            self.history.append({"role": "user", "content": f"[{sender_name}]: {content}"})

            reply = call_llm(
                messages=self.history,
                api_key=self.llm_api_key,
                model=self.llm_model,
                base_url=self.llm_base_url,
            )

            if not reply:
                reply = f"[{self.name}] Acknowledged."

            self.history.append({"role": "assistant", "content": reply})
            logger.info(f"[{self.name}] LLM reply: {reply[:150]}")

            # Extract mentions
            mentions = extract_mentions(reply, self.participants_cache)
            logger.info(f"[{self.name}] Mentions found: {[m['name'] for m in mentions]}")

            sent = False
            if mentions:
                try:
                    self.client.send_message(self.room_id, reply, mentions)
                    logger.info(f"[{self.name}] Sent message with mentions")
                    sent = True
                except Exception as e:
                    logger.error(f"[{self.name}] send_message failed: {e}")

            if not sent:
                try:
                    self.client.post_event(self.room_id, reply[:1000], message_type="thought")
                    logger.info(f"[{self.name}] Posted as event")
                except Exception as e:
                    logger.error(f"[{self.name}] post_event failed: {e}")

            if message_id:
                try:
                    self.client.mark_processed(self.room_id, message_id)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"[{self.name}] Processing error: {e}", exc_info=True)
            if message_id:
                try:
                    self.client.mark_failed(self.room_id, message_id, str(e))
                except Exception:
                    pass
