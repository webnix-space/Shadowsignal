# ShadowSignal AI v2.0 — Fixed & Enhanced

## Autonomous GTM & Market Intelligence Multi-Agent Network

**Fixed version** with working Bright Data SERP API, proper error handling, and professional intelligence terminal UI.

---

## What Was Fixed

### 1. Bright Data "0 Results" / JSON Parse Error
**Root cause:** `resp.json()` crashed when Bright Data returned HTML/error page instead of JSON.
**Fix:** Added `_safe_json()` method that gracefully handles non-JSON responses, extracts raw HTML, and parses search results from the HTML content using regex patterns.

### 2. Backend 500 Errors (Railway Logs)
**Root cause:** `get_next_message` endpoint on Band API was returning 500 errors, causing all agents to crash.
**Fix:** Added fallback to `get_messages()` when `get_next_message` fails, with proper error logging and exponential backoff retry.

### 3. Frontend Crash (Vercel 500)
**Root cause:** The `api/index.py` was not properly structured as a Flask app for Vercel serverless.
**Fix:** Complete rewrite with proper Flask routes, error handling, embedded professional terminal UI, and demo data generation.

### 4. Agent Pipeline Breaks
**Root cause:** Loop detection was too aggressive, blocking upstream messages. Also, Bright Data failures caused the entire pipeline to halt.
**Fix:** Made loop detection agent-specific (only downstream agents skip). Added fallback to LLM knowledge when Bright Data fails.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SHADOWSIGNAL TERMINAL                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Terminal   │  │Intel Dash   │  │  Sources    │          │
│  │   Panel     │  │   Panel     │  │   Panel     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────┐
│                    FLASK BACKEND (Vercel)                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  /api/health  /api/analyze  /api/search  /api/stream │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              RAILWAY / LOCAL: AGENT NETWORK                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Investigator│  │  Analyst  │  │Strategist │  │Regulatory│  │
│  │  (Bright  │  │   (LLM)   │  │   (LLM)   │  │  (LLM)   │  │
│  │   Data)   │  │           │  │           │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│  ┌──────────┐                                              │
│  │ Codeband  │  (Workflow Control)                          │
│  └──────────┘                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ Bright  │  │ AI/ML   │  │  Band   │
        │  Data   │  │  API    │  │  API    │
        │ SERP API│  │         │  │         │
        └─────────┘  └─────────┘  └─────────┘
```

---

## File Structure

```
shadowsignal/
├── agents/
│   ├── base_agent.py      # FIXED: Loop detection, Bright Data, retry logic
│   ├── band_client.py     # FIXED: 500 error fallback, connection handling
│   ├── bright_data.py     # FIXED: JSON parse, HTML extraction, result parsing
│   ├── investigator.py    # FIXED: Real-time intel gathering
│   ├── analyst.py         # FIXED: Structured analysis output
│   ├── strategist.py      # FIXED: Counter-play strategy generation
│   ├── regulatory.py      # FIXED: Compliance risk assessment
│   ├── codeband.py        # FIXED: Workflow control, battle cards
│   └── run_all.py         # FIXED: Process management, auto-restart
├── api/
│   ├── index.py           # FIXED: Flask app + Terminal UI + API endpoints
│   └── band_bridge.py     # FIXED: Band API relay
├── requirements.txt       # FIXED: Dependencies
├── vercel.json           # FIXED: Serverless config
└── README.md
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BRIGHT_DATA_API_KEY` | Yes | Bright Data API token |
| `BRIGHT_DATA_ZONE` | Yes | SERP zone (e.g., `serp`) |
| `AIML_API_KEY` | Yes | AI/ML API key |
| `FEATHERLESS_API_KEY` | No | Featherless AI API key (backup) |
| `BAND_API_KEY` | Yes | Band Protocol API key |
| `BAND_ROOM_ID` | Yes | Band chat room ID |
| `*_API_KEY` | Yes | Per-agent Band API keys (INVESTIGATOR, ANALYST, etc.) |
| `POLL_INTERVAL_SECONDS` | No | Agent poll interval (default: 5) |
| `DATA_DIR` | No | SQLite DB directory (default: `/tmp`) |

---

## Quick Start

### 1. Deploy Frontend (Vercel)
```bash
vercel --prod
```

### 2. Run Agents (Railway / Local)
```bash
pip install -r requirements.txt
python agents/run_all.py
```

### 3. Test Bright Data
```bash
curl -X POST https://your-api.vercel.app/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "nvidia pricing 2026"}'
```

---

## Key Fixes Summary

| Issue | Fix |
|-------|-----|
| `BrightData Search error: Expecting value` | `_safe_json()` handles HTML responses |
| `Parsed 0 results` | Multi-pattern result extraction from HTML/markdown |
| `get_next_message failed: 500` | Fallback to `get_messages()` with retry |
| Frontend 500 crash | Complete Flask rewrite with embedded UI |
| Agent loop blocking | Agent-specific loop detection |
| Pipeline halts on Bright Data failure | LLM knowledge fallback |

---

## License

MIT License — Built for the Band Hackathon (May 2026)

