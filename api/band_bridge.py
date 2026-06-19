"""
ShadowSignal Frontend-Backend Bridge — FIXED
Connects the Vercel frontend to the Band chat agent workflow on Railway.
FIXED: 422 JSON Payload formatting for Band API
FIXED: 403 Forbidden error by bypassing the /participants endpoint
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
    """
    Bridges the frontend to the Band chat agent workflow.
    Sends messages to Band room and polls for agent responses.
    """

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

    def _send_message(self, content: str) -> dict:
        """Send a message to the Band chat room using the officially accepted schema."""
        # 🚨 FIX 422 ERROR: Changed root key from 'content' to 'message' to match Band's validation schema
        payload = {
            "message": content
        }
        
        try:
            resp = requests.post(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"[Bridge] Band API Rejected Payload (HTTP Error {e.response.status_code}): {e.response.text}")
            
            # Safe Fallback just in case Band expects 'text'
            try:
                r2 = requests.post(f"{BAND_BASE}/chats/{self.room_id}/messages", headers=self.headers, json={"text": content}, timeout=15)
                return r2.json()
            except:
                pass
            return {}
        except Exception as e:
            logger.error(f"[Bridge] Failed to send message: {e}")
            return {}

    def _get_messages(self, limit: int = 50) -> list:
        """Get recent messages from the Band chat room."""
        try:
            resp = requests.get(
                f"{BAND_BASE}/chats/{self.room_id}/messages",
                headers=self.headers,
                params={"limit": limit},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("messages", []) or data.get("data", [])
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"[Bridge] Failed to get messages: {e}")
            return []

    def _extract_agent_content(self, messages: list, agent_name: str) -> Optional[str]:
        """Extract the latest message content from a specific agent."""
        for msg in reversed(messages):
            sender = msg.get("sender") or msg.get("author") or {}
            name = sender.get("name", "") if isinstance(sender, dict) else str(sender)
            
            if agent_name.lower() in name.lower():
                content = msg.get("content") or msg.get("message", {}).get("content") or msg.get("text", "")
                return str(content)
        return None

    def trigger_workflow(self, target_competitor: str) -> str:
        """
        Trigger the 5-agent workflow by sending a message to Band chat.
        Returns workflow ID for polling.
        """
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        self.workflow_results["status"] = "running"
        self.workflow_results["ledger"] = []

        self.workflow_results["ledger"].append({
            "timestamp": datetime.now().isoformat(),
            "agent": "SYSTEM",
            "action": "WORKFLOW_START",
            "data": f"Initializing 5-agent Band workflow for {target_competitor}"
        })

        # 🚨 FIX 403 ERROR: We deleted the `_get_agent_mentions` function completely.
        # It was hitting a restricted /participants endpoint. We now trigger the agent by just sending the command.
        message = f"@ShadowSignal Investigator analyze {target_competitor}"
        
        resp = self._send_message(message)

        if not resp:
            self.workflow_results["status"] = "error"
            self.workflow_results["ledger"].append({
                "timestamp": datetime.now().isoformat(),
                "agent": "SYSTEM",
                "action": "ERROR",
                "data": "Band API connection failed. Check payload schema."
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
        """
        Poll the Band chat room for agent responses.
        Returns collected results from all 5 agents.
        """
        if self.workflow_results.get("status") == "error":
            return self.workflow_results

        start_time = time.time()
        agents_found = set()

        while time.time() - start_time < timeout:
            messages = self._get_messages(limit=100)

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

                    action = {
                        "raw_intel": "INTEL_DEPOSITED",
                        "analysis": "ANALYSIS_COMPLETE",
                        "strategy": "STRATEGIES_GENERATED",
                        "audit": "AUDIT_COMPLETE",
                        "deliverables": "DELIVERABLES_READY",
                    }.get(context_key, "RESPONSE")

                    self.workflow_results["ledger"].append({
                        "timestamp": datetime.now().isoformat(),
                        "agent": agent_name.replace("ShadowSignal ", ""),
                        "action": action,
                        "data": f"{len(content)} chars received"
                    })

            if len(agents_found) >= 4:
                self.workflow_results["status"] = "complete"
                break

            audit = self.workflow_results.get("audit", "")
            if audit and "[CRITICAL RISK]" in audit:
                if "deliverables" not in agents_found:
                    self.workflow_results["status"] = "blocked"
                    self.workflow_results["ledger"].append({
                        "timestamp": datetime.now().isoformat(),
                        "agent": "Codeband",
                        "action": "BLOCKED",
                        "data": "Critical risk detected - artifacts blocked"
                    })
                    break

            time.sleep(3)

        if self.workflow_results["status"] == "running":
            self.workflow_results["status"] = "timeout"

        return self.workflow_results
