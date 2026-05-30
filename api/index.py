```python
import os
import json
import requests
import psycopg2
import concurrent.futures
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# --- VERCEL ENVIRONMENT VARIABLES ---
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE")
AIML_API_KEY = os.getenv("AIML_API_KEY")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- 1. POSTGRESQL MEMORY CLUSTER ---
def init_db():
    if not DATABASE_URL: return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS intel_logs (
                id SERIAL PRIMARY KEY,
                target_company VARCHAR(100) NOT NULL,
                threat_level VARCHAR(255),
                executive_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except: pass

init_db()

def save_to_memory(target, threat, summary):
    if not DATABASE_URL: return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO intel_logs (target_company, threat_level, executive_summary) VALUES (%s, %s, %s);",
            (target, threat, summary)
        )
        conn.commit()
        cur.close()
        conn.close()
    except: pass

def get_memory_logs():
    if not DATABASE_URL: 
        return [{"company": "System Alert", "time": "Now", "snippet": "PostgreSQL DATABASE_URL not set in Vercel. Memory offline."}]
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT target_company, created_at, threat_level FROM intel_logs ORDER BY id DESC LIMIT 15;")
        logs = cur.fetchall()
        cur.close()
        conn.close()
        return [{"company": l[0], "time": l[1].strftime("%H:%M %b %d"), "snippet": l[2][:50]} for l in logs]
    except Exception as e:
        return [{"company": "DB Error", "time": "Now", "snippet": str(e)[:50]}]


# --- 2. MULTI-AGENT COGNITIVE LAYER ---
def agent_aiml_sentiment(raw_web_context, target_company):
    if not AIML_API_KEY: return "THREAT: ERROR | AIML API Key missing."
    url = "https://api.aimlapi.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {AIML_API_KEY.strip()}", "Content-Type": "application/json"}
    prompt = "Evaluate the data. Output ONLY a single line: [THREAT LEVEL] | [10-word summary]. Threat Level must be CRITICAL, ELEVATED, or LOW."
    
    payload = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", 
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": f"Target: {target_company}\nData: {raw_web_context[:4000]}"}],
        "temperature": 0.3
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200: return res.json()['choices'][0]['message']['content'].strip()
        return "THREAT: UNKNOWN | AI/ML API unavailable."
    except: return "THREAT: UNKNOWN | Connection timeout."

def agent_featherless_strategy(raw_web_context, target_company):
    if not FEATHERLESS_API_KEY: return '{"error": "Featherless API Key missing."}'
    url = "https://api.featherless.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {FEATHERLESS_API_KEY.strip()}", "Content-Type": "application/json"}
    prompt = (
        "You are an elite enterprise GTM AI. Analyze the Google search data. "
        "Format response STRICTLY as raw JSON with keys: \"executive_summary\", \"pricing_vulnerabilities\", \"recommended_sales_play\". "
        "Values must be single plain-text paragraphs. NO Markdown."
    )
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2", "max_tokens": 4096, "temperature": 0.2,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": f"Target: {target_company}\nData:\n{raw_web_context}"}]
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=35)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if content.startswith("


```
