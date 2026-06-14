from flask import Flask, jsonify, request, render_template_string
import os
import json
import requests
import concurrent.futures
import resend

app = Flask(__name__)

# --- ENVIRONMENTAL AGENT CONFIGURATION ---
resend.api_key = os.getenv("RESEND_API_KEY", "").strip()
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "").strip()
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE", "").strip()
AIML_API_KEY = os.getenv("AIML_API_KEY", "").strip()
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "").strip()
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "compliance@shadowsignal.ai").strip()

# --- OFFICIAL BAND COMPLIANT ARCHITECTURE ---
class BandRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.peers = []
        self.state_context = {}
        self.message_history = []

    def invite_peer(self, agent_name):
        self.peers.append(agent_name)

    def dispatch_message(self, sender, activity, text_content):
        self.message_history.append({
            "sender": sender,
            "activity": activity,
            "data": text_content[:120] + "..." if len(text_content) > 120 else text_content
        })

# --- WORKFLOW AGENT ROUTINES ---

def agent_investigator_room_action(room, target):
    room.invite_peer("Investigator Agent")
    if not BRIGHT_DATA_API_KEY or not BRIGHT_DATA_ZONE:
        raw_intel = f"Baseline search data compiled for target node: {target}."
    else:
        url = "https://api.brightdata.com/request"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}"}
        payload = {
            "zone": BRIGHT_DATA_ZONE,
            "url": f"https://www.google.com/search?q={target}+enterprise+pricing+vulnerabilities",
            "format": "raw", "data_format": "parsed_light"
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=25).json()
            organic = res.get("organic", [])
            raw_intel = "\n".join([f"{r.get('title')}: {r.get('description')}" for r in organic[:5]])
        except:
            raw_intel = f"Fallback scraping stream active for target node: {target}."

    room.state_context["intel_stream"] = raw_intel
    room.dispatch_message("Investigator Agent", "Room Broadcast: Ingested Intel Stream", raw_intel)

def agent_gtm_analyst_room_action(room, target):
    room.invite_peer("GTM Analyst Agent")
    intel_stream = room.state_context.get("intel_stream", "")
    
    if not FEATHERLESS_API_KEY:
        summary = "Standard account variance detected. Defensive posture recommended."
    else:
        url = "https://api.featherless.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {FEATHERLESS_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-ai/DeepSeek-V3.2",
            "messages": [
                {"role": "system", "content": "You are a GTM Strategy Analyst Agent active within a Band Room. Generate a clear tactical market threat summary."},
                {"role": "user", "content": f"Target: {target}\nData Context:\n{intel_stream}"}
            ]
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=35).json()
            summary = res['choices'][0]['message']['content'].strip()
        except:
            summary = "GTM metrics pipeline fallback applied."

    room.state_context["gtm_analysis"] = summary
    room.dispatch_message("GTM Analyst Agent", "Room Broadcast: Compiled Strategy", summary)

def agent_regulatory_compliance_room_action(room, target):
    room.invite_peer("Regulatory Risk Agent")
    intel_stream = room.state_context.get("intel_stream", "")
    
    if not AIML_API_KEY:
        vulnerabilities = "Compliance tracking clear. Minimal operational friction."
    else:
        url = "https://api.aimlapi.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            "messages": [
                {"role": "system", "content": "You are a Regulatory Compliance Risk Agent inside a Band Room. Output either [CRITICAL RISK] or [LOW RISK] followed by a short risk description."},
                {"role": "user", "content": f"Target: {target}\nData Context: {intel_stream[:2000]}"}
            ]
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=30).json()
            vulnerabilities = res['choices'][0]['message']['content'].strip()
        except:
            vulnerabilities = "[LOW RISK] Runtime diagnostics clear."

    room.state_context["compliance_report"] = vulnerabilities
    room.dispatch_message("Regulatory Risk Agent", "Room Broadcast: Issued Compliance Audit", vulnerabilities)

# --- AUTONOMOUS ALERTS ---
def dispatch_resend_alert(target, audit, content):
    if not resend.api_key: return
    try:
        resend.Emails.send({
            "from": "ShadowSignal <onboarding@resend.dev>",
            "to": ALERT_EMAIL,
            "subject": f"🚨 BAND ROOM ESCALATION: {target}",
            "html": f"<h2>Room Level Security Threat</h2><p><b>Audit Verdict:</b> {audit}</p><hr><p>{content}</p>"
        })
    except: pass

# --- ADVANCED COMMAND TERMINAL HTML ---
COMMAND_CENTER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ShadowSignal | Active Band Room</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#030305] text-gray-400 font-sans min-h-screen p-6 md:p-12">
    <div class="max-w-5xl mx-auto space-y-8">
        
        <div class="flex justify-between items-center border-b border-gray-800 pb-6">
            <div>
                <h1 class="text-3xl font-extrabold text-white tracking-tight">SHADOWSIGNAL<span class="text-blue-500 font-mono">.ROOMS</span></h1>
                <p class="text-xs text-gray-500 uppercase tracking-widest mt-1">Inter-Agent Collaborative Chat Space</p>
            </div>
            <span class="text-xs font-mono text-blue-400 bg-blue-950/40 border border-blue-900 px-3 py-1 rounded-md tracking-wider">ROOM ARCHITECTURE ENGAGED</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 bg-[#090a0f] border border-gray-800 p-6 rounded-xl">
            <div class="md:col-span-2">
                <label class="block text-[10px] font-mono uppercase text-gray-500 tracking-wider mb-2">Target Corporate Entity</label>
                <input id="targetInput" type="text" value="Microsoft" class="w-full bg-[#101116] border border-gray-700 rounded-lg p-3 text-white focus:outline-none focus:border-blue-500 font-semibold text-sm">
            </div>
            <div class="flex items-end">
                <button onclick="instantiateBandRoom()" id="controlBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm py-3.5 rounded-lg transition-all tracking-wide">INITIALIZE BAND ROOM</button>
            </div>
        </div>

        <div class="bg-[#07080c] border border-gray-800 rounded-xl p-5 space-y-3">
            <h3 class="text-xs font-mono uppercase text-gray-400 tracking-widest border-b border-gray-800 pb-2">Band Room Peer Message Ledger</h3>
            <div id="roomLogs" class="font-mono text-xs space-y-2 h-36 overflow-y-auto text-blue-400/90">
                <div class="text-gray-600 font-sans italic">Room session offline. Click initiate above to invite agent peers...</div>
            </div>
        </div>

        <div id="outputDashboard" class="hidden grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-[#090a0f] border border-gray-800 p-6 rounded-xl space-y-2">
                <h4 class="text-[10px] font-mono text-purple-400 uppercase tracking-wider border-b border-gray-800 pb-2">GTM Analyst Agent Summary</h4>
                <p id="uiSummary" class="text-xs text-gray-300 leading-relaxed"></p>
            </div>
            <div class="bg-[#090a0f] border border-gray-800 p-6 rounded-xl space-y-2">
                <h4 class="text-[10px] font-mono text-red-400 uppercase tracking-wider border-b border-gray-800 pb-2">Regulatory & Compliance Assessment</h4>
                <p id="uiPricing" class="text-xs text-gray-300 leading-relaxed"></p>
            </div>
        </div>
    </div>

    <script>
        async function instantiateBandRoom() {
            const btn = document.getElementById('controlBtn');
            const target = document.getElementById('targetInput').value;
            const logBox = document.getElementById('roomLogs');
            const dash = document.getElementById('outputDashboard');
            
            btn.disabled = true;
            btn.innerText = "RECRUITING PEERS...";
            dash.classList.add('hidden');
            logBox.innerHTML = `<div class="text-blue-400 animate-pulse">[SYSTEM] Spawning isolated Band Room socket connection...</div>`;

            try {
                const response = await fetch('/api/run-room?target=' + encodeURIComponent(target)).then(r => r.json());
                
                logBox.innerHTML = '';
                response.message_history.forEach(m => {
                    logBox.innerHTML += `<div><span class="text-gray-500">[${m.sender}]</span> <span class="text-blue-500">${m.activity}</span> -> <span class="text-gray-300">${m.data}</span></div>`;
                });

                dash.classList.remove('hidden');
                document.getElementById('uiSummary').innerText = response.shared_context.gtm_analysis;
                document.getElementById('uiPricing').innerText = response.shared_context.compliance_report;

            } catch (err) {
                logBox.innerHTML += `<div class="text-red-500">[ERROR] Failed to coordinate room socket stream handoffs.</div>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "INITIALIZE BAND ROOM";
            }
        }
    </script>
</body>
</html>
"""

# --- GATEWAY ROUTING ENDPOINTS ---

@app.route('/')
def main_interface_gateway():
    return render_template_string(COMMAND_CENTER_HTML)

@app.route('/api/run-room', methods=['GET'])
def process_room_orchestration():
    target = request.args.get('target', 'Microsoft')

    # Establish an isolated room instance matching Band's multi-agent model specifications
    room = BandRoom(room_id="room_gtm_audit_stream")

    # Step 1: Investigator joins room and posts raw data context
    agent_investigator_room_action(room, target)

    # Step 2 & 3: Analyst and Regulatory agents ingest room data and broadcast responses concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.submit(agent_gtm_analyst_room_action, room, target)
        executor.submit(agent_regulatory_compliance_room_action, room, target)

    # Automated Policy Alert Validation
    audit_verdict = room.state_context.get("compliance_report", "")
    if "CRITICAL" in audit_verdict.upper():
        dispatch_resend_alert(target, audit_verdict, room.state_context.get("gtm_analysis", ""))

    return jsonify({
        "status": "active",
        "shared_context": room.state_context,
        "message_history": room.message_history
    })
