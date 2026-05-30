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
def agent_aiml_sentiment(raw_web_context, target_company):
    if not AIML_API_KEY: return "THREAT: ERROR | AIML API Key missing."
    url = "[https://api.aimlapi.com/v1/chat/completions](https://api.aimlapi.com/v1/chat/completions)"
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
    url = "[https://api.featherless.ai/v1/chat/completions](https://api.featherless.ai/v1/chat/completions)"
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
            # FIXED: Safe copy-paste string replacement
            content = content.replace("```json", "").replace("```", "").strip()
            return content
        return f'{{"error": "Featherless API Error {res.status_code}"}}'
    except: return '{"error": "Featherless timeout."}'


# --- 3. THE LIVE TERMINAL UI ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal Elite - Command Center</title>
    <script src="[https://cdn.tailwindcss.com](https://cdn.tailwindcss.com)"></script>
    <style>
        body { background-color: #08090d; color: #cbd5e1; font-family: ui-sans-serif, system-ui; }
        .glass-panel { background: rgba(18, 20, 30, 0.7); border: 1px solid rgba(255, 255, 255, 0.05); backdrop-filter: blur(12px); }
        .glow-purple { box-shadow: 0 0 30px rgba(168, 85, 247, 0.15); }
        .pulse-border { animation: pulse-border 2s infinite; }
        @keyframes pulse-border { 0% { border-color: rgba(168, 85, 247, 0.3); } 50% { border-color: rgba(168, 85, 247, 1); } 100% { border-color: rgba(168, 85, 247, 0.3); } }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        
        .terminal-text { font-family: 'Courier New', Courier, monospace; color: #4ade80; }
        @keyframes fade-in { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fade-in 0.3s ease-out forwards; }
    </style>
</head>
<body class="min-h-screen flex flex-col h-screen overflow-hidden">

    <!-- Top Status Bar -->
    <div class="w-full bg-[#0d0f16] border-b border-gray-800 px-6 py-2.5 flex justify-between items-center text-[10px] uppercase tracking-widest text-gray-400 z-10">
        <div class="flex items-center space-x-6">
            <div class="flex items-center space-x-2">
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span class="font-bold text-gray-300">Live Crawl:</span> <span class="text-emerald-400">Bright Data SERP</span>
            </div>
            <div class="flex items-center space-x-2">
                <span class="w-2 h-2 rounded-full bg-blue-500"></span>
                <span class="font-bold text-gray-300">Memory DB:</span> <span class="text-blue-400">PostgreSQL</span>
            </div>
        </div>
        <div class="hidden md:flex gap-4 font-mono">
            <span>Agent 1: <span class="text-purple-400">Nemotron-30B</span></span>
            <span>Agent 2: <span class="text-purple-400">DeepSeek-V3.2</span></span>
        </div>
    </div>

    <div class="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 p-4 md:p-6 overflow-hidden">
        
        <!-- Sidebar -->
        <div class="lg:col-span-1 flex flex-col h-full overflow-hidden">
            <div class="glass-panel rounded-xl p-5 flex flex-col h-full border border-gray-800">
                <h2 class="text-xs font-bold uppercase tracking-wider text-blue-400 mb-4 flex items-center justify-between border-b border-gray-800 pb-3">
                    <span>🧠 Memory Bank Logs</span>
                </h2>
                <div id="historyContainer" class="flex flex-col gap-3 overflow-y-auto pr-2 flex-1">
                    <p class="text-xs text-gray-500 italic animate-pulse">Syncing with DB...</p>
                </div>
            </div>
        </div>

        <!-- Central Matrix -->
        <div class="lg:col-span-3 flex flex-col gap-6 h-full overflow-y-auto pb-10 pr-2">
            
            <div class="glass-panel rounded-xl p-6 glow-purple border border-purple-900/30">
                <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
                    <div class="flex-1">
                        <label class="block text-[10px] font-bold uppercase text-gray-400 tracking-widest mb-2">Target Competitor</label>
                        <input id="targetCompany" type="text" value="Microsoft" class="w-full bg-[#141622] border border-gray-700 rounded-lg px-4 py-3.5 text-white text-sm focus:outline-none focus:border-purple-500 transition-colors font-semibold">
                    </div>
                    <button onclick="executeOrchestration()" id="actionButton" class="bg-purple-600 hover:bg-purple-700 text-white font-bold px-8 py-3.5 rounded-lg text-sm tracking-wide transition-all shadow-lg shadow-purple-900/50 w-full md:w-auto">
                        Execute Live Scan
                    </button>
                </div>
            </div>

            <!-- LIVE TERMINAL -->
            <div id="liveTerminal" class="hidden glass-panel border border-gray-800 rounded-xl p-4">
                <div class="flex items-center gap-2 mb-2">
                    <span class="w-3 h-3 rounded-full bg-red-500"></span>
                    <span class="w-3 h-3 rounded-full bg-yellow-500"></span>
                    <span class="w-3 h-3 rounded-full bg-green-500"></span>
                    <span class="text-[10px] text-gray-500 font-bold uppercase ml-2 tracking-widest">Live Pipeline Log</span>
                </div>
                <div id="terminalStream" class="terminal-text text-xs whitespace-pre-wrap flex flex-col gap-1.5 h-24 overflow-y-auto">
                </div>
            </div>

            <!-- Dashboard Result Cards -->
            <div id="outputDashboard" class="hidden flex-col gap-6">
                <div id="sentimentBlock" class="glass-panel p-5 rounded-xl border border-gray-700 flex flex-col md:flex-row items-center justify-between gap-4">
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
                    <div class="bg-[#11131e] border border-blue-500/20 rounded-xl p-6 shadow-lg">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-[10px] font-bold uppercase text-blue-400 tracking-wider">Executive Summary</span>
                            <span class="text-xl">📊</span>
                        </div>
                        <p id="summaryText" class="text-sm text-gray-300 leading-relaxed"></p>
                    </div>

                    <div class="bg-[#11131e] border border-red-500/20 rounded-xl p-6 shadow-lg">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-[10px] font-bold uppercase text-red-400 tracking-wider">Pricing Vulnerabilities</span>
                            <span class="text-xl">🎯</span>
                        </div>
                        <p id="pricingText" class="text-sm text-gray-300 leading-relaxed"></p>
                    </div>

                    <div class="bg-[#11131e] border border-emerald-500/30 rounded-xl p-6 shadow-xl shadow-emerald-900/10">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-[10px] font-bold uppercase text-emerald-400 tracking-wider">Recommended Counter-Play</span>
                            <span class="text-xl">⚡</span>
                        </div>
                        <p id="playText" class="text-sm text-white font-medium leading-relaxed"></p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        window.onload = refreshHistoryList;

        function logTerminal(message, isError = false) {
            const stream = document.getElementById('terminalStream');
            const color = isError ? 'text-red-400' : 'text-emerald-400';
            stream.innerHTML += `<div class="${color} animate-fade-in">> ${message}</div>`;
            stream.scrollTop = stream.scrollHeight;
        }

        async function refreshHistoryList() {
            try {
                const res = await fetch('/api/history');
                const data = await res.json();
                const box = document.getElementById('historyContainer');
                
                if (data.logs && data.logs.length > 0) {
                    box.innerHTML = data.logs.map(log => `
                        <div class="bg-[#141622] border border-gray-800 p-3.5 rounded-lg hover:border-blue-500/40 transition-colors">
                            <div class="flex justify-between items-center mb-2">
                                <span class="text-xs font-bold text-white">${log.company}</span>
                                <span class="text-[9px] text-gray-500 font-mono">${log.time}</span>
                            </div>
                            <p class="text-[10px] text-gray-400 font-mono leading-tight">${log.snippet}</p>
                        </div>
                    `).join('');
                } else {
                     box.innerHTML = `<p class="text-xs text-gray-500 italic">No historical traces detected.</p>`;
                }
            } catch(e) {}
        }

        async function executeOrchestration() {
            const target = document.getElementById('targetCompany').value;
            const btn = document.getElementById('actionButton');
            const dash = document.getElementById('outputDashboard');
            const term = document.getElementById('liveTerminal');
            
            btn.disabled = true;
            btn.className = "bg-gray-800 text-gray-500 font-bold px-8 py-3.5 rounded-lg text-sm tracking-wide cursor-not-allowed w-full md:w-auto";
            btn.innerText = "Running Live Pipeline...";
            dash.classList.add('hidden');
            
            term.classList.remove('hidden');
            document.getElementById('terminalStream').innerHTML = '';
            
            logTerminal(`Initializing connection to Bright Data Proxy Network...`);
            logTerminal(`Target Domain: ${target} [Enterprise Pricing Data]`);

            try {
                // STEP 1: SCRAPE
                logTerminal(`Executing SERP query via api.brightdata.com...`);
                const scrapeRes = await fetch(`/api/scrape?target=${encodeURIComponent(target)}`);
                const scrapeData = await scrapeRes.json();
                
                if (scrapeData.error) {
                    logTerminal(`CRITICAL ERROR: ${scrapeData.error}`, true);
                    throw new Error("Scrape failed.");
                }

                logTerminal(`Bypassed Google CAPTCHA. Organic results retrieved.`);
                logTerminal(`Data parsed: ${scrapeData.bytes || 'Multiple'} bytes of live competitive intel.`);
                logTerminal(`Routing structured payload to AI/ML & Featherless AI clusters concurrently...`);

                dash.classList.remove('hidden');
                document.getElementById('sentimentBlock').className = "glass-panel p-5 rounded-xl border pulse-border flex items-center justify-center";
                document.getElementById('sentimentBlock').innerHTML = `<span class="text-xs text-purple-400 font-bold animate-pulse">Running AI Inference (Nemotron + DeepSeek)...</span>`;
                ['summaryText', 'pricingText', 'playText'].forEach(id => {
                    document.getElementById(id).innerHTML = `<span class="animate-pulse text-gray-600">Awaiting AI logic processing...</span>`;
                });

                // STEP 2: AI ORCHESTRATION
                const aiRes = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target: target, raw_data: scrapeData.raw_data })
                });
                const output = await aiRes.json();
                
                logTerminal(`AI Inference Complete. Outputting cards.`);

                let threatColor = "text-yellow-400";
                if(output.aiml_sentiment.includes("CRITICAL") || output.aiml_sentiment.includes("HIGH")) threatColor = "text-red-500";
                if(output.aiml_sentiment.includes("LOW")) threatColor = "text-emerald-400";
                
                document.getElementById('sentimentBlock').className = "glass-panel p-5 rounded-xl border border-gray-700 flex flex-col md:flex-row items-center justify-between gap-4";
                document.getElementById('sentimentBlock').innerHTML = `
                    <div class="flex flex-col">
                        <span class="text-[10px] font-bold tracking-widest text-gray-500 uppercase mb-1">Nemotron-30B Fast-Pass Analysis</span>
                        <span class="text-sm font-bold ${threatColor}">${output.aiml_sentiment}</span>
                    </div>
                `;

                try {
                    const strategy = JSON.parse(output.featherless_strategy);
                    if (strategy.error) throw new Error(strategy.error);
                    
                    document.getElementById('summaryText').innerText = strategy.executive_summary || "No data.";
                    document.getElementById('pricingText').innerText = strategy.pricing_vulnerabilities || "No data.";
                    document.getElementById('playText').innerText = strategy.recommended_sales_play || "No data.";
                } catch(e) {
                    document.getElementById('summaryText').innerText = "Parser Error: " + output.featherless_strategy;
                }
                
                logTerminal(`Saving intelligence run to PostgreSQL database...`);
                setTimeout(refreshHistoryList, 1500); 
                logTerminal(`Pipeline successfully closed.`);

            } catch (error) {
                logTerminal(`System Error: ${error.message}`, true);
            } finally {
                btn.disabled = false;
                btn.className = "bg-purple-600 hover:bg-purple-700 text-white font-bold px-8 py-3.5 rounded-lg text-sm tracking-wide transition-all shadow-lg shadow-purple-900/50 w-full md:w-auto";
                btn.innerText = "Execute Live Scan";
            }
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
