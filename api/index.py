import os
import json
import requests
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

BRIGHT_DATA_ZONE_USER = os.getenv("BRIGHT_DATA_ZONE_USER")
BRIGHT_DATA_ZONE_PASS = os.getenv("BRIGHT_DATA_ZONE_PASS")
AIML_API_KEY = os.getenv("AIML_API_KEY")

def fetch_live_market_data(target_company):
    print(f"📡 Requesting live web scrape via Bright Data for: {target_company}")
    
    proxies = {
        "http": f"http://{BRIGHT_DATA_ZONE_USER}:{BRIGHT_DATA_ZONE_PASS}@brd.superproxy.io:33335",
        "https": f"http://{BRIGHT_DATA_ZONE_USER}:{BRIGHT_DATA_ZONE_PASS}@brd.superproxy.io:33335"
    }
    
    # DuckDuckGo HTML is much easier for datacenter proxies to read without triggering CAPTCHAs
    search_url = f"https://html.duckduckgo.com/html/?q={target_company}+enterprise+pricing+news+competitors"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(search_url, proxies=proxies, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Slices the first 2500 characters of the live HTML/text to send to the AI
            clean_text = " ".join(response.text.split())[:2500]
            return {"status": "success", "raw_data": clean_text}
        else:
            # WILL SHOW THE REAL ERROR IF BRIGHT DATA FAILS
            return {"status": "error", "raw_data": f"BrightData Proxy Blocked. Status: {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "raw_data": f"BrightData Connection Timeout: {str(e)}"}

def engine_analyze_intel(raw_web_context, target_company):
    # If the scraper failed, don't waste API tokens, just return the scraper error to the screen
    if "BrightData" in raw_web_context:
        return raw_web_context

    url = "https://api.aimlapi.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AIML_API_KEY.strip() if AIML_API_KEY else ''}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        "You are an expert GTM strategy AI. Read the messy live web scrape data provided. "
        "Extract exactly 1 real tactical sales insight about the company based ONLY on the provided text."
    )
    
    user_content = f"Target Company: {target_company}\n\nLive Web Data:\n{raw_web_context}"
    
    # Using the exact Free Nvidia model ID from your screenshot
    payload = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.3
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            return res.json()['choices'][0]['message']['content']
            
        # WILL SHOW THE REAL ERROR IF AI/ML API FAILS
        return f"AI/ML API Error (Status {res.status_code}): {res.text}"
        
    except Exception as e:
        return f"AI Engine Connection Failed: {str(e)}"

# --- FRONTEND UI ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal AI - Live Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0c10; color: #c5c6c7; font-family: ui-sans-serif, system-ui; }
        .neon-card { border: 1px solid rgba(59, 130, 246, 0.2); box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5); }
    </style>
</head>
<body class="p-4 md:p-8 flex flex-col items-center justify-center min-h-screen">
    <div class="w-full max-w-xl bg-[#12131c] rounded-2xl p-6 neon-card">
        <div class="flex items-center space-x-3 mb-4">
            <span class="text-3xl">📡</span>
            <div>
                <h1 class="text-xl font-bold text-white tracking-wide">ShadowSignal AI Live</h1>
                <p class="text-[10px] text-emerald-500 font-extrabold uppercase tracking-widest">LIVE DATA MODE ACTIVE</p>
            </div>
        </div>
        <div class="mb-5">
            <label class="block text-xs font-bold uppercase text-gray-400 mb-2">Target Enterprise</label>
            <input id="targetCompany" type="text" value="Nvidia" class="w-full bg-[#1c1d27] border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500">
        </div>
        <button onclick="triggerPipeline()" id="actionButton" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-4 rounded-lg text-sm transition-all">
            Execute Live-Data Scrape & Scan
        </button>
        <div id="outputContainer" class="hidden mt-6 pt-5 border-t border-gray-800">
            <h3 class="text-xs font-bold uppercase tracking-wide text-blue-400 mb-2">⚡ Real-Time Output Stream:</h3>
            <div id="outputBlock" class="bg-[#1a1b26] p-4 rounded-xl border border-gray-800 text-xs text-gray-300 font-mono leading-relaxed whitespace-pre-line overflow-y-auto max-h-64">
                Initializing real requests...
            </div>
        </div>
    </div>
    <script>
        async function triggerPipeline() {
            const target = document.getElementById('targetCompany').value;
            const btn = document.getElementById('actionButton');
            const box = document.getElementById('outputContainer');
            const text = document.getElementById('outputBlock');
            btn.disabled = true;
            btn.className = "w-full bg-gray-700 text-gray-400 font-semibold py-2.5 px-4 rounded-lg text-sm cursor-not-allowed";
            btn.innerText = "Pulling live web data via proxies...";
            box.classList.remove('hidden');
            text.innerText = "Connecting to real Bright Data proxy node...\\nExtracting live search results...\\nSending raw text to AI/ML API...";
            try {
                const response = await fetch(`/api/analyze?target=${encodeURIComponent(target)}`);
                const out = await response.json();
                
                if (out.aiml_analysis.includes("Error") || out.aiml_analysis.includes("Failed") || out.aiml_analysis.includes("Blocked")) {
                    text.innerHTML = `<span style="color: #ef4444;">🚨 <b>PIPELINE FAILURE DETECTED:</b><br><br>${out.aiml_analysis}</span>`;
                } else {
                    text.innerText = out.aiml_analysis;
                }
            } catch(e) {
                text.innerText = "Critical error: App failed to reach the /api/analyze route on Vercel.";
            } finally {
                btn.disabled = false;
                btn.className = "w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-4 rounded-lg text-sm transition-all";
                btn.innerText = "Execute Live-Data Scrape & Scan";
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
    target = request.args.get('target', 'Nvidia')
    
    # 1. LIVE WEB SCRAPE
    scrape_results = fetch_live_market_data(target)
    
    # 2. LIVE AI INFERENCE
    live_analysis = engine_analyze_intel(scrape_results["raw_data"], target)
    
    return jsonify({
        "target": target,
        "aiml_analysis": live_analysis
    })
