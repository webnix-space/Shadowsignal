from flask import Flask, jsonify, request, render_template_string
import os
import json
import requests
import concurrent.futures

# 🚨 VERCEL FIX: App instance defined instantly
app = Flask(__name__)

# --- BULLETPROOF IMPORTS ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: psycopg2 missing. Memory bank will run in volatile mode.")

# --- VERCEL ENVIRONMENT VARIABLES ---
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE")
AIML_API_KEY = os.getenv("AIML_API_KEY")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- 1. POSTGRESQL MEMORY CLUSTER ---
def init_db():
    if not DB_AVAILABLE or not DATABASE_URL: return
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

def save_to_memory(target, threat, summary):
    if not DB_AVAILABLE or not DATABASE_URL: return
    init_db()
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
    if not DB_AVAILABLE or not DATABASE_URL: 
        return [{"company": "System Alert", "time": "Now", "snippet": "Database missing. Running in RAM mode."}]
    init_db()
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
# --- UPDATE THESE AGENT FUNCTIONS IN api/index.py ---

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
        # INCREASED TIMEOUT to 60s
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        if res.status_code == 200: return res.json()['choices'][0]['message']['content'].strip()
        return f"THREAT: UNKNOWN | AI/ML Error {res.status_code}"
    except: return "THREAT: UNKNOWN | Connection timeout."

def agent_featherless_strategy(raw_web_context, target_company):
    if not FEATHERLESS_API_KEY: return '{"error": "Featherless API Key missing."}'
    url = "https://api.featherless.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {FEATHERLESS_API_KEY.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2", "max_tokens": 4096, "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You are an elite enterprise GTM AI. Return raw JSON with keys: \"executive_summary\", \"pricing_vulnerabilities\", \"recommended_sales_play\"."},
            {"role": "user", "content": f"Target: {target_company}\nData:\n{raw_web_context}"}
        ]
    }
    try:
        # INCREASED TIMEOUT to 90s
        res = requests.post(url, json=payload, headers=headers, timeout=90)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            content = content.replace("```json", "").replace("```", "").strip()
            return content
        return f'{{"error": "Featherless Error {res.status_code}"}}'
    except: return '{"error": "Featherless timeout. The model is busy."}'

# --- 3. THE LIVE TERMINAL UI ---

     # --- 3. PROFESSIONAL TERMINAL UI ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal | Enterprise Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #050505; color: #e5e7eb; font-family: 'Inter', system-ui, sans-serif; }
        .glass { background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(10px); border: 1px solid #1f2937; }
        .terminal { font-family: 'Monaco', 'Consolas', monospace; }
        .glow { box-shadow: 0 0 15px rgba(59, 130, 246, 0.2); }
    </style>
</head>
<body class="min-h-screen p-4 md:p-8">
    <div class="max-w-4xl mx-auto space-y-6">
        <div class="flex justify-between items-center border-b border-gray-800 pb-4">
            <div>
                <h1 class="text-xl font-bold text-white tracking-tighter">SHADOWSIGNAL<span class="text-blue-500">.AI</span></h1>
                <p class="text-[10px] text-gray-500 uppercase tracking-widest">Enterprise Intelligence Command</p>
            </div>
            <div id="statusBadge" class="px-3 py-1 bg-green-900/20 text-green-400 text-[10px] border border-green-900 rounded-full">SYSTEM READY</div>
        </div>

        <div class="glass p-4 rounded-xl flex gap-4">
            <input id="targetCompany" type="text" value="Microsoft" class="flex-1 bg-transparent border-none outline-none text-sm placeholder-gray-600" placeholder="Enter target competitor...">
            <button onclick="executeOrchestration()" id="actionButton" class="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold px-6 py-2 rounded-lg transition-all">EXECUTE</button>
        </div>

        <div id="liveTerminal" class="hidden glass p-4 rounded-xl">
            <div id="terminalStream" class="terminal text-[11px] text-gray-400 space-y-1 h-32 overflow-y-auto"></div>
        </div>

        <div id="outputDashboard" class="hidden grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="md:col-span-2 p-4 rounded-lg bg-gray-900/50 border border-gray-800">
                <div id="threatLevel" class="text-[10px] font-bold uppercase tracking-widest text-gray-400">Threat Level: Pending...</div>
            </div>
            <div class="p-4 rounded-lg bg-gray-900/30 border border-gray-800">
                <h4 class="text-[9px] font-bold text-blue-500 uppercase mb-2">Executive Summary</h4>
                <p id="summaryText" class="text-xs text-gray-300"></p>
            </div>
            <div class="p-4 rounded-lg bg-gray-900/30 border border-gray-800">
                <h4 class="text-[9px] font-bold text-red-500 uppercase mb-2">Vulnerabilities</h4>
                <p id="pricingText" class="text-xs text-gray-300"></p>
            </div>
            <div class="md:col-span-2 p-4 rounded-lg bg-blue-900/5 border border-blue-900/30">
                <h4 class="text-[9px] font-bold text-green-500 uppercase mb-2">Counter-Play Strategy</h4>
                <p id="playText" class="text-xs text-gray-300"></p>
            </div>
        </div>
    </div>

    <script>
        function log(msg) {
            const s = document.getElementById('terminalStream');
            s.innerHTML += `<div><span class="text-blue-500">></span> ${msg}</div>`;
            s.scrollTop = s.scrollHeight;
        }

        async function executeOrchestration() {
            const btn = document.getElementById('actionButton');
            const target = document.getElementById('targetCompany').value;
            const term = document.getElementById('liveTerminal');
            const dash = document.getElementById('outputDashboard');
            
            btn.disabled = true;
            btn.innerText = "PROCESSING...";
            term.classList.remove('hidden');
            dash.classList.add('hidden');
            document.getElementById('terminalStream').innerHTML = '';

            log("Establishing secure connection...");
            const scrape = await fetch('/api/scrape?target=' + encodeURIComponent(target)).then(r => r.json());
            if(scrape.error) return log("ERROR: " + scrape.error, true);
            
            log("Ingesting raw intelligence...");
            const ai = await fetch('/api/analyze', { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({target, raw_data: scrape.raw_data}) }).then(r => r.json());
            
            log("Finalizing strategic synthesis.");
            dash.classList.remove('hidden');
            document.getElementById('threatLevel').innerText = "Assessment: " + ai.aiml_sentiment;
            
            try {
                const data = JSON.parse(ai.featherless_strategy.replace(/```json|```/g, ''));
                document.getElementById('summaryText').innerText = data.executive_summary || "N/A";
                document.getElementById('pricingText').innerText = data.pricing_vulnerabilities || "N/A";
                document.getElementById('playText').innerText = (typeof data.recommended_sales_play === 'object') ? JSON.stringify(data.recommended_sales_play) : data.recommended_sales_play;
            } catch(e) { document.getElementById('summaryText').innerText = "Parse Error: Could not render strategy."; }
            
            btn.disabled = false;
            btn.innerText = "EXECUTE";
        }
    </script>
</body>
</html>
"""
                                
# --- 4. FLASK ROUTING & API ENDPOINTS ---

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def main_dashboard(path):
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/scrape', methods=['GET'])
def api_scrape():
    target = request.args.get('target', 'Microsoft')
    if not BRIGHT_DATA_API_KEY:
        return jsonify({"error": "Bright Data API Key missing."})
    
    # Use the direct API URL without manual proxy dictionaries
    url = "https://api.brightdata.com/request"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY.strip()}"
    }
    
    payload = {
        "zone": BRIGHT_DATA_ZONE.strip(),
        "url": f"https://www.google.com/search?q={target}+enterprise+pricing+competitive+strategy+changes&hl=en&gl=us",
        "format": "raw",
        "data_format": "parsed_light"
    }
    
    try:
        # Pass the payload as JSON, no proxy argument needed for the SERP API
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code == 200:
            data = res.json()
            # If the response is a list, it might be the top 10 results directly
            organic = data.get("organic", []) if isinstance(data, dict) else data
            
            if not organic: return jsonify({"error": "No organic results found."})
            
            snippets = [f"Title: {r.get('title')}\nLink: {r.get('link')}\nDescription: {r.get('description')}" for r in organic]
            raw_text = "\n\n".join(snippets)[:15000]
            return jsonify({"status": "success", "raw_data": raw_text, "bytes": len(raw_text)})
        return jsonify({"error": f"Bright Data SERP Error: {res.status_code} - {res.text}"})
    except Exception as e:
        return jsonify({"error": f"Bright Data Connection Error: {str(e)}"})

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    req_data = request.json
    target = req_data.get('target', 'Microsoft')
    raw_data = req_data.get('raw_data', '')
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_aiml = executor.submit(agent_aiml_sentiment, raw_data, target)
        future_feather = executor.submit(agent_featherless_strategy, raw_data, target)
        aiml_result = future_aiml.result()
        feather_result = future_feather.result()
    
    try:
        parsed = json.loads(feather_result)
        if "error" not in parsed:
            save_to_memory(target, aiml_result, parsed.get("executive_summary", ""))
    except: pass
        
    return jsonify({"aiml_sentiment": aiml_result, "featherless_strategy": feather_result})

@app.route('/api/history', methods=['GET'])
def history_endpoint():
    return jsonify({"logs": get_memory_logs()})
