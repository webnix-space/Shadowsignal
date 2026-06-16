import os
import re
import json
import time
import sqlite3
import threading
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# ─── Constants matching original API ───
AIML_BASE = "https://api.aimlapi.com/v1"
FEATHERLESS_BASE = "https://api.featherless.ai/v1"


class BasePollingAgent:
    """
    FIXED: Uses X-API-Key header instead of Bearer token for Band.ai authentication.
    Includes deduplication, error handling, and backoff.
    """

    def __init__(
        self,
        name: str,
        agent_api_key: str,
        system_prompt: str,
        llm_api_key: str,
        llm_model: str,
        llm_base_url: str,
        room_id: str,
        poll_interval: float = 5.0,
    ):
        self.name = name
        self.agent_api_key = agent_api_key
        self.system_prompt = system_prompt
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url.rstrip("/")
        self.room_id = room_id
        self.poll_interval = poll_interval

        # Band API config — FIXED: X-API-Key instead of Bearer
        self.band_base = "https://app.band.ai/api/v1"
        self.band_headers = {
            "X-API-Key": agent_api_key,
            "Content-Type": "application/json",
        }

        # ─── DEDUPLICATION STATE ───
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        self.db_path = f"/tmp/shadowsignal_{safe_name}_processed.db"
        self._init_db()
        self._processed_cache = set()
        self._load_cache()

        # ─── ERROR HANDLING STATE ───
        self.consecutive_errors = 0
        self.max_backoff = 60
        self.max_retries = 1

        # ─── WORKFLOW STATE ───
        self.last_reply_id = None
        self._lock = threading.Lock()

    # ─── SQLite Deduplication ───

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

    # ─── Band API Helpers ───

    def _band_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Dict]:
        url = f"{self.band_base}/{endpoint.lstrip("/")}"

        for attempt in range(self.max_retries + 1):
            try:
                res = requests.request(
                    method, url, headers=self.band_headers, timeout=15, **kwargs
                )

                if res.status_code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    return None

                if res.status_code >= 400:
                    return None

                if res.status_code == 204 or not res.text:
                    return {}

                try:
                    return res.json()
                except json.JSONDecodeError:
                    return None

            except requests.exceptions.RequestException:
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return None
            except Exception:
                return None

        return None

    def _get_messages(self) -> List[Dict]:
        res = self._band_request("GET", f"/agent/chats/{self.room_id}/messages")
        if res and isinstance(res, dict):
            return res.get("messages", []) or res.get("data", [])
        return []

    def _send_reply(self, content: str) -> Optional[Dict]:
        payload = {"content": content, "type": "text"}
        return self._band_request(
            "POST", f"/agent/chats/{self.room_id}/messages", json=payload
        )

    def _mark_processing(self, msg_id: str) -> bool:
        return (
            self._band_request(
                "POST",
                f"/agent/chats/{self.room_id}/messages/{msg_id}/processing",
            )
            is not None
        )

    def _mark_processed_api(self, msg_id: str) -> bool:
        return (
            self._band_request(
                "POST",
                f"/agent/chats/{self.room_id}/messages/{msg_id}/processed",
            )
            is not None
        )

    # ─── LLM Helper ───

    def _call_llm(self, user_message: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            res = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[ERROR] LLM call failed: {str(e)}"

    # ─── Mention & Routing Logic ───

    def _extract_mentions(self, text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r"@([A-Za-z0-9_]+)", text)

    def _should_handle(self, message: Dict) -> bool:
        text = message.get("content", "") or ""
        mentions = self._extract_mentions(text)

        my_clean = re.sub(r"[^a-zA-Z0-9]", "", self.name.lower())

        if mentions:
            for m in mentions:
                m_clean = re.sub(r"[^a-zA-Z0-9]", "", m.lower())
                if m_clean == my_clean or m_clean in my_clean or my_clean in m_clean:
                    return True
            return False

        return True

    def _is_from_self(self, message: Dict) -> bool:
        sender = message.get("sender", "") or ""
        sender_name = message.get("sender_name", "") or ""
        return self.name.lower() in (sender + sender_name).lower()

    # ─── Main Polling Loop ───

    def run(self):
        print(f"[{self.name}] Starting polling loop for room {self.room_id}")

        while True:
            try:
                messages = self._get_messages()

                if not messages:
                    self.consecutive_errors = 0
                    time.sleep(self.poll_interval)
                    continue

                for msg in messages:
                    msg_id = msg.get("id") or msg.get("message_id")
                    if not msg_id:
                        msg_id = str(hash(json.dumps(msg, sort_keys=True)))

                    if self._is_processed(msg_id):
                        continue

                    if self._is_from_self(msg):
                        self._mark_processed(msg_id)
                        continue

                    if not self._should_handle(msg):
                        self._mark_processed(msg_id)
                        continue

                    content = msg.get("content", "") or ""
                    print(f"[{self.name}] Handling: {content[:100]}...")

                    self._mark_processing(msg_id)

                    try:
                        reply = self._call_llm(content)
                    except Exception as e:
                        reply = f"[{self.name}] Error: {str(e)}"

                    sent = False
                    for attempt in range(self.max_retries + 1):
                        result = self._send_reply(reply)
                        if result is not None:
                            sent = True
                            print(f"[{self.name}] Reply sent successfully")
                            break
                        if attempt < self.max_retries:
                            time.sleep(2 ** attempt)

                    if not sent:
                        print(f"[{self.name}] Send failed after retries, marking processed anyway")

                    self._mark_processed_api(msg_id)
                    self._mark_processed(msg_id)

                self.consecutive_errors = 0

            except Exception as e:
                self.consecutive_errors += 1
                print(f"[{self.name}] Poll cycle error: {e}")

            backoff = min(self.poll_interval * (2 ** self.consecutive_errors), self.max_backoff)
            if self.consecutive_errors > 0:
                print(f"[{self.name}] Backing off {backoff}s (errors: {self.consecutive_errors})")
            time.sleep(backoff)
