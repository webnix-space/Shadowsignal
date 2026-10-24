# ShadowSignal

Competitive-intelligence terminal. Enter a company, get an impact score, grounded findings,
three counter-play strategies, a compliance audit, and a source list.

One Vercel deployment. No separate backend, no database, no message bus.

## How it works

`POST /api/analyze` runs five agents in sequence inside a single serverless function:

| Agent | What it does |
|---|---|
| Investigator | Gathers sources from Google News RSS and DuckDuckGo (no API keys) |
| Analyst | Groq LLM scores impact/threat and extracts findings, citing sources by number |
| Strategist | Groq LLM proposes three counter-play strategies |
| Regulatory | Groq LLM audits the strategies for legal and compliance risk |
| Codeband | Deterministic gate: blocks the workflow on HIGH or CRITICAL risk |

Findings are constrained to the retrieved sources. If no sources are found, the API returns
an error instead of inventing output.

## Deploy

1. Import the repo into Vercel.
2. Set one environment variable: `GROQ_API_KEY` (optional: `GROQ_MODEL`; otherwise `openai/gpt-oss-120b` then `openai/gpt-oss-20b`, then auto-discovery).
3. Deploy. Open `/api/health` to confirm `groq_api: true`.

## Layout

```
api/index.py        Flask app: UI route, /api/health, /api/agents/status, /api/analyze
api/_pipeline.py    The agent pipeline
api/_free_data.py   Google News RSS + DuckDuckGo
api/_ui.py          Terminal UI (HTML/CSS/JS)
vercel.json         60 s function timeout, catch-all rewrite
```

Files starting with `_` are helpers; Vercel does not deploy them as separate functions.

## Limits

- Sources are public news headlines and snippets, not scraped pricing pages. Treat output as a
  starting brief, not verified fact.
- The endpoint is public and spends your Groq quota. Add rate limiting before sharing widely.
- Runs on Vercel's function limits; a full run makes three LLM calls.

MIT License
