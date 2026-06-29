"""
Base polling agent — UPDATED
- Replaced Bright Data with free RSS + DuckDuckGo
- Replaced AIML/Featherless with Groq (primary) + NVIDIA NIM (fallback)
- Nanopayments fire before every LLM call
- Payment events logged for SSE bridge to /pay dashboard
"""
import logging
import os
import time
import sqlite3
import re
import json
import requests
from datetime import datetime
from band_client import BandClient
from free_data import BrightDataClient, format_intel_for_llm
from nanopay import fire_nanopayment, get_balance

logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
BAND_ROOM_ID = os.getenv("BAND_ROOM_ID", "")

GROQ_BASE = "https://api.groq.com/openai/v1"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-4-340b-instruct")

LOOP_TRIGGERS = [
    "[CODEBAND] workflow complete",
    "[CODEBAND] WORKFLOW BLOCKED",
    "@InvestigatorAgent workflow complete",
    "@InvestigatorAgent intel ready",
    "@AnalystAgent analysis complete",
    "@StrategistAgent strategies ready",
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

AGENT_ACTION_MAP = {
    "ShadowSignal Investigator": "web_scrape",
    "ShadowSignal Analyst": "analysis",
    "ShadowSignal Strategist": "strategy",
    "ShadowSignal Regulatory": "compliance",
    "ShadowSignal Codeband": "report",
}

PAYMENT_LOG_PATH = os.getenv("DATA_DIR", "/tmp") + "/payment_events.jsonl"
AIML_BASE = "https://api.aimlapi.com/v1"
FEATHERLESS_BASE = "https://api.featherless.ai/v1"


def log_payment_event(event: dict):
    try:
        with open(PAYMENT_LOG_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.warning(f"[PayLog] {e}")


def call_llm_groq(messages: list, max_retries: int = 3) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL, "messages": messages, "max_tokens": 2048, "temperature": 0.7}
    for attempt in range(max_retries):
        try:
            resp = requests.post(f"{GROQ_BASE}/chat/completions", json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError:
            if resp.status_code == 429:
                time.sleep(2 ** attempt + 1)
            else:
                raise
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return "[ERROR] Groq failed."


def call_llm_nvidia(messages: list, max_retries: int = 2) -> str:
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY not set")
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": NVIDIA_MODEL, "messages": messages, "max_tokens": 2048, "temperature": 0.7}
    for attempt in range(max_retries):
        try:
            resp = requests.post(f"{NVIDIA_BASE}/chat/completions", json=payload, headers=headers, timeout=45)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return "[ERROR] NVIDIA failed."


def call_llm(messages: list, api_key: str = "", model: str = "", base_url: str = "", max_retries: int = 3) -> str:
    if GROQ_API_KEY:
        try:
            return call_llm_groq(messages, max_retries=max_retries)
        except Exception as e:
            logger.warning(f"[LLM] Groq failed: {e}")
    if NVIDIA_API_KEY:
        try:
            return call_llm_nvidia(messages)
        except Exception as e:
            logger.warning(f"[LLM] NVIDIA failed: {e}")
    if api_key and base_url:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "max_tokens": 2048}
        for attempt in range(max_retries):
            try:
                resp = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=45)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                if attempt == max_retries - 1:
                    break
                time.sleep(2 ** attempt)
    return "[ERROR] All LLM providers failed."


def safe_get(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return obj if obj is not None else default


def extract_mentions(content, participants, self_id="", self_name=""):
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
        if self_id and agent_id == self_id:
            continue
        if self_name and name and name.lower() == self_name.lower():
            continue
        if name and not name.startswith("ShadowSignal"):
            continue
        checks = []
        if name:
            checks.append(f"@{name}".lower() in content_lower)
            checks.append(f"@{name.lower().replace(' ', '')}" in content_lower)
        if handle:
            checks.append(f"@{handle}".lower() in content_lower)
        if any(checks):
            mentions.append({"id": agent_id, "name": name, "handle": handle or name.lower().replace(" ", "")})
    return mentions


class BasePollingAgent:
    def __init__(self, name, agent_api_key, system_prompt, llm_api_key="", llm_model="", llm_base_url="", room_id=None):
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
        self.bright_data = BrightDataClient()
        data_dir = os.getenv("DATA_DIR", "/tmp")
        os.makedirs(data_dir, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        self.db_path = f"{data_dir}/shadowsignal_{safe_name}_processed.db"
        self._init_db()
        self._processed_cache = set()
        self._load_cache()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.cursor().execute("CREATE TABLE IF NOT EXISTS processed_messages (msg_id TEXT PRIMARY KEY, processed_at TEXT, agent_name TEXT)")
        conn.commit()
        conn.close()

    def _load_cache(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT msg_id FROM processed_messages WHERE agent_name = ? ORDER BY processed_at DESC LIMIT 2000", (self.name,))
        self._processed_cache = {row[0] for row in c.fetchall()}
        conn.close()

    def _is_processed(self, msg_id):
        if msg_id in self._processed_cache:
            return True
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT 1 FROM processed_messages WHERE msg_id = ? AND agent_name = ?", (msg_id, self.name))
        result = c.fetchone() is not None
        conn.close()
        return result

    def _mark_processed(self, msg_id):
        if msg_id in self._processed_cache:
            return
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO processed_messages (msg_id, processed_at, agent_name) VALUES (?, ?, ?)", (msg_id, datetime.utcnow().isoformat(), self.name))
            conn.commit()
            self._processed_cache.add(msg_id)
        except Exception:
            pass
        finally:
            conn.close()

    def _is_loop_message(self, content, sender_name):
        content_lower = content.lower()
        for trigger in LOOP_TRIGGERS:
            if trigger.lower() in content_lower:
                try:
                    if AGENT_ORDER.index(sender_name) > AGENT_ORDER.index(self.name):
                        return True
                except ValueError:
                    pass
        return False

    def _extract_company_name(self, content):
        cleaned = re.sub(r"@\[.+?\]|@[A-Za-z0-9_\-]+", "", content)
        cleaned = re.sub(r"analyze|research|intel|competitive|check|review|please|can you|will you", "", cleaned, flags=re.IGNORECASE).strip()
        words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in ["the", "this", "that", "for", "about"]]
        return words[0] if words else cleaned

    def _get_next_agent(self):
        try:
            idx = AGENT_ORDER.index(self.name)
            if idx + 1 < len(AGENT_ORDER):
                return AGENT_ORDER[idx + 1].lower().replace(" ", "")
        except ValueError:
            pass
        return ""

    def _get_next_agent_full_name(self):
        try:
            idx = AGENT_ORDER.index(self.name)
            if idx + 1 < len(AGENT_ORDER):
                return AGENT_ORDER[idx + 1]
        except ValueError:
            pass
        return ""

    def run(self):
        try:
            me = self.client.me()
            if isinstance(me, dict):
                self.my_id = me.get("id") or safe_get(me, "agent", "id") or safe_get(me, "data", "id")
                api_name = me.get("name") or safe_get(me, "agent", "name")
                if api_name:
                    self.my_name = api_name
            logger.info(f"[{self.name}] Connected. ID={self.my_id}")
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            return

        try:
            pr = self.client.get_participants(self.room_id)
            if isinstance(pr, list):
                self.participants_cache = pr
            elif isinstance(pr, dict):
                for key in ["participants", "data", "members", "agents"]:
                    if key in pr:
                        self.participants_cache = pr[key]
                        break
        except Exception as e:
            logger.warning(f"[{self.name}] Participants fetch failed: {e}")

        logger.info(f"[{self.name}] Balance: {get_balance()} USDC | LLM: Groq→NVIDIA | Data: RSS+DDG")

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
        message_id = msg.get("id") or safe_get(msg, "message", "id") or safe_get(msg, "data", "id") or ""
        if message_id and self._is_processed(message_id):
            return
        content = str(msg.get("content") or safe_get(msg, "message", "content") or safe_get(msg, "data", "content") or "")
        sender_obj = msg.get("sender") or msg.get("author") or msg.get("user") or {}
        sender_id = sender_obj.get("id", "") if isinstance(sender_obj, dict) else ""
        sender_name = sender_obj.get("name", "unknown") if isinstance(sender_obj, dict) else str(sender_obj)

        is_own = (self.my_id and sender_id and sender_id == self.my_id) or (sender_name and self.my_name and sender_name.lower() == self.my_name.lower())
        if is_own:
            if message_id:
                self._mark_processed(message_id)
                try: self.client.mark_processed(self.room_id, message_id)
                except: pass
            return

        if self._is_loop_message(content, sender_name):
            if message_id:
                self._mark_processed(message_id)
                try: self.client.mark_processed(self.room_id, message_id)
                except: pass
            return

        if message_id:
            self._mark_processed(message_id)
            try: self.client.mark_processing(self.room_id, message_id)
            except Exception as e: logger.warning(f"[{self.name}] mark_processing: {e}")

        try:
            user_message = f"[{sender_name}]: {content}"

            if self.name == "ShadowSignal Investigator" and "analyze" in content.lower():
                company = self._extract_company_name(content)
                if company:
                    intel = self.bright_data.get_competitive_intel(company)
                    if intel.get("sources"):
                        user_message += "\n\n--- REAL-TIME DATA (RSS+DuckDuckGo) ---\n" + format_intel_for_llm(intel) + "\n--- END ---"
                        logger.info(f"[{self.name}] Injected {len(intel['sources'])} sources")

            self.history.append({"role": "user", "content": user_message})

            # NANOPAYMENT
            action = AGENT_ACTION_MAP.get(self.name, "llm_call")
            payment = fire_nanopayment(agent_name=self.name, action=action)
            if payment.get("status") == "success":
                logger.info(f"[{self.name}] 💸 {payment['amount']} USDC tx={payment['tx_id']}")
                log_payment_event({"agent": self.name, "action": action, "amount": payment["amount"], "tx_id": payment["tx_id"], "timestamp": datetime.utcnow().isoformat(), "status": "confirmed"})
            else:
                logger.warning(f"[{self.name}] Payment skipped: {payment.get('reason')}")

            reply = call_llm(messages=self.history, api_key=self.llm_api_key, model=self.llm_model, base_url=self.llm_base_url)
            if not reply:
                reply = f"[{self.name}] Acknowledged."

            self.history.append({"role": "assistant", "content": reply})

            mentions = extract_mentions(reply, self.participants_cache, self_id=self.my_id, self_name=self.my_name)
            next_handle = self._get_next_agent()
            if next_handle and next_handle.lower() not in reply.lower():
                reply = reply.rstrip() + f"\n\n@{next_handle} — please proceed."
                mentions = extract_mentions(reply, self.participants_cache, self_id=self.my_id, self_name=self.my_name)

            if not mentions and self.participants_cache:
                next_name = self._get_next_agent_full_name()
                if next_name:
                    for p in self.participants_cache:
                        if not isinstance(p, dict): continue
                        aid = p.get("id") or safe_get(p, "agent", "id")
                        nm = p.get("name", "")
                        if aid and nm.lower() == next_name.lower():
                            mentions.append({"id": aid, "name": nm, "handle": p.get("handle", nm.lower().replace(" ", ""))})
                            break

            sent = False
            if mentions:
                try:
                    self.client.send_message(self.room_id, reply, mentions)
                    sent = True
                except Exception as e:
                    logger.error(f"[{self.name}] send_message: {e}")
            if not sent:
                try:
                    self.client.post_event(self.room_id, reply[:1000], message_type="thought")
                except Exception as e:
                    logger.error(f"[{self.name}] post_event: {e}")

            if message_id:
                try: self.client.mark_processed(self.room_id, message_id)
                except: pass

        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}", exc_info=True)
            if message_id:
                try: self.client.mark_failed(self.room_id, message_id, str(e))
                except: pass
