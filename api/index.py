import os
import json
import requests
import concurrent.futures
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

BRIGHT_DATA_ZONE_USER = os.getenv("BRIGHT_DATA_ZONE_USER")
BRIGHT_DATA_ZONE_PASS = os.getenv("BRIGHT_DATA_ZONE_PASS")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
AIML_API_KEY = os.getenv("AIML_API_KEY")

def fetch_live_market_data(target_company):
    print(f"📡 Requesting massive deep-web scrape for: {target_company}")
    proxies = {
        "http": f"http://{BRIGHT_DATA_ZONE_USER}:{BRIGHT_DATA_ZONE_PASS}@brd.superproxy.io:33335",
        "https": f"http://{BRIGHT_DATA_ZONE_USER}:{BRIGHT_DATA_ZONE_PASS}@brd.superproxy.io:33335"
    }
    search_url = f"https://hn.algolia.com/api/v1/search?query={target_company}+pricing&hitsPerPage=30"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(search_url, proxies=proxies, headers=headers, timeout=12)
        if response.status_code == 200:
            hits = response.json().get("hits", [])
            if not hits:
                return "No recent deep web pricing leaks detected."
            snippets = [f"Title: {h.get('title', '')} | Comment: {h.get('story_text', '')}" for h in hits]
            return " \n\n ".join(snippets)[:20000] 
        return f"BrightData Blocked: {response.status_code}"
    except Exception as e:
        return f"Proxy Timeout: {str(e)}"

def agent_aiml_sentiment(raw_web_context, target_company):
    """AGENT 1: AI/ML API (Nemotron) - Fast Threat Scoring"""
    if "Blocked" in raw_web_context or "Timeout" in raw_web_context:
        return "THREAT: UNKNOWN | Data collection failed."

    url = "https://api.aimlapi.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AIML_API_KEY.strip() if AIML_API_KEY else ''}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are a rapid market sentiment analyzer. Evaluate the pricing data provided. "
        "Output ONLY a single line formatted exactly like this: "
        "[THREAT LEVEL] | [10-word summary of market sentiment]. "
        "For Threat Level, strictly choose one: CRITICAL, ELEVATED, or LOW."
    )
    payload = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Target: {target_company}\nData: {raw_web_context[:4000]}"}
        ],
        "temperature": 0.3
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            return res.json()['choices'][0]['message']['content'].strip()
        return f"AI/ML API Error {res.status_code}"
    except:
        return "AI/ML Agent Timeout"

def agent_featherless_strategy(raw_web_context, target_company):
    """AGENT 2: Featherless API (DeepSeek) - Deep JSON Strategy"""
    if "Blocked" in raw_web_context or "Timeout" in raw_web_context:
        return f'{{"error": "Pipeline blocked: {raw_web_context}"}}'

    url = "https://api.featherless.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {FEATHERLESS_API_KEY.strip() if FEATHERLESS_API_KEY else ''}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are an elite enterprise GTM strategy AI. Analyze the raw web data provided. "
        "Format your entire response STRICTLY as a raw JSON object with EXACTLY these three keys: "
        "\"executive_summary\", \"pricing_vulnerabilities\", and \"recommended_sales_play\". "
        "CRITICAL: The value for each key MUST be a single plain-text paragraph (string). Do not use nested arrays. "
        "Do NOT wrap the output in markdown blocks. Return only raw JSON."
    )
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2", 
        "max_tokens": 4096,                    
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Target: {target_company}\nData:\n{raw_web_context}"}
        ],
        "temperature": 0.2
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code in [200, 201]:
            try:
                content = res.json()['choices'][0]['message']['content'].strip()
                if content.startswith("```json"): content = content[7:]
                elif content.startswith("```"): content = content[3:]
                if content.endswith("```"): content = content[:-3]
                return content.strip()
            except ValueError:
                return '{"error": "Failed to parse JSON"}'
        return f'{{"error": "Featherless Error {res.status_code}"}}'
    except Exception as e:
        return f'{{"error": "Featherless Timeout: {str(e)}"}}'


# --- ENTERPRISE FRONTEND UI ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal AI - Multi-Agent Platform</title>
    <script src="[https://cdn.tailwindcss.com](https://cdn.tailwindcss.com)"></script>
    <style>
        body { background-color: #0b0c10; color: #c5c6c7; font-family: ui-sans-serif, system-ui; }
        .neon-card { border: 1px solid rgba(59, 130, 246, 0.3); box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6); }
        .pulse-border { animation: pulse-border 2s infinite; }
        @keyframes pulse-border { 0% { border-color: rgba(168, 85, 247, 0.4); } 50% { border-color: rgba(168, 85, 247, 1); } 100% { border-color: rgba(168, 85, 247, 0.4); } }
    </style>
</head>
<body class="p-4 md:p-8 flex flex-col items-center justify-center min-h-screen">
    <div class="w-full max-w-2xl bg-[#12131c] rounded-2xl p-6 md:p-8 neon-card">
        <div class="flex items-center justify-between mb-6 border-b border-gray-800 pb-4">
            <div class="flex items-center space-x-3">
                <span class="text-3xl">📡</span>
                <div>
                    <h1 class="text-2xl font-bold text-white tracking-wide">ShadowSignal Multi-Agent</h1>
                    <div class="flex gap-2 mt-1">
                        <span class="px-2 py-0.5 bg-blue-900/50 border border-blue-500 rounded text-[9px] text-blue-300 font-bold uppercase">AI/ML Nemotron</span>
                        <span class="px-2 py-0.5 bg-purple-900/50 border border-purple-500 rounded text-[9px] text-purple-300 font-bold uppercase">Featherless DeepSeek</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mb-5">
            <label class="block text-xs font-bold uppercase text-gray-400 mb-2">Target Competitor</label>
            <input id="targetCompany" type="text" value="Microsoft" class="w-full bg-[#1c1d27] border border-gray-700 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-purple-500 transition-colors">
        </div>
        
        <button onclick="triggerPipeline()" id="actionButton" class="w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-4 rounded-lg text-sm transition-all shadow-lg shadow-purple-900/50">
            Execute Parallel AI Agents
        </button>
        
        <div id="outputContainer" class="hidden mt-8">
            <!-- AGENT 1 OUTPUT -->
            <div id="sentimentBlock" class="mb-6 bg-[#1a1b26] p-4 rounded-xl border pulse-border text-center">
                <span class="text-xs text-purple-400 font-bold animate-pulse">Running AI/ML Fast Threat Detection...</span>
            </div>
            
            <!-- AGENT 2 OUTPUT -->
            <h3 class="text-xs font-bold uppercase tracking-wide text-gray-500 mb-4 flex items-center gap-2">
                <span>Strategic Intelligence Report</span>
            </h3>
            <div id="strategyBlock" class="flex flex-col gap-4">
                <div class="text-xs text-gray-400 animate-pulse text-center">Featherless DeepSeek reasoning...</div>
            </div>
        </div>
    </div>

    <script>
        async function triggerPipeline() {
            const target = document.getElementById('targetCompany').value;
            const btn = document.getElementById('actionButton');
            const box = document.getElementById('outputContainer');
            const sentimentBlock = document.getElementById('sentimentBlock');
            const strategyBlock = document.getElementById('strategyBlock');
            
            btn.disabled = true;
            btn.className = "w-full bg-gray-700 text-gray-400 font-semibold py-3 px-4 rounded-lg text-sm cursor-not-allowed";
            btn.innerText = "Orchestrating AI Agents...";
            
            sentimentBlock.innerHTML = `<span class="text-xs text-purple-400 font-bold animate-pulse">Running AI/ML Fast Threat Detection...</span>`;
            sentimentBlock.className = "mb-6 bg-[#1a1b26] p-4 rounded-xl border pulse-border text-center";
            strategyBlock.innerHTML = `<div class="text-xs text-gray-400 animate-pulse text-center">Featherless DeepSeek reasoning...</div>`;
            box.classList.remove('hidden');
            
            try {
                const response = await fetch(`/api/analyze?target=${encodeURIComponent(target)}`);
                const out = await response.json();
                
                // --- RENDER AGENT 1 (AI/ML) ---
                let threatColor = "text-yellow-400";
                if(out.aiml_sentiment.includes("CRITICAL") || out.aiml_sentiment.includes("HIGH")) threatColor = "text-red-500";
                if(out.aiml_sentiment.includes("LOW")) threatColor = "text-emerald-400";
                
                sentimentBlock.className = "mb-6 bg-gray-900/50 p-4 rounded-xl border border-gray-700 flex flex-col items-center justify-center gap-2";
                sentimentBlock.innerHTML = `
                    <span class="text-[10px] font-bold tracking-widest text-gray-400 uppercase">Nemotron Threat Assessment</span>
                    <span class="text-sm font-bold ${threatColor}">${out.aiml_sentiment}</span>
                `;

                // --- RENDER AGENT 2 (Featherless) ---
                try {
                    const aiData = JSON.parse(out.featherless_strategy);
                    if(aiData.error) {
                        strategyBlock.innerHTML = `<div class="bg-red-900/20 border border-red-800 p-4 rounded-lg text-red-400 text-sm">${aiData.error}</div>`;
                    } else {
                        strategyBlock.innerHTML = `
                            <div class="bg-[#1a1b26] p-5 rounded-xl border border-gray-800 hover:border-gray-600 transition-colors">
                                <span class="text-blue-400 font-bold text-[11px] tracking-wider uppercase block mb-2">Executive Summary</span>
                                <p class="text-sm text-gray-300 leading-relaxed">${aiData.executive_summary || "N/A"}</p>
                            </div>
                            <div class="bg-[#1a1b26] p-5 rounded-xl border border-gray-800 hover:border-gray-600 transition-colors">
                                <span class="text-red-400 font-bold text-[11px] tracking-wider uppercase block mb-2">Pricing Vulnerabilities</span>
                                <p class="text-sm text-gray-300 leading-relaxed">${aiData.pricing_vulnerabilities || "N/A"}</p>
                            </div>
                            <div class="bg-[#1a1b26] p-5 rounded-xl border border-gray-800 hover:border-gray-600 transition-colors shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                                <span class="text-emerald-400 font-bold text-[11px] tracking-wider uppercase block mb-2">Recommended Sales Play</span>
                                <p class="text-sm text-white font-medium leading-relaxed">${aiData.recommended_sales_play || "N/A"}</p>
                            </div>
                        `;
                    }
                } catch(parseErr) {
                    strategyBlock.innerHTML = `<div class="bg-[#1a1b26] p-4 rounded-xl border border-gray-800 text-sm text-gray-300">${out.featherless_strategy}</div>`;
                }
                
            } catch(e) {
                strategyBlock.innerHTML = `<div class="text-red-500 text-sm">Critical UI routing error.</div>`;
            } finally {
                btn.disabled = false;
                btn.className = "w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-4 rounded-lg text-sm transition-all shadow-lg shadow-purple-900/50";
                btn.innerText = "Execute Parallel AI Agents";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def main_dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/analyze', methods=['GET'])
def analyze():
    target = request.args.get('target', 'Microsoft')
    
    # 1. Fetch data
    raw_data = fetch_live_market_data(target)
    
    # 2. Run both AI agents simultaneously using Threading
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_aiml = executor.submit(agent_aiml_sentiment, raw_data, target)
        future_feather = executor.submit(agent_featherless_strategy, raw_data, target)
        
        aiml_result = future_aiml.result()
        feather_result = future_feather.result()
        
    return jsonify({
        "target": target,
        "aiml_sentiment": aiml_result,
        "featherless_strategy": feather_result
    })
