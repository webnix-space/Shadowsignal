"""
ShadowSignal API Bridge — Frontend to Band.ai Agent Backend
Sends trigger messages and polls for agent responses.
FIXED: Never self-mention. Sends plain text or mentions next agent only.
FIXED: Properly polls for real agent responses with better diagnostics.
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
        self._participants_cache = None
        self._self_id = None

    def _get_participants(self) -> list:
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
        """Find mention for target agent, excluding self."""
        participants = self._get_participants()
        
        for p in participants:
            p_id = p.get("id") or p.get("uuid") or ""
            name = p.get("name", "")
            
            # Skip self
            if self._self_id and p_id == self._self_id:
                continue
            
            if agent_name.lower() in name.lower():
                return {
                    "id": p_id,
                    "name": name,
                    "handle": p.get("handle", name.lower().replace(" ", "-"))
                }
        
        return None

    def _discover_self(self) -> Optional[str]:
        """Discover own agent ID by testing mentions."""
        if self._self_id:
            return self._self_id
            
        participants = self._get_participants()
        for p in participants:
            p_id = p.get("id") or p.get("uuid") or ""
            name = p.get("name", "")
            if not p_id:
                continue
                
            test_payload = {
                "message": {
                    "content": "test",
                    "mentions": [{
                        "id": p_id,
                        "name": name or "test",
                        "handle": p.get("handle", "")
                    }]
                }
            }
            try:
                test_resp = requests.post(
                    f"{BAND_BASE}/chats/{self.room_id}/messages",
                    headers=self.headers,
                    json=test_payload,
                    timeout=5,
                )
                if test_resp.status_code == 422 and "cannot_mention_self" in test_resp.text:
                    self._self_id = p_id
                    logger.info(f"[Bridge] Discovered self: {name} ({p_id})")
                    return p_id
            except Exception:
                pass
        
        return None

    def _send_plain_message(self, content: str) -> dict:
        """Send message without mentions (broadcast to room)."""
        payload = {"message": {"content": content}}
        
        try:
            resp = requests.post(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[Bridge] Plain message failed: {e}")
            return {"error": "send_failed", "detail": str(e)}

    def _send_message_with_mention(self, content: str, target_agent: str) -> dict:
        """Send message with mention to specific agent."""
        mention = self._find_mention(target_agent)
        
        if not mention:
            return {"error": "agent_not_found", "detail": f"{target_agent} not in chat room"}

        payload = {
            "message": {
                "content": content,
                "mentions": [mention]
            }
        }

        logger.info(f"[Bridge] Sending to {target_agent} (id={mention['id']})")

        try:
            resp = requests.post(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=15,
            )

            if resp.status_code == 422:
                error_detail = resp.json() if resp.text else {}
                err_msg = error_detail.get("error", {}).get("message", "") if isinstance(error_detail, dict) else str(error_detail)
                
                if "cannot_mention_self" in err_msg:
                    self._self_id = mention["id"]
                    logger.warning(f"[Bridge] Detected self as '{target_agent}' (id={mention['id']}). Cannot mention self.")
                    return {"error": "cannot_mention_self", "detail": f"Bridge is {target_agent}"}
                
                logger.error(f"[Bridge] 422: {error_detail}")
                return {"error": "validation_error", "detail": error_detail}

            if resp.status_code == 403:
                return {"error": "forbidden", "detail": "Agent not participant in this chat"}
            if resp.status_code == 404:
                return {"error": "not_found", "detail": "Chat does not exist for this agent"}

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            logger.error(f"[Bridge] Send failed: {e}")
            return {"error": "unknown", "detail": str(e)}

    def _get_messages(self, limit: int = 50) -> list:
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
        """Trigger workflow by sending appropriate message."""
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        self.workflow_results = {
            "raw_intel": None, "analysis": None, "strategy": None,
            "audit": None, "deliverables": None,
            "status": "running", "ledger": []
        }

        # Discover self first
        self._discover_self()
        
        first_agent = "ShadowSignal Investigator"
        
        # Check if we ARE the investigator
        is_self_investigator = False
        if self._self_id and self._participants_cache:
            for p in self._participants_cache:
                p_id = p.get("id") or p.get("uuid") or ""
                name = p.get("name", "")
                if p_id == self._self_id and first_agent.lower() in name.lower():
                    is_self_investigator = True
                    break

        if is_self_investigator:
            # === FIX: Send PLAIN message (no mention) so the REAL investigator agent picks it up ===
            # The real investigator.py agent (separate process with INVESTIGATOR_API_KEY) 
            # will see this message and process it with Bright Data
            message = f"Please analyze {target} and provide competitive intelligence"
            logger.info(f"[Bridge] Sending PLAIN message (bridge IS {first_agent}, real agent will pick it up)")
            resp = self._send_plain_message(message)
        else:
            # Can mention normally
            message = f"@ShadowSignal Investigator analyze {target}"
            resp = self._send_message_with_mention(message, first_agent)

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
        if self.workflow_results.get("status") == "error":
            return self.workflow_results

        start_time = time.time()
        agents_found = set()
        poll_count = 0

        while time.time() - start_time < timeout:
            messages = self._get_messages(limit=100)
            poll_count += 1

            if not messages:
                logger.warning(f"[Bridge] Poll #{poll_count}: No messages yet, waiting...")
                time.sleep(3)
                continue

            logger.info(f"[Bridge] Poll #{poll_count}: Got {len(messages)} messages")

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
                            logger.info(f"[Bridge] Found {key} from {name} ({len(str(content))} chars)")
                            break

            if len(agents_found) >= 4:
                self.workflow_results["status"] = "complete"
                break

            time.sleep(3)

        if self.workflow_results["status"] == "running":
            logger.warning(f"[Bridge] Timeout after {timeout}s. Agents found: {agents_found}")
            self.workflow_results["status"] = "timeout"

        return self.workflow_results
