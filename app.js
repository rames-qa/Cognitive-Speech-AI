import os
import re
import sys
import logging
import threading
import urllib.parse
import random
import time
import psutil
import socket
import requests
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
# --- UTILITY: PORT REUSE CLEANER ---
def kill_process_on_port(port):
    """Dynamically releases port 5000 if it is locked by an orphaned process."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Safely try 'net_connections' first to bypass the deprecation warning
            connections_fn = getattr(proc, "net_connections", getattr(proc, "connections", None))
            if connections_fn:
                for conn in connections_fn(kind='inet'):
                    if conn.laddr.port == port:
                        print(f"[PORT GUARD] Terminating process {proc.info['name']} (PID: {proc.info['pid']}) holding port {port}...")
                        proc.terminate()
                        proc.wait(timeout=2)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

# Release port 5000 before boot to prevent "Address already in use" errors
kill_process_on_port(5000)

# --- SYSTEM SETUP & CONFIGURATION ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Disable excessive Flask/Werkzeug logs in terminal
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# --- GLOBAL CONCURRENCY STATE ---
automation_lock = threading.Lock()
active_driver = None
current_automation_status = "Awaiting instructions..."

# --- COMPLETELY DYNAMIC REGISTRY CONFIGURATION ---
PLATFORM_REGISTRY = {
    "amazon": {
        "base_url": "https://www.amazon.in",
        "search_path": "/s?k=",
        "has_automation": True,
    },
    "flipkart": {
        "base_url": "https://www.flipkart.com",
        "search_path": "/search?q=",
        "has_automation": False,
    },
    "myntra": {
        "base_url": "https://www.myntra.com",
        "search_path": "/",
        "aliases": ["fashion", "clothes", "shopping"],
        "has_automation": False,
    },
    "gmail": {
        "base_url": "https://mail.google.com",
        "search_path": "/mail/u/0/#search/",
        "aliases": ["mail", "inbox"],
        "has_automation": False,
    },
    "youtube": {
        "base_url": "https://www.youtube.com",
        "search_path": "/results?search_query=",
        "aliases": ["video", "song", "music"],
        "has_automation": False,
    },
    "news": {
        "base_url": "https://news.google.com",
        "search_path": "/search?q=",
        "aliases": [
            "world news",
            "global news",
            "updates",
            "breaking news",
            "current affairs",
        ],
        "has_automation": True,
    },
    "reuters": {
        "base_url": "https://www.reuters.com",
        "search_path": "/search/ui/?q=",
        "aliases": ["international news", "business updates"],
        "has_automation": False,
    },
    "bbc news": {
        "base_url": "https://www.bbc.com/news",
        "search_path": "/search?q=",
        "aliases": ["bbc"],
        "has_automation": False,
    },
    "github": {
        "base_url": "https://github.com",
        "search_path": "/search?q=",
        "has_automation": False,
    },
    "linkedin": {
        "base_url": "https://www.linkedin.com",
        "search_path": "/search/results/all/?keywords=",
        "has_automation": False,
    },
    "google": {
        "base_url": "https://www.google.com",
        "search_path": "/search?q=",
        "has_automation": False,
    },
    "stackoverflow": {
        "base_url": "https://stackoverflow.com",
        "search_path": "/search?q=",
        "has_automation": False,
    },
    "reddit": {
        "base_url": "https://www.reddit.com",
        "search_path": "/search/?q=",
        "has_automation": False,
    },
    "wikipedia": {
        "base_url": "https://en.wikipedia.org",
        "search_path": "/wiki/Special:Search?search=",
        "has_automation": False,
    },
}

# --- DYNAMIC NLP PARSING ENGINE ---
def resolve_intent_and_query(command):
    command = command.lower().strip()
    matched_platform = None

    sorted_platforms = sorted(
        PLATFORM_REGISTRY.items(),
        key=lambda item: max(
            [len(term) for term in [item[0]] + item[1].get("aliases", [])]
        ),
        reverse=True,
    )
    for target_key, config in sorted_platforms:
        search_terms = [target_key] + config.get("aliases", [])
        for term in search_terms:
            if re.search(r"\b" + re.escape(term) + r"\b", command):
                matched_platform = target_key
                command = re.sub(
                    r"\b" + re.escape(term) + r"\b", "", command
                ).strip()
                break
        if matched_platform:
            break

    action_patterns = [
        r"\btell me about\b",
        r"\bdetails of\b",
        r"\bsearch for\b",
        r"\bopen up\b",
        r"\broute to\b",
        r"\bshow me\b",
        r"\bgo to\b",
        r"\bsearch\b",
        r"\blaunch\b",
        r"\bstart\b",
        r"\bplay\b",
        r"\bfind\b",
        r"\bopen\b",
        r"\on\b",
        r"\bfor\b",
        r"\bat\b",
        r"\band\b",
    ]
    clean_query = command
    for pattern in action_patterns:
        clean_query = re.sub(pattern, " ", clean_query)
    extracted_query = " ".join(clean_query.split())
    return matched_platform, extracted_query


# --- AUTOMATION DRIVER CONFIGURATION ROUTINE ---
def get_configured_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("detach", True)
    
    # Hide automation detection flags
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    chrome_service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=chrome_service, options=options)


# --- DYNAMIC SELECTION WORKER DISPATCHER ---
def run_platform_automation(platform, query):
    global active_driver, current_automation_status
    if not automation_lock.acquire(blocking=False):
        current_automation_status = "Engine locked. Pipeline busy."
        return

    local_driver = None
    try:
        current_automation_status = f"Spinning up driver for {platform.title()}..."
        local_driver = get_configured_driver()
        active_driver = local_driver
        
        platform_config = PLATFORM_REGISTRY[platform]
        
        if platform == "amazon":
            current_automation_status = "Running Amazon workflow..."
            local_driver.get(platform_config["base_url"])
            wait = WebDriverWait(local_driver, 12)
            signin_node = wait.until(EC.element_to_be_clickable((By.ID, "nav-link-accountList")))
            signin_node.click()
            current_automation_status = "Amazon workflow complete."
            
        elif platform == "news":
            current_automation_status = "Scraping media nodes..."
            target_url = platform_config["base_url"]
            if query:
                target_url += f"{platform_config['search_path']}{urllib.parse.quote(query)}"
            local_driver.get(target_url)
            time.sleep(4)
            
            headlines = local_driver.find_elements(By.TAG_NAME, 'h4')
            top_stories = [h.text for h in headlines[:3] if h.text]
            if top_stories:
                current_automation_status = f"News update: {', '.join(top_stories[:2])}"
            else:
                current_automation_status = "News page parsed completely."
                
    except Exception as error:
        current_automation_status = f"Error: {str(error)[:35]}..."
        print(f"[SELENIUM FAULT] Pipeline exception: {error}", file=sys.stderr)
        if local_driver:
            try:
                local_driver.quit()
            except:
                pass
        active_driver = None
    finally:
        try:
            automation_lock.release()
        except RuntimeError:
            pass

# --- HTML / JAVASCRIPT / CSS HUD FRONTEND ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognitive AI OS v3.0</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --glass-bg: rgba(10, 25, 50, 0.6);
            --border-glow: rgba(0, 243, 255, 0.25);
            --font-family: 'Courier New', Courier, monospace;
        }

        body, html {
            margin: 0; padding: 0; width: 100%; height: 100%;
            font-family: var(--font-family);
            background: #010409; overflow: hidden; color: #ffffff;
        }

        #canvas-container {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1;
        }

        .ui-layer {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            z-index: 2; display: grid;
            grid-template-columns: 320px 1fr 380px;
            grid-template-rows: 70px 1fr;
            padding: 20px; box-sizing: border-box; gap: 20px;
            pointer-events: none;
        }

        .interactive { pointer-events: auto; }

        .panel {
            background: var(--glass-bg);
            backdrop-filter: blur(15px);
            border: 1px solid var(--border-glow);
            border-radius: 12px; padding: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 15px rgba(0, 243, 255, 0.05);
            display: flex; flex-direction: column; gap: 15px;
            transition: all 0.3s ease;
        }
        .panel:hover {
            border-color: rgba(0, 243, 255, 0.5);
            box-shadow: 0 8px 32px 0 rgba(0, 243, 255, 0.1), inset 0 0 20px rgba(0, 243, 255, 0.1);
        }

        header { 
            grid-column: 1 / -1; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 0 20px;
            height: 100%;
        }
        header h1 {
            margin: 0; font-size: 20px; letter-spacing: 3px;
            color: var(--neon-blue); text-shadow: 0 0 10px rgba(0,243,255,0.5);
        }
        .widget-data {
            font-size: 13px; color: var(--neon-blue);
            border-left: 2px solid var(--neon-blue); padding-left: 10px;
        }

        .avatar-container {
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 15px;
        }
        .avatar-box { 
            width: 140px; height: 140px; border-radius: 50%; 
            border: 2px dashed var(--neon-blue); 
            display: flex; align-items: center; justify-content: center; position: relative; 
        }
        .avatar-glow { 
            width: 85%; height: 85%; 
            background: radial-gradient(circle, rgba(0,243,255,0.6) 0%, transparent 70%); 
            border-radius: 50%; 
            animation: pulse 2.5s infinite ease-in-out; 
        }
        @keyframes pulse { 
            0%, 100% { transform: scale(0.9); opacity: 0.5; filter: drop-shadow(0 0 2px rgba(0,243,255,0.4)); } 
            50% { transform: scale(1.1); opacity: 1; filter: drop-shadow(0 0 15px rgba(0,243,255,0.8)); } 
        }

        .sys-btn {
            background: rgba(0, 243, 255, 0.05); 
            border: 1px solid var(--neon-blue); 
            color: var(--neon-blue); padding: 12px; 
            cursor: pointer; border-radius: 6px; font-family: var(--font-family);
            font-weight: bold; letter-spacing: 1px; transition: all 0.2s ease;
        }
        .sys-btn:hover {
            background: var(--neon-blue); color: #000;
            box-shadow: 0 0 15px var(--neon-blue);
        }
        .btn-danger {
            border-color: #da3633;
            color: #da3633;
        }
        .btn-danger:hover {
            background-color: #da3633;
            color: #fff;
            box-shadow: 0 0 15px #da3633;
        }

        .metrics-grid {
            display: grid; grid-template-columns: 1fr; gap: 10px; font-size: 12px;
        }
        .metric-card {
            background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05);
            padding: 10px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;
        }
        .metric-value { font-weight: bold; color: var(--neon-blue); }

        .network-canvas { 
            width: 100%; height: 150px; background: rgba(0,0,0,0.4); 
            border-radius: 8px; border: 1px solid rgba(0,243,255,0.1);
        }

        .chat-section { display: flex; flex-direction: column; flex-grow: 1; min-height: 0; }
        #chat-output { 
            flex-grow: 1; overflow-y: auto; font-size: 12px; 
            margin-bottom: 12px; border-bottom: 1px solid var(--border-glow);
            padding-right: 5px; display: flex; flex-direction: column; gap: 8px;
        }
        #chat-output::-webkit-scrollbar { width: 4px; }
        #chat-output::-webkit-scrollbar-thumb { background: var(--neon-blue); border-radius: 2px; }

        .chat-msg { margin: 2px 0; line-height: 1.4; }
        .user-msg { color: #88c0d0; }
        .ai-msg { color: var(--neon-blue); }

        .console-input {
            background: rgba(0,0,0,0.6); border: 1px solid var(--neon-blue); 
            color: #fff; padding: 12px; border-radius: 6px;
            font-family: var(--font-family); width: calc(100% - 26px); outline: none;
            box-shadow: inset 0 0 5px rgba(0,243,255,0.2);
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>

    <div id="canvas-container"></div>

    <div class="ui-layer">
        <header class="panel interactive">
            <h1>COGNITIVE AI OS v3.0</h1>
            <div style="display: flex; gap: 20px;">
                <div class="widget-data" id="time-widget">SYSTEM TIME: --:--:--</div>
            </div>
        </header>

        <div class="panel interactive">
            <h3 style="margin: 0; color: var(--neon-blue); font-size: 13px; border-bottom: 1px solid rgba(0,243,255,0.2); padding-bottom: 5px;">[01] COGNITIVE AVATAR NODE</h3>
            <div class="avatar-container">
                <div class="avatar-box">
                    <div class="avatar-glow" id="avatar-core"></div>
                </div>
                <button id="mic-btn" class="sys-btn" style="width: 100%;">INITIALIZE SPEECH COMMS</button>
            </div>
            
            <h3 style="margin: 10px 0 0 0; color: var(--neon-blue); font-size: 13px; border-bottom: 1px solid rgba(0,243,255,0.2); padding-bottom: 5px;">[02] ANALYTICS TELEMETRY</h3>
            <div class="metrics-grid">
                <div class="metric-card">
                    <span>CPU MATRIX</span>
                    <span id="cpu-metric" class="metric-value">--%</span>
                </div>
                <div class="metric-card">
                    <span>RAM LOAD</span>
                    <span id="ram-metric" class="metric-value">--%</span>
                </div>
                <div class="metric-card">
                    <span>AUTOMATION</span>
                    <span id="auto-metric" class="metric-value" style="font-size:10px; text-align:right;">IDLE</span>
                </div>
            </div>
            
            <button id="kill-btn" class="sys-btn btn-danger" style="margin-top:auto;">KILL ACTIVE DRIVERS</button>
        </div>

        <div></div>

        <div class="panel interactive">
            <h3 style="margin: 0; color: var(--neon-blue); font-size: 13px; border-bottom: 1px solid rgba(0,243,255,0.2); padding-bottom: 5px;">[03] NEURAL NETWORK VISUALIZER</h3>
            <canvas id="neural-canvas" class="network-canvas"></canvas>

            <h3 style="margin: 10px 0 0 0; color: var(--neon-blue); font-size: 13px; border-bottom: 1px solid rgba(0,243,255,0.2); padding-bottom: 5px;">[04] COGNITIVE CHAT RECORDS</h3>
            <div class="chat-section">
                <div id="chat-output">
                    <div class="chat-msg ai-msg"><strong>[JARVIS]:</strong> Core mainframe operational. Awaiting command parameters.</div>
                </div>
                <input type="text" id="chat-input" class="console-input" placeholder="Execute command..." autocomplete="off">
            </div>
        </div>
    </div>

    <script>
        // --- 1. THREE.JS 3D BACKGROUND ---
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 1000);
        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        container.appendChild(renderer.domElement);

        const particleCount = 180;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const velocities = [];
        let systemSpeedMultiplier = 1.0;

        for (let i = 0; i < particleCount * 3; i += 3) {
            positions[i] = (Math.random() - 0.5) * 800;
            positions[i + 1] = (Math.random() - 0.5) * 800;
            positions[i + 2] = (Math.random() - 0.5) * 800;
            velocities.push({
                x: (Math.random() - 0.5) * 0.4,
                y: (Math.random() - 0.5) * 0.4,
                z: (Math.random() - 0.5) * 0.4
            });
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        const material = new THREE.PointsMaterial({ color: 0x00f3ff, size: 3.5, transparent: true, opacity: 0.65 });
        const particleSystem = new THREE.Points(geometry, material);
        scene.add(particleSystem);
        camera.position.z = 250;

        function animate3D() {
            requestAnimationFrame(animate3D);
            const positionsArr = particleSystem.geometry.attributes.position.array;
            
            for (let i = 0; i < particleCount; i++) {
                const idx = i * 3;
                positionsArr[idx] += velocities[i].x * systemSpeedMultiplier;
                positionsArr[idx + 1] += velocities[i].y * systemSpeedMultiplier;
                positionsArr[idx + 2] += velocities[i].z * systemSpeedMultiplier;

                if (Math.abs(positionsArr[idx]) > 400) velocities[i].x *= -1;
                if (Math.abs(positionsArr[idx + 1]) > 400) velocities[i].y *= -1;
                if (Math.abs(positionsArr[idx + 2]) > 400) velocities[i].z *= -1;
            }
            particleSystem.geometry.attributes.position.needsUpdate = true;
            particleSystem.rotation.y += 0.0008 * systemSpeedMultiplier;
            renderer.render(scene, camera);
        }
        animate3D();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // --- 2. TIME & SYSTEM TELEMETRY ---
        function updateClock() {
            const now = new Date();
            document.getElementById('time-widget').innerText = `SYSTEM TIME: ${now.toTimeString().split(' ')[0]}`;
        }
        setInterval(updateClock, 1000);
        updateClock();

        function updateTelemetry() {
            fetch('/api/system-metrics')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('cpu-metric').innerText = `${data.cpu}%`;
                    document.getElementById('ram-metric').innerText = `${data.ram}%`;
                    document.getElementById('auto-metric').innerText = data.automation_status.toUpperCase();
                })
                .catch(err => console.warn("Failed fetching dashboard status metrics: ", err));
        }
        setInterval(updateTelemetry, 1500);
        updateTelemetry();

        // --- 3. SPEECH RECOGNITION & TTS VOICE ASSISTANT ---
        const micBtn = document.getElementById('mic-btn');
        const avatarCore = document.getElementById('avatar-core');
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US';

            micBtn.addEventListener('click', () => {
                recognition.start();
                avatarCore.style.background = "radial-gradient(circle, rgba(255,0,85,0.8) 0%, transparent 70%)";
                avatarCore.style.animation = "pulse 0.4s infinite";
                micBtn.innerText = "CAPTURING AUDIO DATA...";
                systemSpeedMultiplier = 0.3; // Breathing dynamic transition on voice active
            });

            recognition.onresult = (event) => {
                const speechToText = event.results[0][0].transcript;
                processCommand(speechToText);
            };

            recognition.onend = () => {
                avatarCore.style.background = "radial-gradient(circle, rgba(0,243,255,0.6) 0%, transparent 70%)";
                avatarCore.style.animation = "pulse 2.5s infinite ease-in-out";
                micBtn.innerText = "INITIALIZE SPEECH COMMS";
                systemSpeedMultiplier = 1.0;
            };
        } else {
            micBtn.innerText = "SPEECH ENGINE UNSUPPORTED";
            micBtn.disabled = true;
        }

        function speak(text) {
            const synth = window.speechSynthesis;
            if (synth.speaking) synth.cancel();
            
            const utterance = new SpeechSynthesisUtterance(text);
            avatarCore.style.animation = "pulse 0.3s infinite";
            systemSpeedMultiplier = 1.8; // System speed up while speaking response
            utterance.onend = () => {
                avatarCore.style.animation = "pulse 2.5s infinite ease-in-out";
                systemSpeedMultiplier = 1.0;
            };
            synth.speak(utterance);
        }

        // --- 4. HUD CHAT MANAGEMENT & DYNAMIC ACTIONS ---
        const chatOutput = document.getElementById('chat-output');
        const chatInput = document.getElementById('chat-input');
        const killBtn = document.getElementById('kill-btn');

        function appendMessage(sender, text, url = null) {
            const container = document.createElement('div');
            container.className = `chat-msg ${sender === 'USER' ? 'user-msg' : 'ai-msg'}`;
            let baseHTML = `<strong>[${sender}]:</strong> ${text}`;
            if (url) {
                baseHTML += ` <a href="${url}" target="_blank" style="color:#00f3ff; text-decoration: underline;">Open Link</a>`;
            }
            container.innerHTML = baseHTML;
            chatOutput.appendChild(container);
            chatOutput.scrollTop = chatOutput.scrollHeight;
        }

        function processCommand(userText) {
            if (!userText.trim()) return;
            appendMessage("USER", userText);
            triggerNeuralSpike();

            fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: userText })
            })
            .then(res => res.json())
            .then(data => {
                appendMessage("JARVIS", data.action, data.url);
                speak(data.action);
                triggerNeuralSpike();

                // DYNAMIC REDIRECT ACTION:
                // If the command returned a dynamic URL route, launch it immediately in a new browser tab!
                if (data.url) {
                    setTimeout(() => {
                        window.open(data.url, '_blank');
                    }, 800);
                }
            });
        }

        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                processCommand(chatInput.value);
                chatInput.value = '';
            }
        });

        killBtn.addEventListener('click', () => {
            fetch('/api/close_session', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    appendMessage("JARVIS", data.action);
                    speak(data.action);
                });
        });

        // --- 5. NEURAL NETWORK VISUALIZER ---
        const canvas = document.getElementById('neural-canvas');
        const ctx = canvas.getContext('2d');
        let nodes = [];

        function resizeCanvas() {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
            initializeNeuralNodes();
        }

        function initializeNeuralNodes() {
            nodes = [];
            const cols = 4;
            const rows = [3, 4, 4, 3];
            const colWidth = canvas.width / (cols + 1);

            for (let i = 0; i < cols; i++) {
                const rowHeight = canvas.height / (rows[i] + 1);
                for (let j = 0; j < rows[i]; j++) {
                    nodes.push({
                        x: colWidth * (i + 1),
                        y: rowHeight * (j + 1),
                        baseActivation: 0.1,
                        currentActivation: 0.1,
                        layer: i
                    });
                }
            }
        }

        function triggerNeuralSpike() {
            nodes.forEach(node => {
                node.currentActivation = Math.random() * 0.9 + 0.1;
            });
        }

        function drawNeuralNetwork() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.lineWidth = 1;
            for (let i = 0; i < nodes.length; i++) {
                for (let j = 0; j < nodes.length; j++) {
                    if (nodes[j].layer === nodes[i].layer + 1) {
                        const distance = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
                        if (distance < canvas.width / 2.5) {
                            const activationAlpha = (nodes[i].currentActivation + nodes[j].currentActivation) / 2;
                            ctx.strokeStyle = `rgba(0, 243, 255, ${activationAlpha * 0.3})`;
                            ctx.beginPath();
                            ctx.moveTo(nodes[i].x, nodes[i].y);
                            ctx.lineTo(nodes[j].x, nodes[j].y);
                            ctx.stroke();
                        }
                    }
                }
            }

            nodes.forEach(node => {
                ctx.beginPath();
                ctx.arc(node.x, node.y, 4.5, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 243, 255, ${node.currentActivation})`;
                ctx.shadowColor = 'rgba(0, 243, 255, 0.8)';
                ctx.shadowBlur = node.currentActivation * 10;
                ctx.fill();
                ctx.shadowBlur = 0;

                if (node.currentActivation > node.baseActivation) {
                    node.currentActivation -= 0.01;
                }
            });

            requestAnimationFrame(drawNeuralNetwork);
        }

        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        drawNeuralNetwork();
    </script>
</body>
</html>
"""

# --- DYNAMIC ENDPOINT ROUTING MANAGEMENT ---

def build_api_payload(status, action, url=""):
    """Helper payload builder; must be defined before referenced by endpoints."""
    return jsonify({"status": status, "action": action, "url": url})


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/system-metrics", methods=["GET"])
def get_system_metrics():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    return jsonify({
        "cpu": cpu,
        "ram": ram,
        "automation_status": current_automation_status
    })


@app.route("/api/command", methods=["POST"])
def process_incoming_command():
    try:
        payload = request.get_json(force=True) or {}
        raw_input = payload.get("command", "").strip()
        if not raw_input:
            return build_api_payload("empty", "No payload execution vector supplied.")
        
        command = raw_input.lower()
        print(f"[INGRESS] Routing Vector Received -> {command}")
        
        if any(token in command for token in ["system", "status", "connected", "dashboard"]):
            return build_api_payload("success", "Dynamic infrastructure matrix operational.")
        
        platform, query = resolve_intent_and_query(command)
        if platform:
            platform_config = PLATFORM_REGISTRY[platform]
            
            # Catch structural instructions requiring automation
            if platform_config["has_automation"] and any(
                act in command for act in ["login", "automation", "run", "start", "scrape", "open"]
            ):
                if automation_lock.locked():
                    return build_api_payload("busy", "Selenium instance pipeline is currently locked.")
                
                threading.Thread(target=run_platform_automation, args=(platform, query), daemon=True).start()
                return build_api_payload(
                    "success",
                    f"Triggered active automation workflow on {platform.title()}.",
                    platform_config["base_url"],
                )
            
            # Fallback out to dynamic URI links if automation isn't flagged
            if query:
                if platform == "myntra":
                    target_url = f"{platform_config['base_url']}/{urllib.parse.quote(query)}"
                else:
                    target_url = f"{platform_config['base_url']}{platform_config['search_path']}{urllib.parse.quote(query)}"
                
                return build_api_payload(
                    "success",
                    f"Dynamic routing mapping for {platform.title()} searching for '{query}'.",
                    target_url,
                )
                
            return build_api_payload(
                "success",
                f"Routing request forward to {platform.title()} root node.",
                platform_config["base_url"],
            )
            
        fallback_target = f"https://www.google.com/search?q={urllib.parse.quote(raw_input)}"
        return build_api_payload(
            "success",
            f"No localized workspace hit. Default fallback query initiated.",
            fallback_target,
        )
    except Exception as runtime_error:
        print(f"[CRITICAL ERROR] Process pipeline crashed: {runtime_error}", file=sys.stderr)
        return jsonify({
            "status": "error",
            "action": "Internal API infrastructure exception encountered.",
            "details": str(runtime_error),
        }), 500


@app.route("/api/close_session", methods=["POST"])
def terminate_orphaned_drivers():
    global active_driver, current_automation_status
    try:
        if automation_lock.locked():
            try:
                automation_lock.release()
            except RuntimeError:
                pass

        if active_driver:
            try:
                active_driver.quit()
            except Exception as e:
                print(f"[TEARDOWN WARN] Active session quit cleanly failed: {e}", file=sys.stderr)
            finally:
                active_driver = None
            
            current_automation_status = "Teardown complete."
            return build_api_payload("success", "Active infrastructure nodes terminated cleanly.")
        
        current_automation_status = "IDLE"
        return build_api_payload("empty", "No standalone processes found active.")
    except Exception as error:
        return build_api_payload("error", f"Node teardown exception: {str(error)}")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("    COGNITIVE SPEECH AI OS v3.0")
    print("    Scope: Unified HUD & Registry Route Pipeline")
    print("    Endpoint Node: http://127.0.0.1:5000")
    print("=" * 65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
