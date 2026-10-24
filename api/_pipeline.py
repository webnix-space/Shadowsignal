"""
ShadowSignal pipeline: five agents run in one request, in sequence.

  1. Investigator  - gathers sources (Google News RSS + DuckDuckGo). No LLM.
  2. Analyst       - LLM: scores impact/threat and extracts findings from the sources.
  3. Strategist    - LLM: three counter-play strategies from the analysis.
  4. Regulatory    - LLM: compliance audit of the strategies.
  5. Codeband      - deterministic gate: blocks the workflow on HIGH/CRITICAL risk.

Only GROQ_API_KEY is required.
"""
import json
import logging
import os
import re
import time
from datetime import datetime

import requests

from _free_data import get_competitive_intel, format_sources_for_llm

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
# Free-tier chat models as of Oct 2026. Env GROQ_MODEL (optional) is tried first.
DEFAULT_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
_NON_CHAT = ("whisper", "tts", "guard", "safeguard", "embed", "playai", "orpheus")
_MODEL_PREF = ("gpt-oss", "llama-3.3", "llama-4", "qwen", "kimi", "llama")
_cache = {"models": None}

THREATS = ("low", "medium", "high", "critical")
TRENDS = ("up", "down", "stable")
RISKS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

MODE_FOCUS = {
    "comprehensive": "pricing, security, contracts, supply, market position",
    "pricing": "pricing changes, tier changes, discounts, cost impact",
    "security": "vulnerabilities, breaches, compliance and trust issues",
    "contract": "contract terms, renewals, lock-in, negotiation leverage",
    "supply": "availability, capacity, lead times, supply chain",
    "market": "market share, partnerships, acquisitions, product moves",
}

GROUNDING = (
    "Use ONLY the numbered sources provided. Cite them like [1] or [2][4]. "
    "Never invent prices, percentages, dates, CVE ids or quotes. "
    "If the sources do not support a claim, do not make it. Reply with JSON only."
)


class PipelineError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def _api_error(resp) -> str:
    try:
        return str(resp.json().get("error", {}).get("message", ""))[:200] or resp.text[:200]
    except ValueError:
        return resp.text[:200]


def _discover_models(headers, exclude) -> list:
    """Ask Groq which chat models this key can use right now."""
    try:
        r = requests.get(GROQ_MODELS_URL, headers=headers, timeout=10)
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
    except (requests.RequestException, ValueError, KeyError):
        return []
    ids = [i for i in ids if i not in exclude and not any(b in i.lower() for b in _NON_CHAT)]
    ids.sort(key=lambda i: next((n for n, p in enumerate(_MODEL_PREF) if p in i), 99))
    return ids


def _groq_json(system: str, user: str) -> dict:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise PipelineError("GROQ_API_KEY is not set on the server.", 503)
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    # Groq's JSON mode requires the word "json" in the messages.
    user = user + "\n\nRespond with a single valid json object and nothing else."

    if _cache["models"] is None:
        env = os.environ.get("GROQ_MODEL", "").strip()
        _cache["models"] = ([env] if env else []) + [m for m in DEFAULT_MODELS if m != env]
    queue = list(_cache["models"])
    tried, errors, discovered = set(), [], False

    while True:
        if not queue:
            if discovered:
                break
            discovered = True
            queue = _discover_models(headers, tried)
            if queue:
                logger.info("Discovered Groq models: %s", queue[:5])
            continue
        model = queue.pop(0)
        tried.add(model)
        base = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.3,
            "max_tokens": 4096,  # reasoning models spend tokens before the json
        }
        strict = dict(base, response_format={"type": "json_object"})
        if model.startswith("openai/gpt-oss"):
            strict["reasoning_effort"] = "low"
        # variant 1: json mode. variant 2: plain request (parsed by us) if json mode is rejected
        gone = False
        for variant, payload in (("json-mode", strict), ("plain", base)):
            for attempt in range(2):
                try:
                    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=40)
                    if resp.status_code == 404:
                        errors.append("%s: %s" % (model, _api_error(resp)))
                        gone = True
                        break
                    if resp.status_code == 400:
                        errors.append("%s[%s]: %s" % (model, variant, _api_error(resp)))
                        break  # try the next variant
                    if resp.status_code == 429:
                        errors.append("%s: rate limited" % model)
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    data = _parse_json(resp.json()["choices"][0]["message"]["content"] or "")
                    _cache["models"] = [model] + [m for m in _cache["models"] if m != model]
                    return data
                except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                    errors.append("%s[%s]: %s" % (model, variant, str(e)[:120]))
                    time.sleep(0.8)
            if gone:
                break
    logger.warning("All Groq models failed: %s", errors)
    raise PipelineError("LLM call failed. " + " | ".join(errors[-4:])[:500])


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
    except ValueError:
        i, j = text.find("{"), text.rfind("}")  # json wrapped in prose
        if i == -1 or j <= i:
            raise
        data = json.loads(text[i:j + 1])
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _enum(v, allowed, default):
    v = str(v or "").strip()
    for a in allowed:
        if v.lower() == a.lower():
            return a
    return default


def _str_list(v, limit):
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        if isinstance(x, dict):
            x = " ".join(str(i) for i in x.values())
        x = str(x).strip()
        if x:
            out.append(x[:400])
    return out[:limit]


def analyst(target, mode, sources_text):
    system = (
        "You are the Analyst agent in a competitive-intelligence system. " + GROUNDING +
        ' Return {"impact_score": 0-100, "trend": "up|down|stable", '
        '"threat_level": "low|medium|high|critical", "confidence": 0-100, '
        '"key_findings": [3-5 strings, each ending with its source refs]}. '
        "Confidence must reflect how well the sources support the findings."
    )
    user = "Target: %s\nFocus: %s\n\nSOURCES:\n%s" % (target, MODE_FOCUS.get(mode, MODE_FOCUS["comprehensive"]), sources_text)
    d = _groq_json(system, user)
    findings = _str_list(d.get("key_findings"), 5)
    if not findings:
        raise PipelineError("Analyst returned no findings.")
    return {
        "impact_score": _int(d.get("impact_score"), 0, 100, 50),
        "trend": _enum(d.get("trend"), TRENDS, "stable"),
        "threat_level": _enum(d.get("threat_level"), THREATS, "medium"),
        "confidence": _int(d.get("confidence"), 0, 100, 50),
        "key_findings": findings,
    }


def strategist(target, analysis):
    system = (
        "You are the Strategist agent. Propose exactly 3 lawful counter-play strategies for a "
        "company competing against the target, based only on the findings given. Do not invent "
        "ROI figures or statistics. Rank best first. "
        'Return {"strategies": [{"name": str, "action": str, "timeline_weeks": int, "risk": "low|medium|high"}]}.'
    )
    user = "Target: %s\nThreat: %s | Impact: %s/100\nFindings:\n- %s" % (
        target, analysis["threat_level"], analysis["impact_score"], "\n- ".join(analysis["key_findings"]))
    d = _groq_json(system, user)
    items = d.get("strategies")
    strategies = []
    if isinstance(items, list):
        for s in items[:3]:
            if not isinstance(s, dict):
                continue
            name = str(s.get("name", "")).strip()[:80]
            action = str(s.get("action", "")).strip()[:300]
            if not (name and action):
                continue
            weeks = _int(s.get("timeline_weeks"), 1, 52, 8)
            risk = _enum(s.get("risk"), ("low", "medium", "high"), "medium")
            strategies.append({"name": name, "action": action, "weeks": weeks, "risk": risk})
    if not strategies:
        raise PipelineError("Strategist returned no usable strategies.")
    return strategies


def regulatory(strategies):
    system = (
        "You are the Regulatory agent. Audit the strategies for anti-trust, predatory pricing, "
        "privacy (GDPR/CCPA), misrepresentation and unfair competition risk. "
        'Return {"compliance_risk": "LOW|MEDIUM|HIGH|CRITICAL", "compliance_details": [3-6 short strings]}. '
        "Name the strategy each issue applies to. Use HIGH or CRITICAL only for concrete legal exposure."
    )
    user = "Strategies:\n" + "\n".join("%d. %s: %s" % (i, s["name"], s["action"]) for i, s in enumerate(strategies, 1))
    d = _groq_json(system, user)
    details = _str_list(d.get("compliance_details"), 6)
    return _enum(d.get("compliance_risk"), RISKS, "MEDIUM"), details


def codeband(risk, details):
    """Deterministic workflow gate."""
    blocked = risk in ("HIGH", "CRITICAL")
    if blocked:
        details = ["WARNING: WORKFLOW BLOCKED. Human compliance review required before acting."] + details
    return blocked, details


def run_pipeline(target: str, mode: str = "comprehensive") -> dict:
    target = re.sub(r"\s+", " ", target).strip()[:80]
    if not target:
        raise PipelineError("Target is required.", 400)
    mode = mode if mode in MODE_FOCUS else "comprehensive"

    intel = get_competitive_intel(target)
    sources = intel["sources"]
    if not sources:
        raise PipelineError("No public sources found for '%s'. Try a more specific name." % target, 404)

    analysis = analyst(target, mode, format_sources_for_llm(sources))
    strategies = strategist(target, analysis)
    risk, details = regulatory(strategies)
    blocked, details = codeband(risk, details)

    return {
        "target": target,
        "mode": mode,
        "timestamp": datetime.utcnow().isoformat(),
        "impact_score": analysis["impact_score"],
        "trend": analysis["trend"],
        "threat_level": analysis["threat_level"],
        "confidence": analysis["confidence"],
        "key_findings": analysis["key_findings"],
        "recommended_actions": [
            "%s: %s (%d wks, %s risk)" % (s["name"], s["action"], s["weeks"], s["risk"]) for s in strategies
        ],
        "sources": [{k: s[k] for k in ("title", "url", "source", "snippet")} for s in sources],
        "compliance_risk": risk,
        "compliance_details": details,
        "workflow_blocked": blocked,
    }
