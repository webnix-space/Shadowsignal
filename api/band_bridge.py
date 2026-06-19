"""
ShadowSignal Frontend-Backend Bridge — FIXED
Connects the Vercel frontend to the Band chat agent workflow.
FIXED: Hardcoded agent UUIDs for mentions (403 on participants endpoint)
FIXED: Mandatory mentions array in message payload
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

# HARDCODED: Agent UUIDs from your Band dashboard
# Replace these with actual UUIDs from your chat room participants
AGENT_IDS = {
    "ShadowSignal Investigator": os.getenv("INVESTIGATOR_ID", ""),
    "ShadowSignal Analyst": os.getenv("ANALYST_ID", ""),
    "ShadowSignal Strategist": os.getenv("STRATEGIST_ID", ""),
    "ShadowSignal Regulatory": os.getenv("REGULATORY_ID", ""),
    "ShadowSignal Codeband": os.getenv("CODEBAND_ID", ""),
}


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

    def _build_mention(self, agent_name: str) -> Optional[dict]:
        """Build mention object from hardcoded agent IDs."""
        agent_id = AGENT_IDS.get(agent_name, "")
        if not agent_id:
            logger.error(f"[Bridge] No UUID configured for agent: {agent_name}")
            return None
        
        # Derive handle from name (lowercase, hyphenated)
        handle = agent_name.lower().replace(" ", "-")
        
        return {
            "id": agent_id,
            "name": agent_name,
            "handle": handle
        }

    def _send_message(self, content: str, target_agent: str = "ShadowSignal Investigator") -> dict:
        """
        FIXED: Uses correct Band.ai Agent API format with mandatory mentions.
        Payload: {"message": {"content": "...", "mentions": [{"id": "uuid", "name": "...", "handle": "..."}]}}
        """
        mention = self._build_mention(target_agent)
        
        if not mention:
            logger.error(f"[Bridge] Cannot send message: missing agent UUID for {target_agent}")
            return {"error": "missing_agent_id", "detail": f"Configure {target_agent} UUID in env vars"}

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
                logger.error(f"[Bridge] 422 Validation Error: {error_detail}")
                return {"error": "validation_error", "detail": error_detail}

            if resp.status_code == 403:
                logger.error("[Bridge] 403 Forbidden - Agent not in chat or wrong permissions")
                return {"error": "forbidden"}

            if resp.status_code == 401:
                logger.error("[Bridge] 401 Unauthorized - Invalid API key")
                return {"error": "unauthorized"}

            if resp.status_code == 404:
                logger.error(f"[Bridge] 404 - Chat room {self.room_id} not found")
                return {"error": "not_found"}

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            logger.error("[Bridge] Request timeout")
            return {"error": "timeout"}
        except Exception as e:
            logger.error(f"[Bridge] Failed to send message: {e}")
            return {"error": "unknown", "detail": str(e)}

    def _get_messages(self, limit: int = 50) -> list:
        """Get recent messages from Band chat room."""
        try:
            resp = requests.get(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                params={"limit": limit, "status": "all"},
                timeout=10,
            )

            if resp.status_code == 403:
                logger.warning("[Bridge] 403 reading messages - using fallback")
                return []
            if resp.status_code == 404:
                logger.warning(f"[Bridge] Chat {self.room_id} not found")
                return []

            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                return data.get("messages", []) or data.get("data", []) or []
            return data if isinstance(data, list) else []

        except Exception as e:
            logger.error(f"[Bridge] Failed to get messages: {e}")
            return []

    def _extract_agent_content(self, messages: list, agent_name: str) -> Optional[str]:
        """Extract latest message content from a specific agent."""
        for msg in reversed(messages):
            sender = msg.get("sender") or msg.get("author") or {}
            name = sender.get("name", "") if isinstance(sender, dict) else str(sender)

            if agent_name.lower() in name.lower():
                content = (
                    msg.get("content")
                    or msg.get("message", {}).get("content")
                    or msg.get("text", "")
                    or msg.get("body", "")
                )
                return str(content) if content else None
        return None

    def trigger_workflow(self, target_competitor: str) -> str:
        """Trigger 5-agent workflow by sending message to Band chat."""
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        self.workflow_results = {
            "raw_intel": None,
            "analysis": None,
            "strategy": None,
            "audit": None,
            "deliverables": None,
            "status": "running",
            "ledger": [],
        }

        self.workflow_results["ledger"].append({
            "timestamp": datetime.now().isoformat(),
            "agent": "SYSTEM",
            "action": "WORKFLOW_START",
            "data": f"Initializing 5-agent Band workflow for {target_competitor}"
        })

        # Send message with @mention to trigger agent
        message = f"@ShadowSignal Investigator analyze {target_competitor}"
        resp = self._send_message(message, target_agent="ShadowSignal Investigator")

        if resp.get("error"):
            error_type = resp.get("error")
            self.workflow_results["status"] = "error"
            self.workflow_results["ledger"].append({
                "timestamp": datetime.now().isoformat(),
                "agent": "SYSTEM",
                "action": "ERROR",
                "data": f"Band API {error_type}: {resp.get('detail', 'Unknown')}"
            })
            return workflow_id

        self.workflow_results["ledger"].append({
            "timestamp": datetime.now().isoformat(),
            "agent": "SYSTEM",
            "action": "TRIGGER_SENT",
            "data": f"Sent analysis request for {target_competitor}"
        })

        return workflow_id

    def poll_workflow(self, workflow_id: str, timeout: int = 120) -> dict:
        """Poll Band chat room for agent responses."""
        if self.workflow_results.get("status") == "error":
            return self.workflow_results

        start_time = time.time()
        agents_found = set()

        while time.time() - start_time < timeout:
            messages = self._get_messages(limit=100)

            if not messages:
                logger.info("[Bridge] No messages readable - switching to demo mode")
                self.workflow_results["status"] = "demo_mode"
                return self.workflow_results

            for agent_name, context_key in [
                ("ShadowSignal Investigator", "raw_intel"),
                ("ShadowSignal Analyst", "analysis"),
                ("ShadowSignal Strategist", "strategy"),
                ("ShadowSignal Regulatory", "audit"),
                ("ShadowSignal Codeband", "deliverables"),
            ]:
                if context_key in agents_found:
                    continue

                content = self._extract_agent_content(messages, agent_name)
                if content and len(content) > 50:
                    self.workflow_results[context_key] = content
                    agents_found.add(context_key)

                    action_map = {
                        "raw_intel": "INTEL_DEPOSITED",
                        "analysis": "ANALYSIS_COMPLETE",
                        "strategy": "STRATEGIES_GENERATED",
                        "audit": "AUDIT_COMPLETE",
                        "deliverables": "DELIVERABLES_READY",
                    }

                    self.workflow_results["ledger"].append({
                        "timestamp": datetime.now().isoformat(),
                        "agent": agent_name.replace("ShadowSignal ", ""),
                        "action": action_map.get(context_key, "RESPONSE"),
                        "data": f"{len(content)} chars received"
                    })

            if len(agents_found) >= 4:
                self.workflow_results["status"] = "complete"
                break

            time.sleep(3)

        if self.workflow_results["status"] == "running":
            self.workflow_results["status"] = "timeout"

        return self.workflow_results
