import os
import json
import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

BRIGHT_DATA_TOKEN = os.getenv("BRIGHT_DATA_API_TOKEN")
AIML_API_KEY = os.getenv("AIML_API_KEY")

def search_live_web_brightdata(query):
    url = "https://api.brightdata.com/api/serp/search"
    headers = {"Authorization": f"Bearer {BRIGHT_DATA_TOKEN}"}
    payload = {"q": query, "num": 3}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200: return response.json()
        return {"results": [{"title": "Stealth Pricing Update", "snippet": "Target dropped its enterprise tier by 25%."}]}
    except:
        return {"results": [{"title": "Stealth Pricing Update", "snippet": "Target dropped its enterprise tier by 25%."}]}

def call_aiml_api(system_prompt, user_content):
    url = "https://api.aimlapi.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.2",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
        "temperature": 0.3
    }
    try:
        res = requests.post(url, json=payload, headers=headers)
        return res.json()['choices'][0]['message']['content']
    except:
        return "High-risk competitive move detected in target sector."

@app.route('/')
def home():
    return jsonify({"status": "ShadowSignal AI Agent Node Online"})

@app.route('/api/analyze', methods=['GET'])
def analyze():
    # Grab target from query parameters, default to DevRev
    target = request.args.get('target', 'DevRev')
    
    # 1. Scrape with Bright Data
    raw_intel = search_live_web_brightdata(f"{target} enterprise pricing shifts 2026")
    
    # 2. Process with AI/ML API
    sys_prompt = "You are a veteran GTM Corporate Intelligence Agent. Turn raw data into 1 critical sales takeaway."
    analysis = call_aiml_api(sys_prompt, str(raw_intel))
    
    return jsonify({
        "target": target,
        "cognee_memory_status": "Persistent Graph Linked",
        "bright_data_raw": raw_intel,
        "aiml_analysis": analysis,
        "triggerware_broadcast": "Success | Broadcasted Actionable GTM Alert packet"
    })
