"""
ShadowSignal Frontend-Backend Bridge — AGENT API VERSION
Uses Band.ai Agent API with proper mentions format.
"""
import os
import requests
import time
import uuid
import logging
from datetime import datetime
from typing import Optional

BAND_API_KEY = os.getenv("BAND_API_KEY", "").strip()
BAND_ROOM_ID = os.getenv("BAND_ROOM_ID", "").strip()
BAND_BASE = "https://app.band.ai/api/v1/agent"

logger = logging.getLogger(__name__)


class BandChatBridge:
    def __init__(self):
        self.headers = {
            "X-API-Key": BAND_API_KEY,
            "Content-Type": "application/json",
        }
        self.room_id = BAND_ROOM_ID
        self.workflow_results = {
            "raw_intel": None,
            "analysis": None,
            "strategy": None,
            "audit": None,
            "deliverables": None,
            "status": "idle",
            "ledger": [],
        }
        # Cache for participant UUIDs
        self._participants_cache = None

    def _get_participants(self) -> list:
        """Get chat participants using Agent API."""
        if self._participants_cache:
            return self._participants_cache
            
        try:
            resp = requests.get(
                f"{BAND_BASE}/chats/{self.room_id}/participants",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, dict):
                participants = data.get("participants", []) or data.get("data", []) or []
            else:
                participants = data if isinstance(data, list) else []
            
            self._participants_cache = participants
            logger.info(f"[Bridge] Found {len(participants)} participants")
            return participants
            
        except Exception as e:
            logger.error(f"[Bridge] Failed to get participants: {e}")
            return []

    def _find_mention(self, agent_name: str) -> Optional[dict]:
        """Build mention object for agent."""
        participants = self._get_participants()
        
        for p in participants:
            name = p.get("name", "")
            if agent_name.lower() in name.lower():
                return {
                    "id": p.get("id") or p.get("uuid"),
                    "name": name,
                    "handle": p.get("handle", name.lower().replace(" ", "-"))
                }
        
        logger.error(f"[Bridge] Agent '{agent_name}' not found in participants")
        return None

    def _send_message(self, content: str, target_agent: str = "ShadowSignal Investigator") -> dict:
        """
        Agent API: POST /agent/chats/{id}/messages
        Payload: {"message": {"content": "...", "mentions": [{"id": "uuid", "name": "...", "handle": "..."}]}}
        """
        mention = self._find_mention(target_agent)
        
        if not mention:
            return {"error": "agent_not_found", "detail": f"{target_agent} not in chat room"}

        payload = {
            "message": {
                "content": content,
                "mentions": [mention]
            }
        }

        try:
            resp = requests.post(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=15,
            )

            if resp.status_code == 422:
                error_detail = resp.json() if resp.text else {}
                logger.error(f"[Bridge] 422: {error_detail}")
                return {"error": "validation_error", "detail": error_detail}

            if resp.status_code == 403:
                logger.error("[Bridge] 403 - Agent not in chat")
                return {"error": "forbidden", "detail": "Agent not participant in this chat"}

            if resp.status_code == 404:
                logger.error(f"[Bridge] 404 - Chat not found")
                return {"error": "not_found", "detail": "Chat does not exist for this agent"}

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            logger.error(f"[Bridge] Send failed: {e}")
            return {"error": "unknown", "detail": str(e)}

    def _get_messages(self, limit: int = 50) -> list:
        """Get messages using Agent API."""
        try:
            resp = requests.get(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                params={"limit": limit, "status": "all"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, dict):
                return data.get("messages", []) or data.get("data", []) or []
            return data if isinstance(data, list) else []
            
        except Exception as e:
            logger.error(f"[Bridge] Get messages failed: {e}")
            return []

    def trigger_workflow(self, target: str) -> str:
        """Trigger workflow by sending message with mention."""
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        self.workflow_results = {
            "raw_intel": None, "analysis": None, "strategy": None,
            "audit": None, "deliverables": None,
            "status": "running", "ledger": []
        }

        message = f"@ShadowSignal Investigator analyze {target}"
        resp = self._send_message(message, "ShadowSignal Investigator")

        if resp.get("error"):
            self.workflow_results["status"] = "error"
            self.workflow_results["ledger"].append({
                "timestamp": datetime.now().isoformat(),
                "agent": "SYSTEM",
                "action": "ERROR",
                "data": f"{resp['error']}: {resp.get('detail', '')}"
            })
            return workflow_id

        self.workflow_results["ledger"].append({
            "timestamp": datetime.now().isoformat(),
            "agent": "SYSTEM",
            "action": "TRIGGER_SENT",
            "data": f"Request sent for {target}"
        })
        return workflow_id

    def poll_workflow(self, workflow_id: str, timeout: int = 120) -> dict:
        """Poll for agent responses."""
        if self.workflow_results.get("status") == "error":
            return self.workflow_results

        start_time = time.time()
        agents_found = set()

        while time.time() - start_time < timeout:
            messages = self._get_messages(limit=100)

            if not messages:
                self.workflow_results["status"] = "demo_mode"
                return self.workflow_results

            for agent_name, key in [
                ("ShadowSignal Investigator", "raw_intel"),
                ("ShadowSignal Analyst", "analysis"),
                ("ShadowSignal Strategist", "strategy"),
                ("ShadowSignal Regulatory", "audit"),
                ("ShadowSignal Codeband", "deliverables"),
            ]:
                if key in agents_found:
                    continue

                for msg in reversed(messages):
                    sender = msg.get("sender") or msg.get("author") or {}
                    name = sender.get("name", "") if isinstance(sender, dict) else str(sender)
                    
                    if agent_name.lower() in name.lower():
                        content = (
                            msg.get("content")
                            or msg.get("message", {}).get("content")
                            or msg.get("text", "")
                        )
                        if content and len(str(content)) > 50:
                            self.workflow_results[key] = str(content)
                            agents_found.add(key)
                            break

            if len(agents_found) >= 4:
                self.workflow_results["status"] = "complete"
                break

            time.sleep(3)

        if self.workflow_results["status"] == "running":
            self.workflow_results["status"] = "timeout"

        return self.workflow_results
