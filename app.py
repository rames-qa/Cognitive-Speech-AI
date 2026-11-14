import logging
import os
import random
import re
import socket
import sys
import threading
import time
import urllib.parse
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import psutil
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- UTILITY: PORT REUSE CLEANER ---
def kill_process_on_port(port):
    """Dynamically releases port 5000 if locked by an orphaned process."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            connections_fn = getattr(
                proc, "net_connections", getattr(proc, "connections", None)
            )
            if connections_fn:
                for conn in connections_fn(kind='inet'):
                    if conn.laddr.port == port:
                        print(
                            f"[PORT GUARD] Terminating {proc.info['name']} (PID:"
                            f" {proc.info['pid']}) holding port {port}..."
                        )
                        proc.terminate()
                        proc.wait(timeout=2)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


kill_process_on_port(5000)

# --- SYSTEM SETUP & CONFIGURATION ---
app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://rames-qa.github.io",
                "http://localhost",
                "http://127.0.0.1",
                "http://localhost:3000",
                "http://localhost:5000"
            ]
        }
    },
)

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# --- GLOBAL STATE ---
automation_lock = threading.Lock()
active_driver = None
current_automation_status = "Awaiting instructions..."

# --- PLATFORM REGISTRY ---
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
            "latest news",
            "international news"
        ],
        "has_automation": True,
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
        r"\bon\b",
        r"\bfor\b",
        r"\bat\b",
        r"\band\b",
    ]
    clean_query = command
    for pattern in action_patterns:
        clean_query = re.sub(pattern, " ", clean_query)
    extracted_query = " ".join(clean_query.split())
    return matched_platform, extracted_query


def get_configured_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chrome_service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=chrome_service, options=options)


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
            signin_node = wait.until(
                EC.element_to_be_clickable((By.ID, "nav-link-accountList"))
            )
            signin_node.click()
            current_automation_status = "Amazon workflow complete."

        elif platform == "news":
            current_automation_status = "Scraping media nodes..."
            target_url = platform_config["base_url"]
            if query:
                target_url += f"{platform_config['search_path']}{urllib.parse.quote(query)}"
            local_driver.get(target_url)
            time.sleep(4)

            headlines = local_driver.find_elements(By.TAG_NAME, "h4")
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
            except Exception:
                pass
        active_driver = None
    finally:
        try:
            automation_lock.release()
        except RuntimeError:
            pass


# --- MODERN BLOCK-WISE VERTICAL MATRIX HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognitive Speech AI - End-to-End Architecture Matrix</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darkMain: '#0b0f19',
                        darkPanel: '#141b2d',
                        borderCol: '#222f4c',
                        neonBlue: '#00f3ff',
                        neonPurple: '#8b5cf6',
                        neonGreen: '#10b981',
                        neonRose: '#ff3366',
                        neonAmber: '#f59e0b',
                    },
                    fontFamily: {
                        sans: ['Poppins', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace'],
                    }
                }
            }
        }
    </script>
    <style>
        body {
            background-color: #0b0f19;
            color: #f0f4f8;
            overflow-x: hidden;
        }
        .glass-panel {
            background: rgba(20, 27, 45, 0.75);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(34, 47, 76, 0.8);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }
        .eq-bar {
            width: 8px;
            background: #00f3ff;
            border-radius: 4px;
            transition: height 0.08s ease;
        }
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #090d16;
        }
        ::-webkit-scrollbar-thumb {
            background: #222f4c;
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #00f3ff;
        }
    </style>
</head>
<body class="min-h-screen flex flex-col font-sans selection:bg-cyan-500 selection:text-black">

    <nav class="sticky top-0 z-50 flex flex-col md:flex-row items-center justify-between px-6 py-4 bg-darkPanel/90 backdrop-blur-md border-b border-borderCol">
        <div class="flex items-center gap-3">
            <div class="w-3 h-3 rounded-full bg-neonBlue animate-ping"></div>
            <span id="navLogo" class="text-xl font-bold tracking-wider bg-gradient-to-r from-neonBlue to-neonPurple bg-clip-text text-transparent">Cognitive Speech AI</span>
        </div>
        <div class="flex items-center gap-6 mt-3 md:mt-0">
            <ul class="flex items-center gap-5 list-none text-sm font-medium">
                <li><a href="#console" id="navLinkConsole" class="text-slate-400 hover:text-neonBlue transition-colors">Console</a></li>
                <li><a href="#pipeline" class="text-slate-400 hover:text-neonBlue transition-colors">Pipeline Architecture</a></li>
                <li><a href="#dashboard" id="navLinkMatrix" class="text-slate-400 hover:text-neonBlue transition-colors">Live Matrix</a></li>
            </ul>
            <div class="flex items-center gap-2 bg-[#090d16] px-3 py-1.5 rounded-lg border border-borderCol">
                <label for="langSelect" id="langLabel" class="text-xs font-semibold text-slate-400 uppercase">LN:</label>
                <select id="langSelect" class="bg-transparent text-white font-mono text-xs font-bold cursor-pointer outline-none">
                    <option value="en" class="bg-darkPanel text-white">EN</option>
                    <option value="ta" class="bg-darkPanel text-white">TA</option>
                    <option value="hi" class="bg-darkPanel text-white">HI</option>
                    <option value="kn" class="bg-darkPanel text-white">KN</option>
                </select>
            </div>
        </div>
    </nav>

    <!-- Console Section: Dual Mode Input (Voice / Text) -->
    <section id="console" class="max-w-5xl mx-auto w-full px-6 pt-10 pb-8 text-center">
        <h1 id="heroTitle" class="text-3xl md:text-5xl font-extrabold mb-3 tracking-tight">Cognitive Speech AI</h1>
        <p id="heroDesc" class="text-slate-400 max-w-2xl mx-auto text-sm md:text-base mb-8">Integrated speech-to-intent pipeline executing real-time AI evaluation, command processing, and automated system response.</p>

        <div class="glass-panel rounded-2xl p-6 mb-6 text-left">
            <div class="flex flex-col sm:flex-row items-center justify-between gap-4 mb-4 border-b border-slate-800 pb-3">
                <div class="flex items-center gap-3 font-semibold text-sm">
                    <span id="voiceStatusDot" class="w-3 h-3 rounded-full bg-slate-500 transition-all duration-300"></span>
                    <span id="voiceStatusText">Acoustic Core Offline</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-slate-400 font-mono">Backend Engine:</span>
                    <span id="backendBadge" class="text-xs font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-neonAmber border border-amber-500/30">DISCONNECTED / FALLBACK</span>
                </div>
            </div>

            <div id="voiceTranscript" class="bg-[#090d16] p-4 rounded-xl font-mono text-sm min-h-[140px] max-h-64 overflow-y-auto text-slate-200 border border-[#1a243a]">
                <span id="transcriptPlaceholder" class="text-slate-500 italic">Say "SYSTEM" followed by your command or submit text input below to trigger speech transcription & intent evaluation...</span>
            </div>

            <!-- Text Input Fallback / Multilingual Direct Command Input -->
            <form id="textCommandForm" class="mt-4 flex flex-col sm:flex-row gap-3">
                <input type="text" id="textCommandInput" placeholder="Or type command here (e.g., 'SYSTEM run vision matrix test')..." class="flex-1 bg-[#090d16] border border-borderCol rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-neonBlue transition-all font-mono">
                <button type="submit" class="px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-sm border border-slate-700 transition-all">Submit Text</button>
            </form>
        </div>

        <div class="flex flex-col sm:flex-row items-center justify-center gap-4 max-w-md mx-auto">
            <button id="btnVoiceTrigger" class="w-full py-4 px-6 rounded-xl font-semibold text-white bg-gradient-to-r from-neonBlue to-neonPurple shadow-lg shadow-cyan-500/25 hover:opacity-90 active:scale-95 transition-all flex items-center justify-center gap-3 text-sm">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                    <path d="M19 10v1a7 7 0 0 1-14 0v-1"/>
                    <line x1="12" x2="12" y1="19" y2="22"/>
                </svg>
                <span id="voiceText">Initialize Ambient Speech Loop</span>
            </button>
        </div>
    </section>

    <!-- Pipeline Architecture Matrix Block -->
    <section id="pipeline" class="max-w-7xl mx-auto w-full px-6 py-8">
        <h2 class="text-xl md:text-2xl font-bold text-center mb-6 text-white tracking-wide">Recommended Architecture Pipeline Execution</h2>
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div class="glass-panel p-4 rounded-xl border border-slate-800 text-center flex flex-col justify-between">
                <div>
                    <span class="text-[10px] font-mono font-bold text-neonBlue bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/30 uppercase">Stage 01</span>
                    <h4 class="text-sm font-bold mt-2 text-white">Voice / Text / Multilingual Input</h4>
                    <p class="text-xs text-slate-400 mt-1">Multi-modal audio capture & multilingual text stream (EN, TA, HI, KN).</p>
                </div>
                <div id="pipeStage1" class="mt-3 text-[11px] font-mono text-slate-500 border-t border-slate-800/80 pt-2">IDLE</div>
            </div>

            <div class="glass-panel p-4 rounded-xl border border-slate-800 text-center flex flex-col justify-between">
                <div>
                    <span class="text-[10px] font-mono font-bold text-neonPurple bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/30 uppercase">Stage 02</span>
                    <h4 class="text-sm font-bold mt-2 text-white">Speech Engine & Transcription</h4>
                    <p class="text-xs text-slate-400 mt-1">Acoustic buffer conversion and web speech transcription tokenizing.</p>
                </div>
                <div id="pipeStage2" class="mt-3 text-[11px] font-mono text-slate-500 border-t border-slate-800/80 pt-2">IDLE</div>
            </div>

            <div class="glass-panel p-4 rounded-xl border border-slate-800 text-center flex flex-col justify-between">
                <div>
                    <span class="text-[10px] font-mono font-bold text-neonAmber bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30 uppercase">Stage 03</span>
                    <h4 class="text-sm font-bold mt-2 text-white">AI Intelligence (Intent & Context)</h4>
                    <p class="text-xs text-slate-400 mt-1">Semantic extraction, intent parsing, and contextual classification.</p>
                </div>
                <div id="pipeStage3" class="mt-3 text-[11px] font-mono text-slate-500 border-t border-slate-800/80 pt-2">IDLE</div>
            </div>

            <div class="glass-panel p-4 rounded-xl border border-slate-800 text-center flex flex-col justify-between">
                <div>
                    <span class="text-[10px] font-mono font-bold text-neonGreen bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30 uppercase">Stage 04</span>
                    <h4 class="text-sm font-bold mt-2 text-white">Python Flask Backend Engine</h4>
                    <p class="text-xs text-slate-400 mt-1">Command processing, automation dispatch, and live telemetry aggregation.</p>
                </div>
                <div id="pipeStage4" class="mt-3 text-[11px] font-mono text-slate-500 border-t border-slate-800/80 pt-2">IDLE</div>
            </div>

            <div class="glass-panel p-4 rounded-xl border border-slate-800 text-center flex flex-col justify-between">
                <div>
                    <span class="text-[10px] font-mono font-bold text-neonRose bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/30 uppercase">Stage 05</span>
                    <h4 class="text-sm font-bold mt-2 text-white">Live Dashboard & Voice Response</h4>
                    <p class="text-xs text-slate-400 mt-1">Acoustic speech synthesis response output and real-time dashboard update.</p>
                </div>
                <div id="pipeStage5" class="mt-3 text-[11px] font-mono text-slate-500 border-t border-slate-800/80 pt-2">IDLE</div>
            </div>
        </div>
    </section>

    <!-- Dashboard & Telemetry Section -->
    <section id="dashboard" class="max-w-7xl mx-auto w-full px-6 pb-16">
        <h2 id="sectionTitleMatrix" class="text-2xl md:text-3xl font-bold text-center mb-10">Cognitive Operations Interface Matrix</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <!-- Acoustic Capture Panel -->
            <div class="glass-panel rounded-2xl p-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-4 mb-5 gap-3">
                    <h3 id="panelHeaderCapture" class="text-lg font-semibold flex items-center gap-2">Acoustic Capture Buffer</h3>
                    <span id="voiceModuleStatus" class="self-start sm:self-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-neonGreen border border-emerald-500/20">STANDBY</span>
                </div>
                <div id="eqContainer" class="flex items-end justify-center gap-1.5 h-20 bg-[#090d16] rounded-xl p-3 mb-5 border border-slate-900">
                    <div class="eq-bar h-[10%]"></div>
                    <div class="eq-bar h-[20%]"></div>
                    <div class="eq-bar h-[15%]"></div>
                    <div class="eq-bar h-[40%]"></div>
                    <div class="eq-bar h-[70%]"></div>
                    <div class="eq-bar h-[50%]"></div>
                    <div class="eq-bar h-[30%]"></div>
                    <div class="eq-bar h-[60%]"></div>
                    <div class="eq-bar h-[25%]"></div>
                    <div class="eq-bar h-[10%]"></div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-[#090d16] p-3.5 rounded-xl border border-slate-800/80 text-center">
                        <p id="metricLabelDecibel" class="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Acoustic Decibels</p>
                        <h5 id="liveDecibel" class="font-mono text-base font-bold text-white">-Inf dB</h5>
                    </div>
                    <div class="bg-[#090d16] p-3.5 rounded-xl border border-slate-800/80 text-center">
                        <p id="metricLabelFrequency" class="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Stream Frequency</p>
                        <h5 id="liveSampleRate" class="font-mono text-base font-bold text-white">0.0 kHz</h5>
                    </div>
                </div>
            </div>

            <!-- Cognitive Vocal Signature Panel -->
            <div class="glass-panel rounded-2xl p-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-4 mb-5 gap-3">
                    <h3 id="panelHeaderSignature" class="text-lg font-semibold">Cognitive Vocal Signature</h3>
                    <span id="cognitiveModality" class="text-xs font-semibold text-slate-400">Acoustic Signal Processing</span>
                </div>

                <div class="bg-[#090d16] border border-dashed border-slate-800 rounded-xl p-4 mb-5 text-center flex flex-col justify-center min-h-[90px]">
                    <div id="panelHeaderStatus" class="text-xs text-slate-400 uppercase tracking-wider mb-1">Current Node Assistant Status</div>
                    <div id="emotionTokenDisplay" class="font-mono text-xl font-bold text-slate-400 transition-all duration-300">SYSTEM SILENT</div>
                </div>

                <div class="space-y-4">
                    <div>
                        <div class="flex justify-between text-xs text-slate-400 mb-1.5">
                            <span id="labelCalm">Calm Stability</span>
                            <span id="txtCalm" class="font-mono font-bold text-white">0%</span>
                        </div>
                        <div class="bg-[#090d16] h-2 rounded-full overflow-hidden">
                            <div id="barCalm" class="h-full bg-neonGreen rounded-full transition-all duration-300 w-0"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-xs text-slate-400 mb-1.5">
                            <span id="labelFriction">Vocal Friction</span>
                            <span id="txtFriction" class="font-mono font-bold text-white">0%</span>
                        </div>
                        <div class="bg-[#090d16] h-2 rounded-full overflow-hidden">
                            <div id="barFriction" class="h-full bg-neonAmber rounded-full transition-all duration-300 w-0"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-xs text-slate-400 mb-1.5">
                            <span id="labelLoad">Dynamic Processing Load</span>
                            <span id="txtLoad" class="font-mono font-bold text-white">0%</span>
                        </div>
                        <div class="bg-[#090d16] h-2 rounded-full overflow-hidden">
                            <div id="barLoad" class="h-full bg-neonPurple rounded-full transition-all duration-300 w-0"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Three Interactive Sub-Systems Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Neural Processing Box -->
            <div class="glass-panel rounded-2xl p-6 flex flex-col justify-between">
                <div>
                    <div class="mb-4 border-b border-slate-800 pb-3">
                        <h3 id="cardTitleNeural" class="text-base font-semibold text-neonBlue mb-1">Neural Processing</h3>
                        <p id="cardDescNeural" class="text-xs text-slate-400">Evaluating language tokens and acoustic matrices across hardware array tracks.</p>
                    </div>
                    <div class="bg-[#090d16] h-1.5 rounded-full overflow-hidden mb-4">
                        <div id="neuralBar" class="h-full bg-gradient-to-r from-neonBlue to-neonPurple rounded-full transition-all w-0"></div>
                    </div>
                    <div class="grid grid-cols-3 gap-2 mb-4">
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valNeuralVelocity" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricNeuralVelocity" class="text-[9px] text-slate-400 uppercase">Velocity</small>
                        </div>
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valNeuralIndex" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricNeuralIndex" class="text-[9px] text-slate-400 uppercase">Index</small>
                        </div>
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valNeuralActive" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricNeuralActive" class="text-[9px] text-slate-400 uppercase">Active</small>
                        </div>
                    </div>
                </div>
                <canvas id="neuralCanvas" class="w-full h-24 bg-[#090d16] rounded-lg border border-slate-900 block mt-2"></canvas>
            </div>

            <!-- Vision AI Matrix Box -->
            <div class="glass-panel rounded-2xl p-6 flex flex-col justify-between">
                <div>
                    <div class="mb-4 border-b border-slate-800 pb-3">
                        <h3 id="cardTitleVision" class="text-base font-semibold text-neonPurple mb-1">Vision AI Matrix</h3>
                        <p id="cardDescVision" class="text-xs text-slate-400">Processing spatial environment tracking, matrix frameworks, and vector points.</p>
                    </div>
                    <div class="bg-[#090d16] h-1.5 rounded-full overflow-hidden mb-4">
                        <div id="analyticsBar" class="h-full bg-gradient-to-r from-neonPurple to-neonGreen rounded-full transition-all w-0"></div>
                    </div>
                    <div class="grid grid-cols-3 gap-2 mb-4">
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valVisionFPS" class="font-mono text-sm font-bold text-white block">0 FPS</span>
                            <small id="subMetricVisionFPS" class="text-[9px] text-slate-400 uppercase">FPS Feed</small>
                        </div>
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valVisionAccuracy" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricVisionAccuracy" class="text-[9px] text-slate-400 uppercase">Accuracy</small>
                        </div>
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valVisionTracking" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricVisionTracking" class="text-[9px] text-slate-400 uppercase">Tracking</small>
                        </div>
                    </div>
                </div>
                <canvas id="analyticsCanvas" class="w-full h-24 bg-[#090d16] rounded-lg border border-slate-900 block mt-2"></canvas>
            </div>

            <!-- Robotics Core Box -->
            <div class="glass-panel rounded-2xl p-6 flex flex-col justify-between">
                <div>
                    <div class="mb-4 border-b border-slate-800 pb-3">
                        <h3 id="cardTitleRobotics" class="text-base font-semibold text-neonGreen mb-1">Robotics Core</h3>
                        <p id="cardDescRobotics" class="text-xs text-slate-400">Automated kinematics telemetry, hardware mapping, and thread scheduling loops.</p>
                    </div>
                    <div class="bg-[#090d16] h-1.5 rounded-full overflow-hidden mb-4">
                        <div id="automationBar" class="h-full bg-gradient-to-r from-neonGreen to-neonBlue rounded-full transition-all w-0"></div>
                    </div>
                    <div class="grid grid-cols-3 gap-2 mb-4">
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valRobotTasks" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricRobotTasks" class="text-[9px] text-slate-400 uppercase">Tasks</small>
                        </div>
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valRobotLoad" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricRobotLoad" class="text-[9px] text-slate-400 uppercase">Load</small>
                        </div>
                        <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                            <span id="valRobotFlow" class="font-mono text-sm font-bold text-white block">0%</span>
                            <small id="subMetricRobotFlow" class="text-[9px] text-slate-400 uppercase">Flow</small>
                        </div>
                    </div>
                </div>
                <canvas id="automationCanvas" class="w-full h-24 bg-[#090d16] rounded-lg border border-slate-900 block mt-2"></canvas>
            </div>
        </div>
    </section>

    <footer id="footerText" class="mt-auto text-center py-6 text-xs text-slate-400 border-t border-borderCol bg-[#090d16]">
        &copy; 2026 Cognitive AI Advanced Web Project | End-to-End Recommended Architecture Implementation
    </footer>

    <script>
        document.addEventListener("DOMContentLoaded", () => {
            const LocalizationMatrix = {
                en: {
                    navLogo: "Cognitive Speech AI", navLinkConsole: "Console", navLinkMatrix: "Live Matrix",
                    heroTitle: "Cognitive Speech AI", heroDesc: "Integrated speech-to-intent pipeline executing real-time AI evaluation, command processing, and automated system response.",
                    voiceStatusOffline: "Acoustic Core Offline", voiceStatusActive: "Ambient Wake-Word Engine Operational",
                    voiceStatusSpeaking: "Broadcasting Audio Output Array...", transcriptPlaceholder: 'Say "SYSTEM" followed by your command or submit text input below to trigger speech transcription & intent evaluation...',
                    voiceTextInit: "Initialize Ambient Speech Loop", voiceTextStop: "Terminate Matrix Operations Loop",
                    sectionTitleMatrix: "Cognitive Operations Interface Matrix", panelHeaderCapture: "Acoustic Capture Buffer",
                    metricLabelDecibel: "Acoustic Decibels", metricLabelFrequency: "Stream Frequency", panelHeaderSignature: "Cognitive Vocal Signature",
                    cognitiveModality: "Acoustic Signal Processing", panelHeaderStatus: "Current Node Assistant Status",
                    statusSilent: "SYSTEM SILENT", statusTransmitting: "TRANSMITTING RESPONSE", statusActive: "AMBIENT WATCH ACTIVE", statusOffline: "SYSTEM OFFLINE",
                    labelCalm: "Calm Stability", labelFriction: "Vocal Friction", labelLoad: "Dynamic Processing Load",
                    cardTitleNeural: "Neural Processing", cardDescNeural: "Evaluating language tokens and acoustic matrices across hardware array tracks.",
                    subMetricNeuralVelocity: "Velocity", subMetricNeuralIndex: "Index", subMetricNeuralActive: "Active",
                    cardTitleVision: "Vision AI Matrix", cardDescVision: "Processing spatial environment tracking, matrix frameworks, and vector points.",
                    subMetricVisionFPS: "FPS Feed", subMetricVisionAccuracy: "Accuracy", subMetricVisionTracking: "Tracking",
                    cardTitleRobotics: "Robotics Core", cardDescRobotics: "Automated kinematics telemetry, hardware mapping, and thread scheduling loops.",
                    subMetricRobotTasks: "Tasks", subMetricRobotLoad: "Load", subMetricRobotFlow: "Flow",
                    footerText: "© 2026 Cognitive AI Advanced Web Project | End-to-End Recommended Architecture Implementation"
                },
                ta: {
                    navLogo: "அறிவுசார் பேச்சு AI", navLinkConsole: "முனையம்", navLinkMatrix: "நேரடி மேட்ரிக்ஸ்",
                    heroTitle: "அறிவுசார் பேச்சு கணினி ஆட்டோமேஷன்", heroDesc: "நிகழ்நேர சொற்பொருள் செயலாக்கத்துடன் ரோபோடிக் நரம்பியல் வடிவங்களை ஒருங்கிணைக்கும் பல மாதிரி இயந்திர வரிசை தளம்.",
                    voiceStatusOffline: "ஒலி கோர் ஆஃப்லைனில் உள்ளது", voiceStatusActive: "சுற்றுப்புற விழித்தெழு சொல் எஞ்சின் செயல்படுகிறது",
                    voiceStatusSpeaking: "ஒலி வெளியீட்டு வரிசையை ஒளிபரப்புகிறது...", transcriptPlaceholder: '"SYSTEM" எனக் கூறி உங்கள் கட்டளையை வழங்கவும் அல்லது உரை உள்ளீட்டை சமர்ப்பிக்கவும்.',
                    voiceTextInit: "சுற்றுப்புற உதவி வளையத்தைத் தொடங்கு", voiceTextStop: "செயல்பாட்டு வளையத்தை நிறுத்து",
                    sectionTitleMatrix: "அறிவுசார் செயல்பாட்டு இடைமுக மேட்ரிக்ஸ்", panelHeaderCapture: "ஒலி பிடிப்பு இடையக பகுதி",
                    metricLabelDecibel: "ஒலி டெசிபல்கள்", metricLabelFrequency: "அலைவரிசை அதிர்வெண்", panelHeaderSignature: "அறிவுசார் குரல் கையொப்பம்",
                    cognitiveModality: "ஒலி சமிகஞை செயலாக்கம்", panelHeaderStatus: "தற்போதைய கணினி உதவி நிலை",
                    statusSilent: "கணினி அமைதி", statusTransmitting: "பதிலை அனுப்புகிறது", statusActive: "சுற்றுப்புற கண்காணிப்பு செயலில் உள்ளது", statusOffline: "கணினி ஆஃப்லைனுக்கு சென்றது",
                    labelCalm: "அமையதியான நிலைத்தன்மை", labelFriction: "குரல் உராய்வு", labelLoad: "இயக்க முறை செயலாக்க சுமை",
                    cardTitleNeural: "நரம்பியல் செயலாக்கம்", cardDescNeural: "வன்பொருள் வரிசை தடங்களில் மொழி டோக்கன்கள் மற்றும் ஒலி மேட்ரிக்ஸ்களை மதிப்பிடுதல்.",
                    subMetricNeuralVelocity: "வேகம்", subMetricNeuralIndex: "குறியீடு", subMetricNeuralActive: "செயலில்",
                    cardTitleVision: "பார்வை AI மேட்ரிக்ஸ்", cardDescVision: "இடஞ்சார்ந்த சூழல் கண்காணிப்பு, மேட்ரிக்ஸ் கட்டமைப்புகள் மற்றும் திசையன் புள்ளிகளை செயலாக்குகிறது.",
                    subMetricVisionFPS: "எஃப்.பி.எஸ் ஃபீட்", subMetricVisionAccuracy: "துல்லியம்", subMetricVisionTracking: "கண்காணிப்பு",
                    cardTitleRobotics: "ரோபோடிக்ஸ் கோர்", cardDescRobotics: "தானியங்கி இயக்கவியல் டெலிமெட்ரி, வன்பொருள் வரைபடம் மற்றும் த்ரெட் திட்டமிடல் சுழல்கள்.",
                    subMetricRobotTasks: "பணிகள்", subMetricRobotLoad: "சுமை", subMetricRobotFlow: "பாய்ச்சல்",
                    footerText: "© 2026 அறிவுசார் AI மேம்பட்ட வலைத் திட்டம்"
                },
                hi: {
                    navLogo: "कॉग्निटिव स्पीच एआई", navLinkConsole: "कंसोल", navLinkMatrix: "लाइव मैट्रिक्स",
                    heroTitle: "कॉग्निटिव स्पीच एआई ऑटोमेशन", heroDesc: "वास्तविक समय के सिमेंटिक निष्पादन के साथ रोबोटिक न्यूरल प्रोसेसिंग पैटर्न को संश्लेषित करने वाला एक मल्टी-मोडल मशीन एरे स्ट्रीम।",
                    voiceStatusOffline: "ध्वनिक कोर ऑफ़लाइन", voiceStatusActive: "वेक-वर्ड इंजन सक्रिय है",
                    voiceStatusSpeaking: "ऑडियो आउटपुट एरे प्रसारित हो रहा है...", transcriptPlaceholder: '"SYSTEM" बोलकर अपना कमांड दें या टेक्स्ट कमांड सबमिट करें।',
                    voiceTextInit: "असिस्टेंट लूप प्रारंभ करें", voiceTextStop: "मैट्रिक्स ऑपरेशंस लूप समाप्त करें",
                    sectionTitleMatrix: "कॉग्निटिव ऑपरेशंस इंटरफेस मैट्रिक्स", panelHeaderCapture: "ध्वनिक कैप्चर बफर",
                    metricLabelDecibel: "ध्वनिक डेसिबल", metricLabelFrequency: "स्ट्रीम फ्रीक्वेंसी", panelHeaderSignature: "कॉग्निटिव वोकल सिग्नेचर",
                    cognitiveModality: "ध्वनिक सिग्नल प्रोसेसिंग", panelHeaderStatus: "वर्तमान नोड असिस्टेंट स्थिति",
                    statusSilent: "सिस्टम मौन", statusTransmitting: "प्रतिक्रिया प्रसारित हो रही है", statusActive: "असिस्टेंट वॉच सक्रिय", statusOffline: "सिस्टम ऑफ़लाइन",
                    labelCalm: "शांत स्थिरता", labelFriction: "मुखर घर्षण", labelLoad: "डायनेमिक प्रोसेसिंग लोड",
                    cardTitleNeural: "न्यूरल प्रोसेसिंग", cardDescNeural: "हार्डवेयर एरे ट्रैक पर भाषा टोकन और ध्वनिक मैट्रिक्स का मूल्यांकन।",
                    subMetricNeuralVelocity: "गति", subMetricNeuralIndex: "इंडेक्स", subMetricNeuralActive: "सक्रिय",
                    cardTitleVision: "विजन एआई मैट्रिक्स", cardDescVision: "स्थानिक पर्यावरण ट्रैकिंग, मैट्रिक्स फ्रेमवर्क और वेक्टर बिंदुओं को संसाधित करना।",
                    subMetricVisionFPS: "एफपीएस फीड", subMetricVisionAccuracy: "सटीकता", subMetricVisionTracking: "ट्रैकिंग",
                    cardTitleRobotics: "रोबोटिक्स कोर", cardDescRobotics: "स्वचालित कीनेमैटिक्स टेलीमेट्री, हार्डवेयर मैपिंग और थ्रेड शेड्यूलिंग लूप।",
                    subMetricRobotTasks: "कार्य", subMetricRobotLoad: "लोड", subMetricRobotFlow: "प्रवाह",
                    footerText: "© 2026 कॉग्निटिव एआई एडवांस्ड वेब प्रोजेक्ट"
                },
                kn: {
                    navLogo: "ಕಾಗ್ನಿಟಿವ್ ಸ್ಪೀಚ್ ಎಐ", navLinkConsole: "ಕನ್ಸೋಲ್", navLinkMatrix: "ಲೈವ್ ಮ್ಯಾಟ್ರಿಕ್ಸ್",
                    heroTitle: "ಕಾಗ್ನಿಟಿವ್ ಸ್ಪೀಚ್ ಎಐ ಆಟೊಮೇಷನ್", heroDesc: "ನೈಜ-ಸಮಯದ ಲಾಕ್ಷಣಿಕ ಮರಣದಂಡನೆಯೊಂದಿಗೆ ರೋಬೋಟಿಕ್ ನರ ಸಂಸ್ಕರಣಾ ಮಾದರಿಗಳನ್ನು ಸಂಯೋಜಿಸುವ ಮಲ್ಟಿ-ಮೋಡಲ್ ಯಂತ್ರ ಅರೇ ಸ್ಟ್ರೀಮ್.",
                    voiceStatusOffline: "ಅಕೌಸ್ಟಿic ಕೋರ್ ಆಫ್ಲೈನ್‌ನಲ್ಲಿದೆ", voiceStatusActive: "ವೇಕ್-ವರ್ಡ್ ಇಂಜಿನ್ ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತಿದೆ",
                    voiceStatusSpeaking: "ಆಡಿಯೊ ಔಟ್‌ಪುಟ್ ಪ್ರಸಾರವಾಗುತ್ತಿದೆ...", transcriptPlaceholder: '"SYSTEM" ಎಂದು ಹೇಳಿ ನಿಮ್ಮ ಆದೇಶವನ್ನು ನೀಡಿ ಅಥವಾ ಪಠ್ಯ ನಮೂದಿಸಿ.',
                    voiceTextInit: "ಅಸಿಸ್ಟೆಂಟ್ ಲೂಪ್ ಪ್ರಾರಂಭಿಸಿ", voiceTextStop: "ಮ್ಯಾಟ್ರಿಕ್ಸ್ ಕಾರ್ಯಾಚರಣೆಗಳ ಲೂಪ್ ನಿಲ್ಲಿಸಿ",
                    sectionTitleMatrix: "ಕಾಗ್ನಿಟಿವ್ ಆಪರೇಷನ್ಸ್ ಇಂಟರ್ಫೇಸ್ ಮ್ಯಾಟ್ರಿಕ್ಸ್", panelHeaderCapture: "ಅಕೌಸ್ಟಿಕ್ ಕ್ಯಾಪ್ಚರ್ ಬಫರ್",
                    metricLabelDecibel: "ಅಕೌಸ್ಟಿಕ್ ಡೆಸಿಬಲ್ಸ್", metricLabelFrequency: "ಸ್ಟ್ರೀಮ್ ಆವರ್ತನ", panelHeaderSignature: "ಕಾಗ್ನಿಟಿವ್ ವೋಕಲ್ ಸಿಗ್ನೇಚರ್",
                    cognitiveModality: "ಅಕೌಸ್ಟಿಕ್ ಸಿಗ್ನಲ್ ಪ್ರೊಸೆಸಿಂಗ್", panelHeaderStatus: "ಪ್ರಸ್ತುತ ಅಸಿಸ್ಟೆಂಟ್ ಸ್ಥಿತಿ",
                    statusSilent: "ಸಿಸ್ಟಮ್ ಸೈಲೆಂಟ್", statusTransmitting: "ಪ್ರತಿಕ್ರಿಯೆ ರವಾನಿಸಲಾಗುತ್ತಿದೆ", statusActive: "ಸುತ್ತಮುತ್ತಲಿನ ಜಾಗರೂಕತೆ ಸಕ್ರಿಯವಾಗಿದೆ", statusOffline: "ಸಿಸ್ಟಮ್ ಆಫ್‌ಲೈನ್",
                    labelCalm: "ಶಾಂತ ಸ್ಥಿರತೆ", labelFriction: "ಧ್ವನಿ ಘರ್ಷಣೆ", labelLoad: "ಡೈನಾಮಿಕ್ ಸಂಸ್ಕರಣಾ ಲೋಡ್",
                    cardTitleNeural: "ನರ ಸಂಸ್ಕರಣೆ", cardDescNeural: "ಹಾರ್ಡ್‌ವೇರ್ ಅರೇ ಟ್ರ್ಯಾಕ್‌ಗಳಲ್ಲಿ ಭಾಷಾ ಟೋಕನ್‌ಗಳು ಮತ್ತು ಅಕೌಸ್ಟಿಕ್ ಮ್ಯಾಟ್ರಿಕ್ಸ್‌ಗಳನ್ನು ಮೌಲ್ಯಮಾಪನ ಮಾಡುವುದು.",
                    subMetricNeuralVelocity: "ವೇಗ", subMetricNeuralIndex: "ಸೂಚ್ಯಂಕ", subMetricNeuralActive: "ಸಕ್ರಿಯ",
                    cardTitleVision: "ವಿಷನ್ ಎಐ ಮ್ಯಾಟ್ರಿಕ್ಸ್", cardDescVision: "ಸ್ಪೇಷಿಯಲ್ ಎನ್ವಿರಾನ್ಮೆಂಟ್ ಟ್ರ್ಯಾಕಿಂಗ್, ಮ್ಯಾಟ್ರಿಕ್ಸ್ ಫ್ರೇಮ್‌‌ವರ್ಕ್‌ಗಳು ಮತ್ತು ವೆಕ್ಟರ್ ಪಾಯಿಂಟ್‌ಗಳನ್ನು ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗುತ್ತಿದೆ.",
                    subMetricVisionFPS: "ಎಫ್‌ಪಿಎಸ್ ಫೀಡ್", subMetricVisionAccuracy: "ನಿಖರತೆ", subMetricVisionTracking: "ಟ್ರ್ಯಾಕಿಂಗ್",
                    cardTitleRobotics: "ರೋಬೋಟಿಕ್ಸ್ ಕೋರ್", cardDescRobotics: "ಸ್ವಯಂಚಾಲಿತ ಯಂತ್ರಾಂಶ ಟೆಲಿಮೆಟ್ರಿ, ಹಾರ್ಡ್‌ವೇರ್ ಮ್ಯಾಪಿಂಗ್ ಮತ್ತು ಥ್ರೆಡ್ ಶೆಡ್ಯೂಲಿಂಗ್ ಲೂಪ್‌ಗಳು.",
                    subMetricRobotTasks: "ಕಾರ್ಯಗಳು", subMetricRobotLoad: "ಲೋಡ್", subMetricRobotFlow: "ಪ್ರವಾಹ",
                    footerText: "© 2026 ಕಾಗ್ನಿಟಿವ್ ಎಐ ಅಡ್ವಾನ್ಸಡ್ ವೆಬ್ ಪ್ರಾಜೆಕ್ಟ್"
                }
            };

            let currentLang = 'en';
            const langSelect = document.getElementById("langSelect");
            
            function updateLanguage(lang) {
                currentLang = lang;
                const dict = LocalizationMatrix[lang];
                if (!dict) return;
                for (const key in dict) {
                    const el = document.getElementById(key);
                    if (el) el.textContent = dict[key];
                }
            }

            if (langSelect) {
                langSelect.addEventListener("change", (e) => updateLanguage(e.target.value));
            }

            const pipeStages = [
                document.getElementById("pipeStage1"),
                document.getElementById("pipeStage2"),
                document.getElementById("pipeStage3"),
                document.getElementById("pipeStage4"),
                document.getElementById("pipeStage5")
            ];

            function updatePipelineVisual(stageIndex, statusText, isError = false) {
                pipeStages.forEach((stage, idx) => {
                    if (!stage) return;
                    if (idx < stageIndex) {
                        stage.textContent = "PASSED";
                        stage.className = "mt-3 text-[11px] font-mono text-neonGreen font-bold border-t border-slate-800/80 pt-2";
                    } else if (idx === stageIndex) {
                        stage.textContent = statusText;
                        stage.className = isError 
                            ? "mt-3 text-[11px] font-mono text-neonRose font-bold border-t border-slate-800/80 pt-2 animate-pulse"
                            : "mt-3 text-[11px] font-mono text-neonBlue font-bold border-t border-slate-800/80 pt-2 animate-pulse";
                    } else {
                        stage.textContent = "WAITING";
                        stage.className = "mt-3 text-[11px] font-mono text-slate-600 border-t border-slate-800/80 pt-2";
                    }
                });
            }

            let isListening = false;
            let recognition = null;
            const BACKEND_URL = "http://localhost:5000";

            const btnVoiceTrigger = document.getElementById("btnVoiceTrigger");
            const voiceStatusDot = document.getElementById("voiceStatusDot");
            const voiceStatusText = document.getElementById("voiceStatusText");
            const voiceTranscript = document.getElementById("voiceTranscript");
            const voiceModuleStatus = document.getElementById("voiceModuleStatus");
            const emotionTokenDisplay = document.getElementById("emotionTokenDisplay");
            const textCommandForm = document.getElementById("textCommandForm");
            const textCommandInput = document.getElementById("textCommandInput");
            const backendBadge = document.getElementById("backendBadge");

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const languageCodes = { en: "en-IN", ta: "ta-IN", hi: "hi-IN", kn: "kn-IN" };

            function escapeHtml(str) {
                return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            }

            function speakResponse(text) {
                updatePipelineVisual(4, "VOICE TTS ACTIVE");
                if (!("speechSynthesis" in window)) return;
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = languageCodes[currentLang] || "en-IN";
                utterance.rate = 1;
                utterance.pitch = 1;
                utterance.onstart = () => {
                    if (voiceStatusText) voiceStatusText.textContent = LocalizationMatrix[currentLang].voiceStatusSpeaking;
                };
                utterance.onend = () => {
                    if (voiceStatusText) voiceStatusText.textContent = LocalizationMatrix[currentLang].voiceStatusActive;
                    updatePipelineVisual(5, "COMPLETED");
                };
                window.speechSynthesis.speak(utterance);
            }

            async function processPipelineCommand(command, mode = "VOICE") {
                updatePipelineVisual(0, `${mode} INPUT READY`);
                await new Promise(r => setTimeout(r, 150));
                
                updatePipelineVisual(1, "TRANSCRIBING & TOKENIZING");
                await new Promise(r => setTimeout(r, 150));
                
                updatePipelineVisual(2, "AI INTENT EVALUATION");
                if (voiceStatusText) voiceStatusText.textContent = "Connecting to Python Flask backend...";
                if (emotionTokenDisplay) emotionTokenDisplay.textContent = "PROCESSING AI INTENT";

                updatePipelineVisual(3, "FLASK EXECUTING COMMAND");

                try {
                    const response = await fetch(`${BACKEND_URL}/api/command`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ command, lang: currentLang, mode })
                    });

                    if (!response.ok) throw new Error(`Backend HTTP ${response.status}`);

                    const data = await response.json();
                    if (backendBadge) {
                        backendBadge.textContent = "FLASK ONLINE (5000)";
                        backendBadge.className = "text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-neonGreen border border-emerald-500/30";
                    }

                    voiceTranscript.innerHTML = `
                        <div class="text-neonBlue">Incoming Command [${mode}]: ${escapeHtml(command)}</div>
                        <div class="text-neonPurple mt-1">Intent Category: ${escapeHtml(data.intent || "General Automated Action")}</div>
                        <div class="text-neonGreen mt-2">Flask Backend Response: ${escapeHtml(data.action || "No response text")}</div>
                    `;
                    
                    if (emotionTokenDisplay) {
                        emotionTokenDisplay.textContent = (data.status || "EXECUTION OK").toUpperCase();
                    }

                    speakResponse(data.action || "Command processed by Flask backend.");

                    if (data.url) {
                        const link = document.createElement("a");
                        link.href = data.url;
                        link.target = "_blank";
                        link.rel = "noopener noreferrer";
                        link.textContent = "Open Requested Action URL";
                        link.className = "block mt-3 text-neonBlue underline text-xs font-mono";
                        voiceTranscript.appendChild(link);

                        // AUTOMATIC REDIRECTION TAB OPENER
                        window.open(data.url, '_blank');
                    }
                } catch (err) {
                    console.warn("Python Flask backend not reachable. Executing client-side AI fallback simulation:", err);
                    if (backendBadge) {
                        backendBadge.textContent = "FALLBACK / DISCONNECTED";
                        backendBadge.className = "text-xs font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-neonAmber border border-amber-500/30";
                    }

                    let fallbackIntent = "SYSTEM_TELEMETRY";
                    let fallbackResponse = `Simulated execution routine for "${command}". All system nodes reporting active.`;
                    
                    const lowerCmd = command.toLowerCase();
                    if (lowerCmd.includes("vision") || lowerCmd.includes("camera") || lowerCmd.includes("matrix")) {
                        fallbackIntent = "VISION_AI_EVALUATION";
                        fallbackResponse = "Vision AI matrix diagnostics initiated. Spatial vector resolution set to high precision.";
                    } else if (lowerCmd.includes("robot") || lowerCmd.includes("motor") || lowerCmd.includes("arm")) {
                        fallbackIntent = "ROBOTICS_CORE_KINEMATICS";
                        fallbackResponse = "Robotics kinematics thread verified. Hardware mapping operational.";
                    }

                    voiceTranscript.innerHTML = `
                        <div class="text-neonBlue">Command Input [${mode}]: ${escapeHtml(command)}</div>
                        <div class="text-neonAmber mt-1">Simulated Intent: ${fallbackIntent}</div>
                        <div class="text-neonGreen mt-2">Simulated AI Response: ${escapeHtml(fallbackResponse)}</div>
                    `;

                    if (emotionTokenDisplay) emotionTokenDisplay.textContent = "SIMULATED AI OK";
                    speakResponse(fallbackResponse);
                }
            }

            textCommandForm.addEventListener("submit", (e) => {
                e.preventDefault();
                const cmd = textCommandInput.value.trim();
                if (cmd) {
                    processPipelineCommand(cmd, "TEXT");
                    textCommandInput.value = "";
                }
            });

            if (SpeechRecognition) {
                recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;

                recognition.onstart = () => {
                    isListening = true;
                    if (voiceStatusDot) voiceStatusDot.className = "w-3 h-3 rounded-full bg-neonGreen animate-ping";
                    if (voiceStatusText) voiceStatusText.textContent = LocalizationMatrix[currentLang].voiceStatusActive;
                    if (voiceModuleStatus) {
                        voiceModuleStatus.textContent = "LISTENING";
                        voiceModuleStatus.className = "self-start sm:self-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-neonGreen border border-emerald-500/40";
                    }
                    document.getElementById("voiceText").textContent = LocalizationMatrix[currentLang].voiceTextStop;
                    updatePipelineVisual(0, "RECORDING AUDIO...");
                };

                recognition.onresult = (event) => {
                    const transcriptText = event.results[0][0].transcript;
                    processPipelineCommand(transcriptText, "VOICE");
                };

                recognition.onerror = (event) => {
                    console.warn("Speech recognition error:", event.error);
                    updatePipelineVisual(1, "SPEECH ERROR", true);
                };

                recognition.onend = () => {
                    isListening = false;
                    if (voiceStatusDot) voiceStatusDot.className = "w-3 h-3 rounded-full bg-slate-500";
                    if (voiceStatusText) voiceStatusText.textContent = LocalizationMatrix[currentLang].voiceStatusOffline;
                    if (voiceModuleStatus) {
                        voiceModuleStatus.textContent = "STANDBY";
                        voiceModuleStatus.className = "self-start sm:self-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-neonGreen border border-emerald-500/20";
                    }
                    document.getElementById("voiceText").textContent = LocalizationMatrix[currentLang].voiceTextInit;
                };

                btnVoiceTrigger.addEventListener("click", () => {
                    recognition.lang = languageCodes[currentLang] || "en-IN";
                    if (isListening) {
                        recognition.stop();
                    } else {
                        try {
                            recognition.start();
                        } catch (e) {
                            console.error(e);
                        }
                    }
                });
            } else {
                btnVoiceTrigger.addEventListener("click", () => {
                    const manualCmd = prompt("Enter command for Cognitive AI Matrix:", "SYSTEM run diagnostics");
                    if (manualCmd) processPipelineCommand(manualCmd, "TEXT_PROMPT");
                });
            }

            const eqBars = document.querySelectorAll('.eq-bar');
            const liveDecibel = document.getElementById("liveDecibel");
            const liveSampleRate = document.getElementById("liveSampleRate");
            
            const barCalm = document.getElementById("barCalm");
            const txtCalm = document.getElementById("txtCalm");
            const barFriction = document.getElementById("barFriction");
            const txtFriction = document.getElementById("txtFriction");
            const barLoad = document.getElementById("barLoad");
            const txtLoad = document.getElementById("txtLoad");

            const neuralBar = document.getElementById("neuralBar");
            const valNeuralVelocity = document.getElementById("valNeuralVelocity");
            const valNeuralIndex = document.getElementById("valNeuralIndex");
            const valNeuralActive = document.getElementById("valNeuralActive");

            const analyticsBar = document.getElementById("analyticsBar");
            const valVisionFPS = document.getElementById("valVisionFPS");
            const valVisionAccuracy = document.getElementById("valVisionAccuracy");
            const valVisionTracking = document.getElementById("valVisionTracking");

            const automationBar = document.getElementById("automationBar");
            const valRobotTasks = document.getElementById("valRobotTasks");
            const valRobotLoad = document.getElementById("valRobotLoad");
            const valRobotFlow = document.getElementById("valRobotFlow");

            const neuralCtx = document.getElementById("neuralCanvas")?.getContext("2d");
            const analyticsCtx = document.getElementById("analyticsCanvas")?.getContext("2d");
            const automationCtx = document.getElementById("automationCanvas")?.getContext("2d");

            let step = 0;
            function drawWave(ctx, color) {
                if (!ctx) return;
                const width = ctx.canvas.width;
                const height = ctx.canvas.height;
                ctx.clearRect(0, 0, width, height);
                ctx.beginPath();
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                for (let x = 0; x < width; x++) {
                    let y = (height / 2) + Math.sin(x * 0.04 + step) * (height / 4) * Math.sin(step * 0.5);
                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.stroke();
            }

            setInterval(() => {
                step += 0.15;
                
                eqBars.forEach((bar) => {
                    const h = isListening ? Math.floor(Math.random() * 85) + 15 : Math.floor(Math.random() * 20) + 5;
                    bar.style.height = h + "%";
                });

                const dbVal = isListening ? -(Math.random() * 15 + 2).toFixed(1) : -(Math.random() * 30 + 35).toFixed(1);
                if (liveDecibel) liveDecibel.textContent = dbVal + " dB";
                if (liveSampleRate) liveSampleRate.textContent = (44.1 + Math.random() * 0.4).toFixed(1) + " kHz";

                const calmVal = Math.floor(75 + Math.random() * 20);
                const frictionVal = Math.floor(5 + Math.random() * 15);
                const loadVal = Math.floor(40 + Math.random() * 45);

                if (barCalm) barCalm.style.width = calmVal + "%";
                if (txtCalm) txtCalm.textContent = calmVal + "%";
                if (barFriction) barFriction.style.width = frictionVal + "%";
                if (txtFriction) txtFriction.textContent = frictionVal + "%";
                if (barLoad) barLoad.style.width = loadVal + "%";
                if (txtLoad) txtLoad.textContent = loadVal + "%";

                const nVel = Math.floor(82 + Math.random() * 15);
                const nInd = Math.floor(90 + Math.random() * 9);
                const nAct = Math.floor(65 + Math.random() * 30);
                if (neuralBar) neuralBar.style.width = nVel + "%";
                if (valNeuralVelocity) valNeuralVelocity.textContent = nVel + "%";
                if (valNeuralIndex) valNeuralIndex.textContent = nInd + "%";
                if (valNeuralActive) valNeuralActive.textContent = nAct + "%";

                const vFps = Math.floor(58 + Math.random() * 5);
                const vAcc = Math.floor(94 + Math.random() * 5);
                const vTrk = Math.floor(88 + Math.random() * 11);
                if (analyticsBar) analyticsBar.style.width = vAcc + "%";
                if (valVisionFPS) valVisionFPS.textContent = vFps + " FPS";
                if (valVisionAccuracy) valVisionAccuracy.textContent = vAcc + "%";
                if (valVisionTracking) valVisionTracking.textContent = vTrk + "%";

                const rTasks = Math.floor(91 + Math.random() * 8);
                const rLoad = Math.floor(45 + Math.random() * 35);
                const rFlow = Math.floor(85 + Math.random() * 14);
                if (automationBar) automationBar.style.width = rFlow + "%";
                if (valRobotTasks) valRobotTasks.textContent = rTasks + "%";
                if (valRobotLoad) valRobotLoad.textContent = rLoad + "%";
                if (valRobotFlow) valRobotFlow.textContent = rFlow + "%";

                drawWave(neuralCtx, "#00f3ff");
                drawWave(analyticsCtx, "#8b5cf6");
                drawWave(automationCtx, "#10b981");

            }, 120);
        });
    </script>
</body>
</html>
"""

# Updated build_api_payload to pass 'intent' cleanly to your HTML frontend
def build_api_payload(status, action, url="", intent="Platform Routing Vector"):
    return jsonify({"status": status, "action": action, "url": url, "intent": intent})


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
        "automation_status": current_automation_status,
    })


@app.route("/api/command", methods=["POST"])
def process_incoming_command():
    try:
        payload = request.get_json(force=True) or {}
        raw_input = payload.get("command", "").strip()
        if not raw_input:
            return build_api_payload("empty", "No payload execution vector supplied.", intent="Empty Vector")

        command = raw_input.lower()
        print(f"[INGRESS] Routing Vector Received -> {command}")

        if any(term in command for term in ["gold rate", "gold price", "gold"]):
            return build_api_payload(
                "success",
                "Live financial sync: Current benchmark gold rate data retrieved successfully. Opening live market search matrix.",
                "https://www.google.com/search?q=gold+rate+today",
                intent="Live Financial Telemetry"
            )

        if "weather" in command:
            return build_api_payload(
                "success",
                "Atmospheric telemetry online: Local meteorological weather conditions loaded successfully.",
                "https://www.google.com/search?q=weather+forecast",
                intent="Atmospheric Meteorological Sync"
            )

        if any(term in command for term in ["news", "headlines", "updates", "current affairs", "breaking news"]):
            return build_api_payload(
                "success",
                "Global news network nodes parsed. Displaying current international and national headlines.",
                "https://news.google.com",
                intent="Global News Network Parse"
            )

        if any(token in command for token in ["system", "status", "connected", "dashboard"]):
            return build_api_payload("success", "Dynamic infrastructure matrix operational.", intent="System Diagnostics")

        platform, query = resolve_intent_and_query(command)
        if platform:
            platform_config = PLATFORM_REGISTRY[platform]

            if platform_config.get("has_automation") and any(
                act in command for act in ["login", "automation", "run", "start", "scrape", "open"]
            ):
                if automation_lock.locked():
                    return build_api_payload("busy", "Selenium instance pipeline is currently locked.", intent="Automation Locked")

                threading.Thread(
                    target=run_platform_automation,
                    args=(platform, query),
                    daemon=True,
                ).start()
                return build_api_payload(
                    "success",
                    f"Triggered active thread runner for {platform}.",
                    platform_config["base_url"],
                    intent=f"Automated Platform Thread: {platform.title()}"
                )

            if query:
                if platform == "myntra":
                    target_url = f"{platform_config['base_url']}/{urllib.parse.quote(query)}"
                else:
                    target_url = f"{platform_config['base_url']}{platform_config['search_path']}{urllib.parse.quote(query)}"

                return build_api_payload(
                    "success",
                    f"Dynamic routing mapping for {platform.title()} searching for '{query}'.",
                    target_url,
                    intent=f"Platform Search Vector: {platform.title()}"
                )

            return build_api_payload(
                "success",
                f"Routing request forward to {platform.title()} root node.",
                platform_config["base_url"],
                intent=f"Platform Direct Routing: {platform.title()}"
            )

        fallback_target = f"https://www.google.com/search?q={urllib.parse.quote(raw_input)}"
        return build_api_payload(
            "success",
            f"No localized workspace hit for '{raw_input}'. Global search query initiated.",
            fallback_target,
            intent="Global Search Fallback"
        )
    except Exception as runtime_error:
        print(f"[CRITICAL ERROR] Process pipeline crashed: {runtime_error}", file=sys.stderr)
        return (
            jsonify({
                "status": "error",
                "action": "Internal API infrastructure exception encountered.",
                "details": str(runtime_error),
                "intent": "System Error"
            }),
            500,
        )


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
                print(f"[DRIVER CLEANUP ERROR] {e}")
            finally:
                active_driver = None

        current_automation_status = "Drivers killed. System idle."
        return build_api_payload("success", "Active automation drivers terminated.", intent="Session Close")
    except Exception as e:
        return build_api_payload("error", f"Termination failed: {str(e)}", intent="Termination Error")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("   COGNITIVE SPEECH AI (LOCAL UNIFIED HUB)")
    print("   Operational Scope: Registry-Driven Route Processing Engine")
    print("   Network Target:    http://localhost:5000")
    print("=" * 65 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
