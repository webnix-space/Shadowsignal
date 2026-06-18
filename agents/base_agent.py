"""
Base polling agent using Band REST API + Bright Data for REAL competitive intelligence.
FIXED: Per-agent SQLite deduplication + LOOP DETECTION + REAL DATA via Bright Data.
FIXED: F-string syntax error (line 325) — replaced with proper string concatenation.
FIXED: Loop detection — made triggers agent-specific to avoid blocking upstream messages.
FIXED: Added retry with exponential backoff for LLM calls.
FIXED: SQLite DB path uses persistent storage if available.
"""
import logging
import os
import time
import sqlite3
import re
import requests
from datetime import datetime
from band_client import BandClient
from bright_data import BrightDataClient, format_intel_for_llm

logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
BAND_ROOM_ID = os.getenv("BAND_ROOM_ID", "")

AIML_BASE = "https://api.aimlapi.com/v1"
FEATHERLESS_BASE = "https://api.featherless.ai/v1"

# Loop detection triggers — made AGENT-SPECIFIC to avoid blocking upstream messages
# Only skip if the exact agent posted the completion phrase
LOOP_TRIGGERS = [
    "[CODEBAND] workflow complete",
    "[CODEBAND] WORKFLOW BLOCKED",
    "@InvestigatorAgent \u2705 workflow complete",
    "@InvestigatorAgent intel ready",
    "@AnalystAgent analysis complete",
    "@StrategistAgent strategies ready",
    "@StrategistAgent revision needed",
    "@RegulatoryAgent cleared",
    "@RegulatoryAgent BLOCKED",
]

AGENT_ORDER = [
    "ShadowSignal Investigator",
    "ShadowSignal Analyst",
    "ShadowSignal Strategist",
    "ShadowSignal Regulatory",
    "ShadowSignal Codeband",
]


def call_llm(messages: list, api_key: str, model: str, base_url: str, max_retries: int = 3) -> str:
    """Call LLM with exponential backoff retry."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "max_tokens": 2048}

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=45,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            wait = 2 ** attempt
            logger.warning(f"[LLM] Timeout on attempt {attempt + 1}/{max_retries}, retrying in {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:  # Rate limit
                wait = 2 ** attempt + 1
                logger.warning(f"[LLM] Rate limited (429), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            logger.warning(f"[LLM] Error on attempt {attempt + 1}/{max_retries}: {e}, retrying in {wait}s...")
            time.sleep(wait)

    return "[ERROR] LLM call failed after all retries."


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

        # Bright Data for real-time intel
        self.bright_data = BrightDataClient()

        # Use persistent storage if available, fallback to /tmp
        data_dir = os.getenv("DATA_DIR", "/tmp")
        os.makedirs(data_dir, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        self.db_path = f"{data_dir}/shadowsignal_{safe_name}_processed.db"
        self._init_db()
        self._processed_cache = set()
        self._load_cache()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                msg_id TEXT PRIMARY KEY,
                processed_at TEXT,
                agent_name TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _load_cache(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT msg_id FROM processed_messages WHERE agent_name = ? ORDER BY processed_at DESC LIMIT 2000",
            (self.name,),
        )
        self._processed_cache = {row[0] for row in c.fetchall()}
        conn.close()

    def _is_processed(self, msg_id: str) -> bool:
        if msg_id in self._processed_cache:
            return True
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM processed_messages WHERE msg_id = ? AND agent_name = ?",
            (msg_id, self.name),
        )
        result = c.fetchone() is not None
        conn.close()
        return result

    def _mark_processed(self, msg_id: str):
        if msg_id in self._processed_cache:
            return
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute(
                "INSERT OR IGNORE INTO processed_messages (msg_id, processed_at, agent_name) VALUES (?, ?, ?)",
                (msg_id, datetime.utcnow().isoformat(), self.name),
            )
            conn.commit()
            self._processed_cache.add(msg_id)
        except Exception:
            pass
        finally:
            conn.close()

    def _is_loop_message(self, content: str, sender_name: str) -> bool:
        """Detect loop messages — only skip if sender is downstream AND content contains completion phrase."""
        content_lower = content.lower()

        # Check for specific completion phrases from downstream agents
        for trigger in LOOP_TRIGGERS:
            if trigger.lower() in content_lower:
                # Only block if sender is downstream in the chain
                try:
                    my_index = AGENT_ORDER.index(self.name)
                    sender_index = AGENT_ORDER.index(sender_name)
                    if sender_index > my_index:
                        logger.info(f"[{self.name}] LOOP DETECTED: downstream msg from {sender_name} with trigger \"{trigger}\" — skipping")
                        return True
                except ValueError:
                    pass

        return False

    def _extract_company_name(self, content: str) -> str:
        """Extract company name from user query like \"analyze nvidia\" or \"analyze google\"."""
        cleaned = re.sub(r"@[A-Za-z0-9_\-]+", "", content)
        cleaned = re.sub(r"analyze|research|intel|competitive|check|review", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        words = [w for w in cleaned.split() if len(w) > 2]
        return words[0] if words else cleaned

    def run(self):
        try:
            me = self.client.me()
            if isinstance(me, dict):
                self.my_id = me.get("id") or safe_get(me, "agent", "id") or safe_get(me, "data", "id")
                api_name = me.get("name") or safe_get(me, "agent", "name")
                if api_name:
                    self.my_name = api_name
            logger.info(f"[{self.name}] Connected. ID={self.my_id} Name={self.my_name}")
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            return

        try:
            participants_resp = self.client.get_participants(self.room_id)
            if isinstance(participants_resp, list):
                self.participants_cache = participants_resp
            elif isinstance(participants_resp, dict):
                for key in ["participants", "data", "members", "agents"]:
                    if key in participants_resp:
                        self.participants_cache = participants_resp[key]
                        break
            logger.info(f"[{self.name}] {len(self.participants_cache)} participants cached")
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
            return

        message_id = (
            msg.get("id") or
            safe_get(msg, "message", "id") or
            safe_get(msg, "data", "id") or
            ""
        )

        if message_id and self._is_processed(message_id):
            return

        content = (
            msg.get("content") or
            safe_get(msg, "message", "content") or
            safe_get(msg, "data", "content") or
            ""
        )
        content = str(content) if content else ""

        sender_obj = msg.get("sender") or msg.get("author") or msg.get("user") or {}
        if isinstance(sender_obj, dict):
            sender_id = sender_obj.get("id", "")
            sender_name = sender_obj.get("name", "unknown")
        else:
            sender_id = ""
            sender_name = str(sender_obj) if sender_obj else "unknown"

        logger.info(f"[{self.name}] Message id={message_id} from={sender_name} content={content[:80]}")

        # Skip own messages
        is_own = False
        if self.my_id and sender_id and sender_id == self.my_id:
            is_own = True
        if sender_name and self.my_name and sender_name.lower() == self.my_name.lower():
            is_own = True

        if is_own:
            if message_id:
                self._mark_processed(message_id)
                try:
                    self.client.mark_processed(self.room_id, message_id)
                except Exception:
                    pass
            return

        # Loop detection — only skip downstream completion messages
        if self._is_loop_message(content, sender_name):
            if message_id:
                self._mark_processed(message_id)
                try:
                    self.client.mark_processed(self.room_id, message_id)
                except Exception:
                    pass
            return

        # Mark processing
        if message_id:
            self._mark_processed(message_id)
            try:
                self.client.mark_processing(self.room_id, message_id)
            except Exception as e:
                logger.warning(f"[{self.name}] mark_processing failed: {e}")

        try:
            # Build user message with optional real-time data
            user_message = f"[{sender_name}]: {content}"

            # Investigator fetches real-time data via Bright Data
            if self.name == "ShadowSignal Investigator" and "analyze" in content.lower():
                company = self._extract_company_name(content)
                if company and self.bright_data.api_key:
                    logger.info(f"[{self.name}] Fetching real-time intel for: {company}")
                    intel = self.bright_data.get_competitive_intel(company)
                    if intel.get("sources"):
                        intel_text = format_intel_for_llm(intel)
                        # FIXED: Proper string concatenation with explicit newlines
                        user_message = (
                            user_message
                            + "\n\n--- REAL-TIME WEB DATA ---\n"
                            + intel_text
                            + "\n--- END WEB DATA ---"
                        )
                        logger.info(f"[{self.name}] Added {len(intel['sources'])} real sources")

            self.history.append({"role": "user", "content": user_message})

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
