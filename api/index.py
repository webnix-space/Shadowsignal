```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShadowSignal Elite - Command Center</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #08090d; color: #cbd5e1; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
        .glass-panel { background: rgba(18, 20, 30, 0.7); border: 1px solid rgba(255, 255, 255, 0.05); backdrop-filter: blur(12px); }
        .glow-purple { box-shadow: 0 0 30px rgba(168, 85, 247, 0.15); }
        .pulse-border { animation: pulse-border 2s infinite; }
        @keyframes pulse-border { 
            0% { border-color: rgba(168, 85, 247, 0.3); } 
            50% { border-color: rgba(168, 85, 247, 1); } 
            100% { border-color: rgba(168, 85, 247, 0.3); } 
        }
        ::-webkit-scrollbar { width: 6px; } 
        ::-webkit-scrollbar-track { background: transparent; } 
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    </style>
</head>
<body class="min-h-screen flex flex-col h-screen overflow-hidden">

    <!-- Top Navigation / Ticker -->
    <div class="w-full bg-[#0d0f16] border-b border-gray-800 px-6 py-2.5 flex justify-between items-center text-[10px] uppercase tracking-widest text-gray-400 z-10">
        <div class="flex items-center space-x-6">
            <div class="flex items-center space-x-2">
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span class="font-bold text-gray-300">Live Crawl:</span> <span class="text-emerald-400">Bright Data SERP API</span>
            </div>
            <div class="flex items-center space-x-2">
                <span class="w-2 h-2 rounded-full bg-blue-500"></span>
                <span class="font-bold text-gray-300">Memory DB:</span> <span class="text-blue-400">Local Storage</span>
            </div>
        </div>
        <div class="hidden md:flex gap-4 font-mono">
            <span>Agent 1: <span class="text-purple-400">Nemotron-30B</span></span>
            <span>Agent 2: <span class="text-purple-400">DeepSeek-V3.2</span></span>
        </div>
    </div>

    <!-- Main Workspace -->
    <div class="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 p-4 md:p-6 overflow-hidden">
        
        <!-- Sidebar: Memory Bank -->
        <div class="lg:col-span-1 flex flex-col h-full overflow-hidden">
            <div class="glass-panel rounded-xl p-5 flex flex-col h-full border border-gray-800">
                <h2 class="text-xs font-bold uppercase tracking-wider text-blue-400 mb-4 flex items-center justify-between border-b border-gray-800 pb-3">
                    <span>🧠 Memory Bank Logs</span>
                </h2>
                <div id="historyContainer" class="flex flex-col gap-3 overflow-y-auto pr-2 flex-1">
                    <!-- History logs injected here -->
                </div>
            </div>
        </div>

        <!-- Central Execution Matrix -->
        <div class="lg:col-span-3 flex flex-col gap-6 h-full overflow-y-auto pb-10 pr-2">
            
            <!-- Controller -->
            <div class="glass-panel rounded-xl p-6 glow-purple border border-purple-900/30">
                <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
                    <div class="flex-1">
                        <label class="block text-[10px] font-bold uppercase text-gray-400 tracking-widest mb-2">Target Competitor</label>
                        <input id="targetCompany" type="text" value="Google Cloud" class="w-full bg-[#141622] border border-gray-700 rounded-lg px-4 py-3.5 text-white text-sm focus:outline-none focus:border-purple-500 transition-colors font-semibold">
                    </div>
                    <button onclick="executeOrchestration()" id="actionButton" class="bg-purple-600 hover:bg-purple-700 text-white font-bold px-8 py-3.5 rounded-lg text-sm tracking-wide transition-all shadow-lg shadow-purple-900/50 w-full md:w-auto">
                        Execute Multi-Agent Scan
                    </button>
                </div>
            </div>

            <!-- Error Modal -->
            <div id="errorModal" class="hidden glass-panel border-red-500/50 p-4 rounded-xl text-red-400 text-sm font-mono whitespace-pre-wrap"></div>

            <!-- Dashboard Outputs -->
            <div id="outputDashboard" class="hidden flex-col gap-6">
                
                <!-- Nemotron Threat Header -->
                <div id="sentimentBlock" class="glass-panel p-5 rounded-xl border border-gray-700 flex flex-col md:flex-row items-center justify-between gap-4">
                    <span class="text-xs text-purple-400 font-bold animate-pulse">Agent 1: Analyzing Threat Level...</span>
                </div>

                <!-- DeepSeek Strategy Cards -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
                    <div class="bg-[#11131e] border border-blue-500/20 rounded-xl p-6 shadow-lg hover:border-blue-500/50 transition-colors">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-[10px] font-bold uppercase text-blue-400 tracking-wider">Executive Summary</span>
                            <span class="text-xl">📊</span>
                        </div>
                        <p id="summaryText" class="text-sm text-gray-300 leading-relaxed"><span class="animate-pulse">DeepSeek digesting Bright Data SERP...</span></p>
                    </div>

                    <div class="bg-[#11131e] border border-red-500/20 rounded-xl p-6 shadow-lg hover:border-red-500/50 transition-colors">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-[10px] font-bold uppercase text-red-400 tracking-wider">Pricing Vulnerabilities</span>
                            <span class="text-xl">🎯</span>
                        </div>
                        <p id="pricingText" class="text-sm text-gray-300 leading-relaxed"><span class="animate-pulse">Extracting weaknesses...</span></p>
                    </div>

                    <div class="bg-[#11131e] border border-emerald-500/30 rounded-xl p-6 shadow-xl shadow-emerald-900/10 hover:border-emerald-500/60 transition-colors">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-[10px] font-bold uppercase text-emerald-400 tracking-wider">Recommended Counter-Play</span>
                            <span class="text-xl">⚡</span>
                        </div>
                        <p id="playText" class="text-sm text-white font-medium leading-relaxed"><span class="animate-pulse">Synthesizing strategy...</span></p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- JAVASCRIPT ORCHESTRATION LOGIC -->
    <script>
        // ==========================================
        // 🔑 INSERT ALL 4 OF YOUR API KEYS HERE
        // ==========================================
        const BRIGHT_DATA_API_KEY = ""; // "Bearer <API_KEY>" from Bright Data
        const BRIGHT_DATA_ZONE = "";    // e.g. "serp_api_1"
        const AIML_API_KEY = "";        // AI/ML API Key
        const FEATHERLESS_API_KEY = ""; // Featherless API Key

        // Initialize UI
        window.onload = refreshHistoryList;

        // --- MEMORY SYSTEM (LocalStorage) ---
        function saveToMemory(company, threat, summary) {
            let logs = JSON.parse(localStorage.getItem('shadowsignal_logs') || '[]');
            const now = new Date();
            const timeString = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')} ${now.toLocaleString('default', { month: 'short' })} ${now.getDate()}`;
            
            logs.unshift({
                company: company,
                time: timeString,
                threat: threat,
                snippet: summary.substring(0, 70) + '...'
            });
            
            if (logs.length > 15) logs = logs.slice(0, 15);
            localStorage.setItem('shadowsignal_logs', JSON.stringify(logs));
            refreshHistoryList();
        }

        function refreshHistoryList() {
            const logs = JSON.parse(localStorage.getItem('shadowsignal_logs') || '[]');
            const box = document.getElementById('historyContainer');
            
            if (logs.length === 0) {
                box.innerHTML = `<p class="text-xs text-gray-500 italic">No historical traces detected.</p>`;
                return;
            }

            box.innerHTML = logs.map(log => `
                <div class="bg-[#141622] border border-gray-800 p-3.5 rounded-lg hover:border-blue-500/40 transition-colors">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-xs font-bold text-white">${log.company}</span>
                        <span class="text-[9px] text-gray-500 font-mono">${log.time}</span>
                    </div>
                    <p class="text-[10px] text-gray-400 font-mono leading-tight">${log.snippet}</p>
                </div>
            `).join('');
        }

        // --- CRAWLER: BRIGHT DATA SERP API ---
        async function fetchBrightDataSERP(target) {
            if (!BRIGHT_DATA_API_KEY || !BRIGHT_DATA_ZONE) {
                throw new Error("Missing Bright Data API Key or Zone name.");
            }

            const query = encodeURIComponent(`${target} enterprise pricing competitive strategy changes`);
            const targetUrl = `https://www.google.com/search?q=${query}&hl=en&gl=us`;

            const payload = {
                zone: BRIGHT_DATA_ZONE,
                url: targetUrl,
                format: "raw",
                data_format: "parsed_light" // From your screenshot! Forces clean JSON output.
            };

            const res = await fetch("https://api.brightdata.com/request", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${BRIGHT_DATA_API_KEY}`
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errText = await res.text();
                throw new Error(`Bright Data Error ${res.status}: ${errText}`);
            }

            const data = await res.json();
            
            // Extract the top 10 organic Google results
            if (!data.organic || data.organic.length === 0) return "No data found on Google SERP.";
            
            const snippets = data.organic.map(r => `Title: ${r.title}\nLink: ${r.link}\nDescription: ${r.description}`);
            return snippets.join("\n\n").substring(0, 15000); // Package beautifully for the AI
        }

        // --- AGENT 1: AI/ML NEMOTRON ---
        async function runAgent1(target, dataContext) {
            if (!AIML_API_KEY) throw new Error("Missing AI/ML API Key.");
            
            const prompt = "Evaluate the data. Output ONLY a single line: [THREAT LEVEL] | [10-word summary]. Threat Level must be CRITICAL, ELEVATED, or LOW.";
            const payload = {
                model: "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                messages: [
                    {role: "system", content: prompt},
                    {role: "user", content: `Target: ${target}\nGoogle Data: ${dataContext.substring(0, 3000)}`}
                ],
                temperature: 0.3
            };

            const res = await fetch("https://api.aimlapi.com/v1/chat/completions", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${AIML_API_KEY}` },
                body: JSON.stringify(payload)
            });
            if(!res.ok) throw new Error(`AI/ML API Error: ${res.status}`);
            const data = await res.json();
            return data.choices[0].message.content.trim();
        }

        // --- AGENT 2: FEATHERLESS DEEPSEEK ---
        async function runAgent2(target, dataContext) {
            if (!FEATHERLESS_API_KEY) throw new Error("Missing Featherless API Key.");
            
            const prompt = "You are an elite enterprise GTM AI. Analyze the scraped Google SERP data. Format response STRICTLY as raw JSON with EXACTLY these three keys: \"executive_summary\", \"pricing_vulnerabilities\", \"recommended_sales_play\". Values must be single plain-text paragraphs. NO Markdown.";
            const payload = {
                model: "deepseek-ai/DeepSeek-V3.2",
                max_tokens: 4096,
                temperature: 0.2,
                messages: [
                    {role: "system", content: prompt},
                    {role: "user", content: `Target: ${target}\nGoogle Data:\n${dataContext}`}
                ]
            };

            const res = await fetch("https://api.featherless.ai/v1/chat/completions", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${FEATHERLESS_API_KEY}` },
                body: JSON.stringify(payload)
            });
            
            if (!res.ok) throw new Error(`Featherless API Error: ${res.status}`);
            
            const data = await res.json();
            let content = data.choices[0].message.content.trim();
            
            // Markdown stripper
            content = content.replace(/^```json/i, '').replace(/^```/i, '').replace(/```$/i, '').trim();
            return JSON.parse(content);
        }

        // --- MASTER ORCHESTRATOR ---
        async function executeOrchestration() {
            const target = document.getElementById('targetCompany').value;
            const btn = document.getElementById('actionButton');
            const dash = document.getElementById('outputDashboard');
            const errBox = document.getElementById('errorModal');
            
            if(!FEATHERLESS_API_KEY || !AIML_API_KEY || !BRIGHT_DATA_API_KEY) {
                errBox.classList.remove('hidden');
                errBox.innerText = "❌ ERROR: You must insert all 4 API keys at the top of the Javascript section before running.";
                return;
            }

            // UI Reset
            errBox.classList.add('hidden');
            btn.disabled = true;
            btn.className = "bg-gray-800 text-gray-500 font-bold px-8 py-3.5 rounded-lg text-sm tracking-wide cursor-not-allowed w-full md:w-auto";
            btn.innerText = "Querying Bright Data SERP API...";
            dash.classList.remove('hidden');
            
            document.getElementById('sentimentBlock').className = "glass-panel p-5 rounded-xl border pulse-border flex items-center justify-center";
            document.getElementById('sentimentBlock').innerHTML = `<span class="text-xs text-purple-400 font-bold animate-pulse">Running Google SERP Crawl...</span>`;
            ['summaryText', 'pricingText', 'playText'].forEach(id => {
                document.getElementById(id).innerHTML = `<span class="animate-pulse text-gray-600">Awaiting SERP data payload...</span>`;
            });
            
            try {
                // 1. Scrape Google SERP data via Bright Data
                const webData = await fetchBrightDataSERP(target);
                
                document.getElementById('sentimentBlock').innerHTML = `<span class="text-xs text-emerald-400 font-bold animate-pulse">SERP Payload Received. Agent 1 & Agent 2 reasoning concurrently...</span>`;
                ['summaryText', 'pricingText', 'playText'].forEach(id => {
                    document.getElementById(id).innerHTML = `<span class="animate-pulse text-blue-500">Processing structured Google intelligence...</span>`;
                });

                // 2. Parallel AI Execution
                const [aimlResult, deepseekResult] = await Promise.all([
                    runAgent1(target, webData),
                    runAgent2(target, webData)
                ]);
                
                // 3. Render Agent 1
                let threatColor = "text-yellow-400";
                if(aimlResult.includes("CRITICAL") || aimlResult.includes("HIGH")) threatColor = "text-red-500";
                if(aimlResult.includes("LOW")) threatColor = "text-emerald-400";
                
                document.getElementById('sentimentBlock').className = "glass-panel p-5 rounded-xl border border-gray-700 flex flex-col md:flex-row items-center justify-between gap-4";
                document.getElementById('sentimentBlock').innerHTML = `
                    <div class="flex flex-col">
                        <span class="text-[10px] font-bold tracking-widest text-gray-500 uppercase mb-1">Nemotron-30B Fast-Pass Analysis</span>
                        <span class="text-sm font-bold ${threatColor}">${aimlResult}</span>
                    </div>
                `;

                // 4. Render Agent 2
                document.getElementById('summaryText').innerText = deepseekResult.executive_summary || "No data.";
                document.getElementById('pricingText').innerText = deepseekResult.pricing_vulnerabilities || "No data.";
                document.getElementById('playText').innerText = deepseekResult.recommended_sales_play || "No data.";
                
                // 5. Save to Local Memory
                saveToMemory(target, aimlResult, deepseekResult.executive_summary);
                
            } catch (error) {
                console.error(error);
                errBox.classList.remove('hidden');
                errBox.innerText = `🚨 Pipeline Failure:\n${error.message}\n\nNote: If Bright Data throws a CORS error, you may need to run this from a local server or use a CORS proxy.`;
            } finally {
                btn.disabled = false;
                btn.className = "bg-purple-600 hover:bg-purple-700 text-white font-bold px-8 py-3.5 rounded-lg text-sm tracking-wide transition-all shadow-lg shadow-purple-900/50 w-full md:w-auto";
                btn.innerText = "Execute Multi-Agent Scan";
            }
        }
    </script>
</body>
</html>


```
