import os
import json
import requests
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

BRIGHT_DATA_ZONE_USER = os.getenv("BRIGHT_DATA_ZONE_USER")
BRIGHT_DATA_ZONE_PASS = os.getenv("BRIGHT_DATA_ZONE_PASS")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")

def fetch_live_market_data(target_company):
    print(f"📡 Requesting massive deep-web scrape for: {target_company}")
    
    proxies = {
        "http": f"http://{BRIGHT_DATA_ZONE_USER}:{BRIGHT_DATA_ZONE_PASS}@brd.superproxy.io:33335",
        "https": f"http://{BRIGHT_DATA_ZONE_USER}:{BRIGHT_DATA_ZONE_PASS}@brd.superproxy.io:33335"
    }
    
    # Increased hits to 30 because Featherless gives us a massive 32K context window!
    search_url = f"https://hn.algolia.com/api/v1/search?query={target_company}+pricing&hitsPerPage=30"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(search_url, proxies=proxies, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            hits = data.get("hits", [])
            
            if not hits:
                return {"status": "success", "raw_data": f"No recent deep web pricing leaks detected for {target_company}."}
            
            # Grabbing a massive chunk of text
            snippets = [f"Title: {h.get('title', '')} | Comment: {h.get('story_text', '')}" for h in hits]
            clean_text = " \n\n ".join(snippets)[:20000] 
            
            return {"status": "success", "raw_data": clean_text}
        else:
            return {"status": "error", "raw_data": f"BrightData Blocked. Status: {response.status_code}"}
    except Exception as e:
        return {"status": "error", "raw_data": f"Proxy Timeout: {str(e)}"}

def engine_analyze_intel(raw_web_context, target_company):
    if "BrightData" in raw_web_context or "Timeout" in raw_web_context:
        return f'{{"error": "Pipeline blocked: {raw_web_context}"}}'

    url = "https://api.featherless.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {FEATHERLESS_API_KEY.strip() if FEATHERLESS_API_KEY else ''}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        "You are an elite enterprise GTM strategy AI. Analyze the extensive raw web data provided. "
        "Return a structured strategic assessment identifying competitor weaknesses and sales counter-plays. "
        "Format your entire response STRICTLY as a JSON object with these exact keys: "
        "\"executive_summary\", \"pricing_vulnerabilities\", \"recommended_sales_play\"."
    )
    
    user_content = f"Target Company: {target_company}\n\nMassive Web Scrape Data:\n{raw_web_context}"
    
    payload = {
        "model": "deepseek-ai/DeepSeek-V3", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code in [200, 201]:
            return res.json()['choices'][0]['message']['content']
        return f'{{"error": "Featherless API Error (Status {res.status_code}): {res.text}"}}'
    except Exception as e:
        return f'{{"error": "Featherless Engine Connection Failed: {str(e)}"}}'

# --- ENTERPRISE FRONTEND UI ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal AI - Enterprise Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0c10; color: #c5c6c7; font-family: ui-sans-serif, system-ui; }
        .neon-card { border: 1px solid rgba(59, 130, 246, 0.3); box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6); }
    </style>
</head>
<body class="p-4 md:p-8 flex flex-col items-center justify-center min-h-screen">
    <div class="w-full max-w-2xl bg-[#12131c] rounded-2xl p-6 md:p-8 neon-card">
        <div class="flex items-center justify-between mb-6 border-b border-gray-800 pb-4">
            <div class="flex items-center space-x-3">
                <span class="text-3xl">📡</span>
                <div>
                    <h1 class="text-2xl font-bold text-white tracking-wide">ShadowSignal Enterprise</h1>
                    <p class="text-[10px] text-purple-400 font-extrabold uppercase tracking-widest">FEATHERLESS DEEPSEEK ENGINE ACTIVE</p>
                </div>
            </div>
        </div>
        
        <div class="mb-5">
            <label class="block text-xs font-bold uppercase text-gray-400 mb-2">Target Competitor</label>
            <input id="targetCompany" type="text" value="Microsoft" class="w-full bg-[#1c1d27] border border-gray-700 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-purple-500 transition-colors">
        </div>
        
        <button onclick="triggerPipeline()" id="actionButton" class="w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-4 rounded-lg text-sm transition-all shadow-lg shadow-purple-900/50">
            Execute Market Analysis
        </button>
        
        <div id="outputContainer" class="hidden mt-8">
            <h3 class="text-xs font-bold uppercase tracking-wide text-gray-400 mb-4">Strategic Intelligence Report:</h3>
            <div id="outputBlock" class="flex flex-col gap-4">
                <div class="text-xs text-gray-400 animate-pulse">Running 32K context analysis via DeepSeek...</div>
            </div>
        </div>
    </div>

    <script>
        async function triggerPipeline() {
            const target = document.getElementById('targetCompany').value;
            const btn = document.getElementById('actionButton');
            const box = document.getElementById('outputContainer');
            const textBlock = document.getElementById('outputBlock');
            
            btn.disabled = true;
            btn.className = "w-full bg-gray-700 text-gray-400 font-semibold py-3 px-4 rounded-lg text-sm cursor-not-allowed";
            btn.innerText = "Ingesting deep-web data...";
            box.classList.remove('hidden');
            
            try {
                const response = await fetch(`/api/analyze?target=${encodeURIComponent(target)}`);
                const out = await response.json();
                
                try {
                    // Render the structured JSON enterprise response
                    const aiData = JSON.parse(out.aiml_analysis);
                    
                    if(aiData.error) {
                        textBlock.innerHTML = `<div class="bg-red-900/20 border border-red-800 p-4 rounded-lg text-red-400 text-sm">${aiData.error}</div>`;
                    } else {
                        textBlock.innerHTML = `
                            <div class="bg-[#1a1b26] p-5 rounded-xl border border-gray-800 hover:border-gray-600 transition-colors">
                                <span class="text-blue-400 font-bold text-[11px] tracking-wider uppercase block mb-2">Executive Summary</span>
                                <p class="text-sm text-gray-300 leading-relaxed">${aiData.executive_summary}</p>
                            </div>
                            <div class="bg-[#1a1b26] p-5 rounded-xl border border-gray-800 hover:border-gray-600 transition-colors">
                                <span class="text-red-400 font-bold text-[11px] tracking-wider uppercase block mb-2">Pricing Vulnerabilities</span>
                                <p class="text-sm text-gray-300 leading-relaxed">${aiData.pricing_vulnerabilities}</p>
                            </div>
                            <div class="bg-[#1a1b26] p-5 rounded-xl border border-gray-800 hover:border-gray-600 transition-colors shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                                <span class="text-emerald-400 font-bold text-[11px] tracking-wider uppercase block mb-2">Recommended Sales Play</span>
                                <p class="text-sm text-white font-medium leading-relaxed">${aiData.recommended_sales_play}</p>
                            </div>
                        `;
                    }
                } catch(parseErr) {
                    textBlock.innerHTML = `<div class="bg-[#1a1b26] p-4 rounded-xl border border-gray-800 text-sm text-gray-300">${out.aiml_analysis}</div>`;
                }
                
            } catch(e) {
                textBlock.innerHTML = `<div class="text-red-500 text-sm">Critical UI routing error.</div>`;
            } finally {
                btn.disabled = false;
                btn.className = "w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-4 rounded-lg text-sm transition-all shadow-lg shadow-purple-900/50";
                btn.innerText = "Execute Market Analysis";
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
    scrape_results = fetch_live_market_data(target)
    live_analysis = engine_analyze_intel(scrape_results["raw_data"], target)
    return jsonify({
        "target": target,
        "aiml_analysis": live_analysis
    })
