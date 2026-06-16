import time
import json
import os
import re
import sqlite3
from datetime import datetime

class BasePollingAgent:
    """
    BasePollingAgent: A resilient polling agent for Band.ai with:
    - Message deduplication (persistent SQLite)
    - Exponential backoff on errors
    - Idempotent reply emission
    - Graceful degradation on Band.ai 500s
    """

    def __init__(self, band_client, chat_id, agent_name, poll_interval=5):
        self.band_client = band_client
        self.chat_id = chat_id
        self.agent_name = agent_name
        self.poll_interval = poll_interval

        # Persistent deduplication store
        self.db_path = f"/tmp/shadowsignal_{agent_name.lower().replace(' ', '_')}_processed.db"
        self._init_db()

        # Retry state
        self.consecutive_errors = 0
        self.max_backoff = 60  # seconds
        self.max_retries_per_message = 1

        # Message tracking in-memory cache (faster than DB for hot path)
        self._processed_cache = set()
        self._load_cache()

    def _init_db(self):
        """Initialize SQLite DB for persistent message deduplication."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS processed_messages (
                msg_id TEXT PRIMARY KEY,
                processed_at TEXT,
                agent_name TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def _load_cache(self):
        """Load recently processed IDs into memory cache."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Load last 1000 to keep memory reasonable
        c.execute(
            "SELECT msg_id FROM processed_messages WHERE agent_name = ? ORDER BY processed_at DESC LIMIT 1000",
            (self.agent_name,)
        )
        self._processed_cache = {row[0] for row in c.fetchall()}
        conn.close()

    def _is_processed(self, msg_id):
        """Check if message was already processed (cache + DB)."""
        if msg_id in self._processed_cache:
            return True
        # Double-check DB in case cache was cleared
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT 1 FROM processed_messages WHERE msg_id = ? AND agent_name = ?", (msg_id, self.agent_name))
        result = c.fetchone() is not None
        conn.close()
        return result

    def _mark_processed(self, msg_id):
        """Mark message as processed persistently."""
        if msg_id in self._processed_cache:
            return

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute(
                "INSERT OR IGNORE INTO processed_messages (msg_id, processed_at, agent_name) VALUES (?, ?, ?)",
                (msg_id, datetime.utcnow().isoformat(), self.agent_name)
            )
            conn.commit()
            self._processed_cache.add(msg_id)
        except Exception as e:
            print(f"[{self.agent_name}] DB error marking processed: {e}")
        finally:
            conn.close()

    def _get_backoff_time(self):
        """Calculate exponential backoff based on consecutive errors."""
        backoff = min(self.poll_interval * (2 ** self.consecutive_errors), self.max_backoff)
        return backoff

    def _extract_mentions(self, text):
        """Extract @AgentName mentions from message text."""
        if not text:
            return []
        mentions = re.findall(r'@([A-Za-z0-9_]+)', text)
        return mentions

    def _should_handle(self, message):
        """
        Determine if this agent should handle the message.
        Handles if:
        - Message mentions this agent by name
        - Message has no mentions (broadcast)
        - Message is from a human user
        """
        text = message.get("content", "") or ""
        mentions = self._extract_mentions(text)

        # Clean agent name for matching (remove spaces, case insensitive)
        my_name_clean = self.agent_name.lower().replace(" ", "")

        # If mentions exist, only handle if we're mentioned
        if mentions:
            for m in mentions:
                if m.lower().replace(" ", "") == my_name_clean:
                    return True
            return False

        # No mentions = broadcast or human message — handle it
        return True

    def _clean_message_text(self, text):
        """Remove @mentions from message text before processing."""
        return re.sub(r'@[A-Za-z0-9_]+\s*', '', text).strip()

    def handle_message(self, message):
        """
        OVERRIDE THIS in subclasses.
        Returns: (reply_text, event_payload) or None to skip replying.
        """
        raise NotImplementedError("Subclasses must implement handle_message()")

    def poll_and_reply(self):
        """
        Single poll cycle with full error handling and deduplication.
        """
        try:
            messages = self.band_client.get_messages(self.chat_id)

            if not messages:
                self.consecutive_errors = 0
                return

            for msg in messages:
                msg_id = msg.get("id") or msg.get("message_id") or str(hash(json.dumps(msg, sort_keys=True)))

                # DEDUPLICATION: Skip if already processed
                if self._is_processed(msg_id):
                    continue

                # Check if we should handle this message
                if not self._should_handle(msg):
                    self._mark_processed(msg_id)
                    continue

                # Process the message
                clean_text = self._clean_message_text(msg.get("content", ""))
                print(f"[{self.agent_name}] Handling message: {clean_text[:80]}...")

                try:
                    result = self.handle_message(msg)
                except Exception as e:
                    print(f"[{self.agent_name}] Error in handle_message: {e}")
                    result = None

                # Send reply if we have one
                if result:
                    reply_text, event_payload = result if isinstance(result, tuple) else (result, None)

                    # Try to send reply (with limited retries)
                    sent = False
                    for attempt in range(self.max_retries_per_message):
                        try:
                            response = self.band_client.send_message(
                                self.chat_id,
                                reply_text,
                                event_payload=event_payload
                            )
                            if response is not None:
                                sent = True
                                print(f"[{self.agent_name}] Reply sent successfully")
                                break
                            else:
                                print(f"[{self.agent_name}] Send returned None (likely 500), attempt {attempt+1}")
                        except Exception as e:
                            print(f"[{self.agent_name}] Send error: {e}")

                        if attempt < self.max_retries_per_message - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff between retries

                    if not sent:
                        print(f"[{self.agent_name}] FAILED to send after {self.max_retries_per_message} attempts. Marking processed anyway to prevent spam.")

                # ALWAYS mark as processed, even if send failed
                # This prevents infinite loops on Band.ai 500 errors
                self._mark_processed(msg_id)

            # Reset error counter on success
            self.consecutive_errors = 0

        except Exception as e:
            self.consecutive_errors += 1
            print(f"[{self.agent_name}] Poll cycle error: {e}")

    def run(self):
        """Main loop with adaptive backoff."""
        print(f"[{self.agent_name}] Starting polling loop for chat {self.chat_id}")

        while True:
            self.poll_and_reply()

            # Adaptive sleep with exponential backoff on errors
            sleep_time = self._get_backoff_time()
            if self.consecutive_errors > 0:
                print(f"[{self.agent_name}] Backing off for {sleep_time}s (errors: {self.consecutive_errors})")
            time.sleep(sleep_time)
