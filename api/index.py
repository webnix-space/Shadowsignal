"""
ShadowSignal: single Vercel deployment (Flask serverless function).
Serves the terminal UI and runs the agent pipeline in-request.
Env: GROQ_API_KEY (required), GROQ_MODEL (optional).
"""
import logging
import os
import sys
from datetime import datetime
from urllib.parse import parse_qs, urlencode

from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pipeline import run_pipeline, PipelineError  # noqa: E402
from _ui import TERMINAL_HTML  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [API] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


class VercelPathFix:
    """Vercel rewrites every request to /api/index and loses the original path.
    vercel.json passes it back as ?path=..., restore it here."""

    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "").rstrip("/") == "/api/index":
            qs = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            original = qs.pop("path", ["/"])[0] or "/"
            environ["PATH_INFO"] = original if original.startswith("/") else "/" + original
            environ["QUERY_STRING"] = urlencode(qs, doseq=True)
        return self.wsgi(environ, start_response)


app.wsgi_app = VercelPathFix(app.wsgi_app)

AGENTS = [
    ("investigator", "Investigator", "Data Gathering"),
    ("analyst", "Analyst", "Intelligence Analysis"),
    ("strategist", "Strategist", "Strategy Generation"),
    ("regulatory", "Regulatory", "Compliance Check"),
    ("codeband", "Codeband", "Workflow Gate"),
]


@app.route("/")
def index():
    return render_template_string(TERMINAL_HTML)


@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "version": "4.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {"free_data": True, "groq_api": bool(os.environ.get("GROQ_API_KEY", "").strip())},
    })


@app.route("/api/agents/status")
def agents_status():
    return jsonify({
        "agents": [{"id": i, "name": "ShadowSignal " + n, "status": "online", "role": r} for i, n, r in AGENTS],
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    target = str(data.get("target", "")).strip()
    if not target:
        return jsonify({"error": "Target is required"}), 400
    try:
        return jsonify(run_pipeline(target, str(data.get("mode", "comprehensive"))))
    except PipelineError as e:
        logger.warning("Pipeline error: %s", e)
        return jsonify({"error": str(e)}), e.status
    except Exception:
        logger.exception("Unhandled pipeline failure")
        return jsonify({"error": "Internal error"}), 500
