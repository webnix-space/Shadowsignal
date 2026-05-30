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

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    print("Warning: resend missing. Email alerts disabled.")

# --- VERCEL ENVIRONMENT VARIABLES ---
if RESEND_AVAILABLE:
    resend.api_key = os.getenv("RESEND_API_KEY")
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE")
AIML_API_KEY = os.getenv("AIML_API_KEY")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

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
    except Exception as e:
        print(f"DB Init Error: {e}")

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
    except Exception as e:
        print(f"DB Save Error: {e}")

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

def send_automated_alert(target, threat_level, summary):
    if not RESEND_AVAILABLE or not os.getenv('RESEND_API_KEY'):
        print("Email alert skipped: Resend not configured")
        return
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": "ShadowSignal AI <onboarding@resend.dev>",
        "to": ALERT_EMAIL or "admin@shadowsignal.ai",
        "subject": f"CRITICAL THREAT DETECTED: {target}",
        "html": f"<h1>Intelligence Alert</h1><p><b>Target:</b> {target}</p><p><b>Threat Level:</b> {threat_level}</p><p><b>Summary:</b> {summary}</p>"
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"Email alert failed: {e}")

def agent_nemotron_sentiment(raw_web_context, target_company):
    """Agent 1: NVIDIA Nemotron-3 - Threat Assessment & Sentiment Analysis"""
    if not AIML_API_KEY: 
        return "THREAT: ERROR | AIML API Key missing."
    url = "https://api.aimlapi.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {AIML_API_KEY.strip()}", "Content-Type": "application/json"}
    prompt = "Evaluate the competitive intelligence data. Output ONLY a single line: [THREAT LEVEL] | [10-word summary]. Threat Level must be CRITICAL, ELEVATED, or LOW."

    payload = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", 
        "messages": [
            {"role": "system", "content": prompt}, 
            {"role": "user", "content": f"Target: {target_company}\nData: {raw_web_context[:4000]}"}
        ],
        "temperature": 0.3
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        if res.status_code == 200: 
            return res.json()['choices'][0]['message']['content'].strip()
        return f"THREAT: UNKNOWN | Nemotron Error {res.status_code}"
    except Exception as e:
        return f"THREAT: UNKNOWN | Nemotron Connection Error: {str(e)}"

def agent_deepseek_strategy(raw_web_context, target_company):
    """Agent 2: DeepSeek-V3.2 - GTM Strategy & Vulnerability Analysis"""
    if not FEATHERLESS_API_KEY: 
        return '{"error": "DeepSeek API Key missing."}'
    url = "https://api.featherless.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {FEATHERLESS_API_KEY.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2", 
        "max_tokens": 4096, 
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You are an elite enterprise GTM AI. Return raw JSON with keys: \"executive_summary\", \"pricing_vulnerabilities\", \"recommended_sales_play\"."},
            {"role": "user", "content": f"Target: {target_company}\nData:\n{raw_web_context}"}
        ]
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=90)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            content = content.replace("```json", "").replace("```", "").strip()
            return content
        return f'{{"error": "DeepSeek Error {res.status_code}"}}'
    except Exception as e:
        return f'{{"error": "DeepSeek timeout: {str(e)}"}}'

# --- 3. OPTIMIZED TERMINAL UI WITH DUAL AGENT DASHBOARD ---

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal | Enterprise Intel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body { background: #050505; color: #a1a1aa; font-family: 'Inter', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .glass { background: rgba(10, 10, 10, 0.85); border: 1px solid #1f2937; backdrop-filter: blur(12px); }
        .glass-card { background: rgba(15, 15, 15, 0.9); border: 1px solid #262626; }
        .agent-nemotron { border-left: 3px solid #76b900; }
        .agent-deepseek { border-left: 3px solid #4f46e5; }
        .gradient-text { background: linear-gradient(90deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .pulse-dot { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: .5; }
        }
        .terminal-line { opacity: 0; animation: fadeIn 0.3s ease-in forwards; }
        @keyframes fadeIn { to { opacity: 1; } }
        .status-critical { color: #ef4444; border-color: #7f1d1d; background: rgba(127, 29, 29, 0.2); }
        .status-elevated { color: #f59e0b; border-color: #78350f; background: rgba(120, 53, 15, 0.2); }
        .status-low { color: #10b981; border-color: #064e3b; background: rgba(6, 78, 59, 0.2); }
        .loading-spinner {
            border: 2px solid #1f2937;
            border-top: 2px solid #3b82f6;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
        <!-- Header -->
        <div class="flex justify-between items-end border-b border-gray-800 pb-6">
            <div>
                <h1 class="text-3xl font-bold text-white tracking-tighter">SHADOWSIGNAL<span class="text-blue-500">.AI</span></h1>
                <p class="text-xs text-gray-500 uppercase tracking-widest mt-1">Dual-Agent Competitive Intelligence</p>
            </div>
            <div class="text-right space-y-2">
                <div id="status" class="text-emerald-500 text-[10px] font-bold uppercase border border-emerald-900 bg-emerald-900/10 px-3 py-1 rounded-full inline-flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 pulse-dot"></span>
                    System Ready
                </div>
                <div class="text-[10px] text-gray-600 font-mono">v2.0 | Nemotron + DeepSeek</div>
            </div>
        </div>

        <!-- Input Section -->
        <div class="glass p-6 rounded-2xl flex flex-col md:flex-row gap-4 items-center">
            <div class="flex-1 w-full">
                <label class="text-[10px] text-gray-500 uppercase tracking-wider mb-1 block">Target Company</label>
                <input id="targetCompany" type="text" value="Microsoft" 
                    class="w-full bg-transparent border-b border-gray-700 outline-none text-white p-2 placeholder-gray-600 focus:border-blue-500 transition-colors font-mono text-sm"
                    placeholder="Enter competitor name...">
            </div>
            <button onclick="executeOrchestration()" id="actionButton" 
                class="bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs px-8 py-4 rounded-xl transition-all flex items-center gap-2">
                <span id="btnText">EXECUTE ANALYSIS</span>
                <div id="btnSpinner" class="loading-spinner hidden"></div>
            </button>
        </div>

        <!-- Workspace -->
        <div id="workspace" class="hidden space-y-6">
            <!-- Terminal -->
            <div class="glass p-4 rounded-xl">
                <div class="flex justify-between items-center mb-3">
                    <span class="text-[10px] text-gray-500 uppercase tracking-wider">Execution Log</span>
                    <span class="text-[10px] text-gray-600 font-mono">real-time</span>
                </div>
                <div id="terminal" class="font-mono text-[11px] text-gray-400 h-32 overflow-y-auto space-y-1 bg-black/40 p-3 rounded-lg"></div>
            </div>

            <!-- Agent Status Grid -->
            <div id="agentStatus" class="hidden grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="glass-card p-5 rounded-xl agent-nemotron">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-[#76b900]/20 flex items-center justify-center">
                                <span class="text-[#76b900] text-xs font-bold">N</span>
                            </div>
                            <div>
                                <div class="text-xs font-bold text-white">Agent 1: Nemotron-3</div>
                                <div class="text-[10px] text-gray-500">Threat Assessment</div>
                            </div>
                        </div>
                        <div id="nemotronStatus" class="text-[10px] text-gray-500">Waiting...</div>
                    </div>
                    <div id="nemotronResult" class="text-xs text-gray-300 font-mono min-h-[40px]"></div>
                </div>

                <div class="glass-card p-5 rounded-xl agent-deepseek">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-[#4f46e5]/20 flex items-center justify-center">
                                <span class="text-[#4f46e5] text-xs font-bold">D</span>
                            </div>
                            <div>
                                <div class="text-xs font-bold text-white">Agent 2: DeepSeek-V3.2</div>
                                <div class="text-[10px] text-gray-500">GTM Strategy</div>
                            </div>
                        </div>
                        <div id="deepseekStatus" class="text-[10px] text-gray-500">Waiting...</div>
                    </div>
                    <div id="deepseekResult" class="text-xs text-gray-300 font-mono min-h-[40px]"></div>
                </div>
            </div>

            <!-- Dashboard Results -->
            <div id="dashboard" class="hidden grid grid-cols-1 lg:grid-cols-12 gap-6">
                <!-- Threat Assessment Banner -->
                <div class="lg:col-span-12 glass p-6 rounded-2xl border-l-4" id="threatBanner">
                    <div class="flex items-center justify-between">
                        <div>
                            <div id="threatLevel" class="text-[10px] font-bold uppercase mb-2 tracking-wider">Assessment</div>
                            <p id="summaryText" class="text-sm text-gray-300"></p>
                        </div>
                        <div id="threatBadge" class="px-4 py-2 rounded-lg text-xs font-bold border"></div>
                    </div>
                </div>

                <!-- Vulnerabilities -->
                <div class="lg:col-span-4 glass p-6 rounded-2xl border-t border-red-500/30">
                    <h4 class="text-[10px] font-bold text-red-500 uppercase mb-3 tracking-wider">Pricing Vulnerabilities</h4>
                    <p id="pricingText" class="text-xs leading-relaxed text-gray-400"></p>
                </div>

                <!-- Strategy -->
                <div class="lg:col-span-8 glass p-6 rounded-2xl border-t border-emerald-500/30">
                    <div class="flex justify-between items-start mb-3">
                        <h4 class="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Counter-Play Strategy</h4>
                        <button onclick="downloadReport()" class="text-[10px] text-blue-400 hover:text-blue-300 underline">DOWNLOAD JSON REPORT</button>
                    </div>
                    <pre id="playText" class="text-xs text-gray-400 font-mono whitespace-pre-wrap"></pre>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentReport = null;

        function log(msg, type = 'info') {
            const t = document.getElementById('terminal');
            const color = type === 'error' ? 'text-red-500' : type === 'success' ? 'text-emerald-500' : 'text-blue-500';
            const icon = type === 'error' ? '✕' : type === 'success' ? '✓' : '▲';
            t.innerHTML += `<div class="terminal-line"><span class="${color}">${icon}</span> ${msg}</div>`;
            t.scrollTop = t.scrollHeight;
        }

        function setAgentStatus(agent, status, result = '') {
            const statusEl = document.getElementById(agent + 'Status');
            const resultEl = document.getElementById(agent + 'Result');

            if (status === 'running') {
                statusEl.innerHTML = '<span class="text-blue-400">● Running...</span>';
                statusEl.className = 'text-[10px] text-blue-400';
            } else if (status === 'complete') {
                statusEl.innerHTML = '<span class="text-emerald-400">✓ Complete</span>';
                statusEl.className = 'text-[10px] text-emerald-400';
                resultEl.innerText = result;
            } else if (status === 'error') {
                statusEl.innerHTML = '<span class="text-red-400">✕ Failed</span>';
                statusEl.className = 'text-[10px] text-red-400';
                resultEl.innerText = result;
            }
        }

        function updateThreatBanner(threatLevel) {
            const banner = document.getElementById('threatBanner');
            const badge = document.getElementById('threatBadge');

            banner.className = banner.className.replace(/border-l-4 border-\w+-\d+/, '');
            badge.className = 'px-4 py-2 rounded-lg text-xs font-bold border';

            if (threatLevel.includes('CRITICAL')) {
                banner.classList.add('border-l-4', 'border-red-500');
                badge.classList.add('status-critical');
                badge.innerText = 'CRITICAL';
            } else if (threatLevel.includes('ELEVATED')) {
                banner.classList.add('border-l-4', 'border-amber-500');
                badge.classList.add('status-elevated');
                badge.innerText = 'ELEVATED';
            } else {
                banner.classList.add('border-l-4', 'border-emerald-500');
                badge.classList.add('status-low');
                badge.innerText = 'LOW';
            }
        }

        function downloadReport() {
            if (!currentReport) return;
            const blob = new Blob([JSON.stringify(currentReport, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ShadowSignal_${document.getElementById('targetCompany').value}_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
        }

        async function executeOrchestration() {
            const target = document.getElementById('targetCompany').value;
            if (!target.trim()) {
                log("Error: Target company required", 'error');
                return;
            }

            // Reset UI
            document.getElementById('workspace').classList.remove('hidden');
            document.getElementById('dashboard').classList.add('hidden');
            document.getElementById('agentStatus').classList.remove('hidden');
            document.getElementById('terminal').innerHTML = '';
            document.getElementById('btnText').innerText = 'ANALYZING...';
            document.getElementById('btnSpinner').classList.remove('hidden');
            document.getElementById('actionButton').disabled = true;

            setAgentStatus('nemotron', 'running');
            setAgentStatus('deepseek', 'running');

            log(`Initializing intelligence sweep for: ${target}`);
            log("Establishing proxy tunnel via Bright Data...");

            try {
                const scrape = await fetch('/api/scrape?target=' + encodeURIComponent(target)).then(r => r.json());
                if (scrape.error) {
                    log("FAILURE: " + scrape.error, 'error');
                    setAgentStatus('nemotron', 'error', scrape.error);
                    setAgentStatus('deepseek', 'error', scrape.error);
                    return;
                }

                log(`SERP data acquired: ${scrape.bytes} bytes`, 'success');
                log("Dispatching dual-agent inference cluster...");

                const ai = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target, raw_data: scrape.raw_data })
                }).then(r => r.json());

                currentReport = ai;

                // Update Agent 1 (Nemotron)
                setAgentStatus('nemotron', 'complete', ai.aiml_sentiment);
                log(`Agent 1 (Nemotron) complete: ${ai.aiml_sentiment}`, 'success');

                // Update Agent 2 (DeepSeek)
                let deepseekData;
                try {
                    deepseekData = JSON.parse(ai.featherless_strategy.replace(/```json|```/g, ''));
                    setAgentStatus('deepseek', 'complete', 'JSON parsed successfully');
                    log("Agent 2 (DeepSeek) complete: Strategy generated", 'success');
                } catch (e) {
                    setAgentStatus('deepseek', 'error', 'JSON parse failed');
                    log("Agent 2 (DeepSeek) raw output: " + ai.featherless_strategy.substring(0, 100) + "...", 'error');
                    deepseekData = { executive_summary: "Parse error", pricing_vulnerabilities: "Parse error", recommended_sales_play: ai.featherless_strategy };
                }

                // Update Dashboard
                document.getElementById('dashboard').classList.remove('hidden');
                document.getElementById('threatLevel').innerText = "Nemotron Assessment";
                document.getElementById('summaryText').innerText = ai.aiml_sentiment;
                updateThreatBanner(ai.aiml_sentiment);

                document.getElementById('pricingText').innerText = deepseekData.pricing_vulnerabilities || "No data";
                document.getElementById('playText').innerText = typeof deepseekData.recommended_sales_play === 'object' 
                    ? JSON.stringify(deepseekData.recommended_sales_play, null, 2) 
                    : deepseekData.recommended_sales_play || "No data";

                if (ai.aiml_sentiment.includes('CRITICAL')) {
                    log("ALERT: Critical threat level detected - Email notification dispatched", 'error');
                }

            } catch (error) {
                log("System error: " + error.message, 'error');
                setAgentStatus('nemotron', 'error', error.message);
                setAgentStatus('deepseek', 'error', error.message);
            } finally {
                document.getElementById('btnText').innerText = 'EXECUTE ANALYSIS';
                document.getElementById('btnSpinner').classList.add('hidden');
                document.getElementById('actionButton').disabled = false;
            }
        }

        // Allow Enter key to trigger analysis
        document.getElementById('targetCompany').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') executeOrchestration();
        });
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

    url = "https://api.brightdata.com/request"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY.strip()}"
    }

    payload = {
        "zone": BRIGHT_DATA_ZONE.strip() if BRIGHT_DATA_ZONE else "",
        "url": f"https://www.google.com/search?q={target}+enterprise+pricing+competitive+strategy+changes&hl=en&gl=us",
        "format": "raw",
        "data_format": "parsed_light"
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code == 200:
            data = res.json()
            organic = data.get("organic", []) if isinstance(data, dict) else data

            if not organic: 
                return jsonify({"error": "No organic results found."})

            snippets = [f"Title: {r.get('title')}\nLink: {r.get('link')}\nDescription: {r.get('description')}" for r in organic]
            raw_text = "\n\n".join(snippets)[:15000]
            return jsonify({"status": "success", "raw_data": raw_text, "bytes": len(raw_text)})
        return jsonify({"error": f"Bright Data SERP Error: {res.status_code} - {res.text}"})
    except Exception as e:
        return jsonify({"error": f"Bright Data Connection Error: {str(e)}"})

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.get_json()
    if not data or 'raw_data' not in data or 'target' not in data:
        return jsonify({"error": "Missing required fields: raw_data, target"}), 400

    raw_data = data['raw_data']
    target = data['target']

    # Execute both agents concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_nemotron = executor.submit(agent_nemotron_sentiment, raw_data, target)
        future_deepseek = executor.submit(agent_deepseek_strategy, raw_data, target)
        nemotron_result = future_nemotron.result()
        deepseek_result = future_deepseek.result()

    # Send alert if critical
    if "CRITICAL" in nemotron_result: 
        send_automated_alert(target, nemotron_result, deepseek_result)

    # Save to memory
    try:
        parsed = json.loads(deepseek_result.replace("```json", "").replace("```", "").strip())
        if "error" not in parsed:
            save_to_memory(target, nemotron_result, parsed.get("executive_summary", ""))
    except Exception as e:
        print(f"Memory save skipped: {e}")

    return jsonify({
        "aiml_sentiment": nemotron_result, 
        "featherless_strategy": deepseek_result,
        "agents": {
            "agent_1": "Nemotron-3 (Threat Assessment)",
            "agent_2": "DeepSeek-V3.2 (GTM Strategy)"
        }
    })

@app.route('/api/history', methods=['GET'])
def history_endpoint():
    return jsonify({"logs": get_memory_logs()})

if __name__ == '__main__':
    app.run(debug=True)
