"""
ShadowSignal Pay — Nanopayment module for Circle Arc Testnet.
Every LLM call triggers a real USDC micropayment on ARC-TESTNET.
Track 4: Best Agentic Economy Experience on Arc.
"""
import logging
import os
import time
import requests
import uuid

logger = logging.getLogger(__name__)

CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY", "")
CIRCLE_WALLET_ID = os.getenv("CIRCLE_WALLET_ID", "c363f82d-2f21-565d-8825-89ca87f79380")

PAYMENT_AMOUNTS = {
    "web_scrape": "0.005",
    "llm_call":   "0.002",
    "analysis":   "0.003",
    "strategy":   "0.003",
    "compliance": "0.002",
    "report":     "0.001",
}

RECIPIENT_ADDRESS = "0x9fcf22efa1dbf96fd95f753c01c1b839db1fee37"
CIRCLE_API_BASE = "https://api.circle.com/v1/w3s"
TOKEN_ID = "ef87c8c3-85de-598a-af50-c5135eecfa74"


def fire_nanopayment(agent_name: str, action: str = "llm_call") -> dict:
    if not CIRCLE_API_KEY:
        logger.warning("[NanoPay] CIRCLE_API_KEY not set — skipping")
        return {"status": "skipped"}

    amount = PAYMENT_AMOUNTS.get(action, "0.001")

    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "walletId": CIRCLE_WALLET_ID,
        "tokenId": TOKEN_ID,
        "destinationAddress": RECIPIENT_ADDRESS,
        "amounts": [amount],
        "fee": {"type": "level", "config": {"feeLevel": "MEDIUM"}}
    }

    headers = {
        "Authorization": f"Bearer {CIRCLE_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{CIRCLE_API_BASE}/developer/transactions/transfer",
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        tx_id = data.get("data", {}).get("id", "unknown")
        tx_state = data.get("data", {}).get("state", "unknown")
        logger.info(f"[NanoPay] ✅ {agent_name} | {action} | {amount} USDC | tx={tx_id}")
        return {"status": "success", "tx_id": tx_id, "amount": amount, "agent": agent_name}
    except Exception as e:
        logger.error(f"[NanoPay] ❌ Failed: {e}")
        return {"status": "error", "reason": str(e)}


def get_balance() -> str:
    if not CIRCLE_API_KEY:
        return "unknown"
    headers = {"Authorization": f"Bearer {CIRCLE_API_KEY}"}
    try:
        resp = requests.get(
            f"{CIRCLE_API_BASE}/wallets/{CIRCLE_WALLET_ID}/balances",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        balances = resp.json().get("data", {}).get("tokenBalances", [])
        for b in balances:
            if b.get("token", {}).get("symbol") == "USDC" and not b.get("token", {}).get("isNative"):
                return b.get("amount", "0")
        return "0"
    except Exception as e:
        logger.error(f"[NanoPay] Balance check failed: {e}")
        return "error"
