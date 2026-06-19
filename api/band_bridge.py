"""
ShadowSignal Band Bridge — DEBUG VERSION
Tries multiple payload formats to find the correct one.
"""
import os
import requests
import json
import logging

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

    def _test_send(self, content: str) -> dict:
        """
        Try multiple payload formats until one succeeds.
        Logs each attempt for debugging.
        """
        test_payloads = [
            ("plain_string", content),
            ("text_field", {"text": content}),
            ("message_field", {"message": content}),
            ("body_field", {"body": content}),
            ("content_wrapped", {"content": {"text": content}}),
            ("message_object", {"message": {"text": content}}),
            ("data_field", {"data": content}),
        ]

        for name, payload in test_payloads:
            try:
                logger.info(f"[Bridge] Trying format '{name}': {json.dumps(payload)[:100]}...")
                
                resp = requests.post(
                    f"{BAND_BASE}/chats/{self.room_id}/messages",
                    headers=self.headers,
                    json=payload if not isinstance(payload, str) else None,
                    data=json.dumps(payload) if isinstance(payload, str) else None,
                    timeout=15,
                )

                if resp.status_code == 200:
                    logger.info(f"[Bridge] SUCCESS with format '{name}'!")
                    return resp.json()
                else:
                    error = resp.json() if resp.text else {}
                    logger.warning(f"[Bridge] Format '{name}' failed: {resp.status_code} - {error.get('error', {}).get('message', resp.text[:100])}")

            except Exception as e:
                logger.warning(f"[Bridge] Format '{name}' exception: {e}")

        logger.error("[Bridge] ALL formats failed!")
        return {"error": "all_formats_failed"}

    def trigger_workflow(self, target: str) -> str:
        message = f"@ShadowSignal Investigator analyze {target}"
        result = self._test_send(message)
        return result

    def poll_workflow(self, workflow_id: str, timeout: int = 120) -> dict:
        # Simplified for debug
        return {"status": "debug", "send_result": workflow_id}
