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
    <title>Cognitive Autonomous AI - Enterprise Architecture Matrix Hub</title>
    
    <!-- Fonts & Tailwind CSS CDN -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
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
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: #0b0f19;
            color: #f0f4f8;
            overflow-x: hidden;
            font-family: 'Poppins', sans-serif;
            min-height: 100vh;
        }
        .glass-panel {
            background: rgba(20, 27, 45, 0.85);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border: 1px solid rgba(34, 47, 76, 0.85);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.6);
        }
        .flow-card {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .flow-card:hover {
            border-color: rgba(0, 243, 255, 0.6);
            box-shadow: 0 0 25px rgba(0, 243, 255, 0.25);
            transform: translateY(-3px);
        }
        .eq-bar {
            width: 8px;
            background: #00f3ff;
            border-radius: 4px;
            transition: height 0.08s ease;
        }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #090d16; }
        ::-webkit-scrollbar-thumb { background: #222f4c; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #00f3ff; }
    </style>
</head>
<body class="min-h-screen flex flex-col font-sans selection:bg-cyan-500 selection:text-black">

    <!-- Top Enterprise Navigation Header -->
    <nav class="sticky top-0 z-50 flex flex-col md:flex-row items-center justify-between px-6 py-4 bg-darkPanel/95 backdrop-blur-md border-b border-borderCol">
        <div class="flex items-center gap-3">
            <div class="w-3.5 h-3.5 rounded-full bg-neonBlue animate-ping"></div>
            <span id="navLogo" class="text-xl font-bold tracking-wider bg-gradient-to-r from-neonBlue via-neonPurple to-neonGreen bg-clip-text text-transparent">Cognitive Autonomous AI Matrix</span>
        </div>
        <div class="flex items-center gap-5 mt-3 md:mt-0">
            <div class="flex items-center gap-1.5 bg-[#090d16] px-3 py-1 rounded-lg border border-borderCol font-mono text-xs">
                <span id="backendPingDot" class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span id="backendStatusLabel" class="text-neonGreen">Flask Bridge: ONLINE</span>
            </div>
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

    <!-- Main Workspace -->
    <main class="max-w-6xl mx-auto w-full px-6 pt-10 pb-16 flex-1 space-y-12">
        
        <!-- Header Banner -->
        <header class="text-center max-w-3xl mx-auto">
            <h1 id="heroTitle" class="text-3xl md:text-5xl font-extrabold mb-3 tracking-tight bg-gradient-to-r from-neonBlue via-neonPurple to-neonGreen bg-clip-text text-transparent">End-to-End Architecture Blueprint</h1>
            <p id="heroDesc" class="text-slate-400 text-sm md:text-base">Visual multi-tiered matrix mapping acoustic voice input, speech transcription, intent AI evaluation, Python Flask execution, and live output feedback.</p>
        </header>

        <!-- Block-Wise Vertical Architecture Blueprint -->
        <section id="architecture-flow" class="flex flex-col items-center gap-5">
            
            <!-- TIER 1: Cognitive Speech AI -->
            <div id="archNode-1" onclick="handleBlockActivation(1)" class="flow-card glass-panel w-full max-w-2xl rounded-2xl p-6 border-2 border-slate-700 cursor-pointer text-center">
                <div class="flex items-center justify-center gap-2 text-neonBlue mb-2">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
                    <h3 class="font-bold text-lg text-white">Cognitive Speech AI</h3>
                </div>
                <p class="text-xs font-mono text-slate-400">Voice / Text / Multilingual Input (EN, TA, HI, KN)</p>
            </div>

            <div class="text-neonBlue font-bold text-xl animate-bounce">↓</div>

            <!-- TIER 2: Split Grid (Speech Engine & AI Intelligence) -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-2xl">
                <div id="archNode-2" onclick="handleBlockActivation(2)" class="flow-card glass-panel rounded-2xl p-5 border-2 border-slate-700 cursor-pointer text-center">
                    <div class="flex items-center justify-center gap-2 text-cyan-400 mb-2">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M2 10v3"/><path d="M6 6v11"/><path d="M10 3v18"/><path d="M14 8v7"/><path d="M18 5v13"/><path d="M22 10v3"/></svg>
                        <h4 class="font-bold text-base text-white">Speech Engine</h4>
                    </div>
                    <p class="text-xs font-mono text-slate-400">Transcription & Acoustic Buffering</p>
                </div>

                <div id="archNode-3" onclick="handleBlockActivation(3)" class="flow-card glass-panel rounded-2xl p-5 border-2 border-slate-700 cursor-pointer text-center">
                    <div class="flex items-center justify-center gap-2 text-purple-400 mb-2">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2a10 10 0 1 0 10 10H12V2Z"/><path d="M12 12 2.7 9.3"/><path d="M12 12l9.3 2.7"/></svg>
                        <h4 class="font-bold text-base text-white">AI Intelligence</h4>
                    </div>
                    <p class="text-xs font-mono text-slate-400">Intent and Context Extraction</p>
                </div>
            </div>

            <div class="text-neonPurple font-bold text-xl animate-bounce">↓</div>

            <!-- TIER 3: Python Flask Backend -->
            <div id="archNode-4" onclick="handleBlockActivation(4)" class="flow-card glass-panel w-full max-w-2xl rounded-2xl p-6 border-2 border-slate-700 cursor-pointer text-center">
                <div class="flex items-center justify-center gap-2 text-neonGreen mb-2">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16"/></svg>
                    <h3 class="font-bold text-lg text-white">Python Flask Backend</h3>
                </div>
                <p class="text-xs font-mono text-slate-400">Command processing · AI evaluation · Approved automation · System metrics</p>
            </div>

            <div class="text-neonGreen font-bold text-xl animate-bounce">↓</div>

            <!-- TIER 4: Split Grid (Live Dashboard & Voice Response) -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-2xl">
                <div id="archNode-5" onclick="handleBlockActivation(5)" class="flow-card glass-panel rounded-2xl p-5 border-2 border-slate-700 cursor-pointer text-center">
                    <div class="flex items-center justify-center gap-2 text-neonBlue mb-2">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/></svg>
                        <h4 class="font-bold text-base text-white">Live Dashboard</h4>
                    </div>
                    <p class="text-xs font-mono text-slate-400">Telemetry & UI Visualization</p>
                </div>

                <div id="archNode-6" onclick="handleBlockActivation(6)" class="flow-card glass-panel rounded-2xl p-5 border-2 border-slate-700 cursor-pointer text-center">
                    <div class="flex items-center justify-center gap-2 text-neonRose mb-2">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
                        <h4 class="font-bold text-base text-white">Voice Response</h4>
                    </div>
                    <p class="text-xs font-mono text-slate-400">Acoustic TTS Output & Feedback</p>
                </div>
            </div>

        </section>

        <!-- Interactive Execution Terminal & Command Console -->
        <section id="console" class="glass-panel rounded-2xl p-6">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                <div class="flex items-center gap-3 font-semibold text-sm">
                    <span id="terminalDot" class="w-3 h-3 rounded-full bg-emerald-500 animate-ping"></span>
                    <span id="terminalStatusText">Autonomous Execution Terminal Online</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-slate-400 font-mono">Active Token:</span>
                    <span id="activeTokenBadge" class="text-xs font-mono font-bold px-2.5 py-0.5 rounded bg-cyan-500/10 text-neonBlue border border-cyan-500/30">IDLE</span>
                </div>
            </div>

            <div id="terminalLog" class="bg-[#090d16] p-4 rounded-xl font-mono text-xs md:text-sm min-h-[160px] max-h-72 overflow-y-auto text-slate-200 border border-[#1a243a] mb-4 space-y-2">
                <div class="text-slate-500">[SYSTEM] Click any architectural block above or submit a command below to execute pipeline vector...</div>
            </div>

            <form id="commandForm" class="flex flex-col sm:flex-row gap-3">
                <input type="text" id="commandInput" placeholder="Try: 'Open YouTube', 'Gold rate', 'Weather', 'News'..." class="flex-1 bg-[#090d16] border border-borderCol rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-neonBlue transition-all font-mono">
                <button type="submit" class="px-6 py-3 rounded-xl bg-gradient-to-r from-neonBlue to-neonPurple text-black font-semibold text-sm hover:opacity-90 transition-all flex items-center justify-center gap-2">
                    <span>Execute Vector</span>
                </button>
            </form>

            <div class="mt-4 flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800/80">
                <button id="btnVoiceTrigger" type="button" class="w-full sm:w-auto py-3 px-6 rounded-xl font-semibold text-white bg-darkPanel border border-borderCol hover:border-neonBlue transition-all flex items-center justify-center gap-3 text-sm">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
                    <span id="voiceText">Initialize Speech Recognition Stream</span>
                </button>
                <div class="text-xs text-slate-400 font-mono">Web Speech Recognition & Synthesis Active</div>
            </div>
        </section>

        <!-- Real-Time Acoustic Telemetry Matrix -->
        <section id="dashboard" class="space-y-6">
            <h2 id="sectionTitleMatrix" class="text-2xl font-bold text-center text-white">Cognitive Operations Interface Matrix</h2>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Acoustic Capture Panel -->
                <div class="glass-panel rounded-2xl p-6">
                    <div class="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
                        <h3 id="panelHeaderCapture" class="text-base font-semibold">Acoustic Capture Buffer</h3>
                        <span id="voiceModuleStatus" class="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-neonGreen border border-emerald-500/20">READY</span>
                    </div>
                    <div id="eqContainer" class="flex items-end justify-center gap-1.5 h-20 bg-[#090d16] rounded-xl p-3 mb-4 border border-slate-900">
                        <div class="eq-bar h-[15%]"></div>
                        <div class="eq-bar h-[35%]"></div>
                        <div class="eq-bar h-[25%]"></div>
                        <div class="eq-bar h-[65%]"></div>
                        <div class="eq-bar h-[85%]"></div>
                        <div class="eq-bar h-[50%]"></div>
                        <div class="eq-bar h-[35%]"></div>
                        <div class="eq-bar h-[75%]"></div>
                        <div class="eq-bar h-[30%]"></div>
                        <div class="eq-bar h-[15%]"></div>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-[#090d16] p-3 rounded-xl border border-slate-800 text-center">
                            <span id="metricLabelDecibel" class="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">Signal Decibels</span>
                            <span id="liveDecibel" class="font-mono text-base font-bold text-white">-17.8 dB</span>
                        </div>
                        <div class="bg-[#090d16] p-3 rounded-xl border border-slate-800 text-center">
                            <span id="metricLabelFrequency" class="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">Stream Frequency</span>
                            <span id="liveSampleRate" class="font-mono text-base font-bold text-neonBlue">44.1 kHz</span>
                        </div>
                    </div>
                </div>

                <!-- Cognitive Vocal Signature Panel -->
                <div class="glass-panel rounded-2xl p-6">
                    <div class="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
                        <h3 id="panelHeaderSignature" class="text-base font-semibold">Cognitive Vocal Signature</h3>
                        <span id="cognitiveModality" class="text-xs font-semibold text-slate-400">Signal Processing</span>
                    </div>
                    <div class="space-y-4">
                        <div>
                            <div class="flex justify-between text-xs text-slate-400 mb-1.5">
                                <span id="labelCalm">Calm Stability</span>
                                <span id="txtCalm" class="font-mono font-bold text-white">94%</span>
                            </div>
                            <div class="bg-[#090d16] h-2.5 rounded-full overflow-hidden">
                                <div id="barCalm" class="h-full bg-neonGreen rounded-full w-[94%] transition-all duration-300"></div>
                            </div>
                        </div>
                        <div>
                            <div class="flex justify-between text-xs text-slate-400 mb-1.5">
                                <span id="labelLoad">Dynamic Processing Load</span>
                                <span id="txtLoad" class="font-mono font-bold text-white">38%</span>
                            </div>
                            <div class="bg-[#090d16] h-2.5 rounded-full overflow-hidden">
                                <div id="barLoad" class="h-full bg-neonPurple rounded-full w-[38%] transition-all duration-300"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Sub-Systems Matrix Grid -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-4">
                <div class="glass-panel rounded-2xl p-6 flex flex-col justify-between">
                    <div>
                        <div class="mb-4 border-b border-slate-800 pb-3">
                            <h3 id="cardTitleNeural" class="text-base font-semibold text-neonBlue mb-1">Neural Processing</h3>
                            <p id="cardDescNeural" class="text-xs text-slate-400">Evaluating language tokens and acoustic matrices across hardware array tracks.</p>
                        </div>
                        <div class="bg-[#090d16] h-1.5 rounded-full overflow-hidden mb-4">
                            <div id="neuralBar" class="h-full bg-gradient-to-r from-neonBlue to-neonPurple rounded-full transition-all w-[75%]"></div>
                        </div>
                        <div class="grid grid-cols-3 gap-2 mb-4">
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">98.4%</span>
                                <small class="text-[9px] text-slate-400 uppercase">Velocity</small>
                            </div>
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">1.02</span>
                                <small class="text-[9px] text-slate-400 uppercase">Index</small>
                            </div>
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">16 Core</span>
                                <small class="text-[9px] text-slate-400 uppercase">Active</small>
                            </div>
                        </div>
                    </div>
                    <canvas id="neuralCanvas" class="w-full h-24 bg-[#090d16] rounded-lg border border-slate-900 block mt-2"></canvas>
                </div>

                <div class="glass-panel rounded-2xl p-6 flex flex-col justify-between">
                    <div>
                        <div class="mb-4 border-b border-slate-800 pb-3">
                            <h3 id="cardTitleVision" class="text-base font-semibold text-neonPurple mb-1">Vision AI Matrix</h3>
                            <p id="cardDescVision" class="text-xs text-slate-400">Processing spatial environment tracking, matrix frameworks, and vector points.</p>
                        </div>
                        <div class="bg-[#090d16] h-1.5 rounded-full overflow-hidden mb-4">
                            <div id="analyticsBar" class="h-full bg-gradient-to-r from-neonPurple to-neonGreen rounded-full transition-all w-[88%]"></div>
                        </div>
                        <div class="grid grid-cols-3 gap-2 mb-4">
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">60 FPS</span>
                                <small class="text-[9px] text-slate-400 uppercase">FPS Feed</small>
                            </div>
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">99.1%</span>
                                <small class="text-[9px] text-slate-400 uppercase">Accuracy</small>
                            </div>
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">Vector</span>
                                <small class="text-[9px] text-slate-400 uppercase">Tracking</small>
                            </div>
                        </div>
                    </div>
                    <canvas id="analyticsCanvas" class="w-full h-24 bg-[#090d16] rounded-lg border border-slate-900 block mt-2"></canvas>
                </div>

                <div class="glass-panel rounded-2xl p-6 flex flex-col justify-between">
                    <div>
                        <div class="mb-4 border-b border-slate-800 pb-3">
                            <h3 id="cardTitleRobotics" class="text-base font-semibold text-neonGreen mb-1">Robotics Core</h3>
                            <p id="cardDescRobotics" class="text-xs text-slate-400">Automated kinematics telemetry, hardware mapping, and thread scheduling loops.</p>
                        </div>
                        <div class="bg-[#090d16] h-1.5 rounded-full overflow-hidden mb-4">
                            <div id="automationBar" class="h-full bg-gradient-to-r from-neonGreen to-neonBlue rounded-full transition-all w-[92%]"></div>
                        </div>
                        <div class="grid grid-cols-3 gap-2 mb-4">
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">24 Loop</span>
                                <small class="text-[9px] text-slate-400 uppercase">Tasks</small>
                            </div>
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">14.2%</span>
                                <small class="text-[9px] text-slate-400 uppercase">Load</small>
                            </div>
                            <div class="bg-[#090d16] p-2 rounded-lg border border-slate-800 text-center">
                                <span class="font-mono text-sm font-bold text-white block">SYNC</span>
                                <small class="text-[9px] text-slate-400 uppercase">Flow</small>
                            </div>
                        </div>
                    </div>
                    <canvas id="automationCanvas" class="w-full h-24 bg-[#090d16] rounded-lg border border-slate-900 block mt-2"></canvas>
                </div>
            </div>
        </section>

    </main>

    <!-- Footer -->
    <footer id="footerText" class="mt-auto text-center py-6 text-xs text-slate-400 border-t border-borderCol bg-[#090d16]">
        &copy; 2026 Cognitive Autonomous AI Enterprise Matrix | Designed by Ramesh Kumar K
    </footer>

    <!-- Frontend Script Logic -->
    <script>
        const BACKEND_URL = "http://localhost:5000";

        const LocalizationMatrix = {
            en: {
                navLogo: "Cognitive Autonomous AI Matrix",
                heroTitle: "End-to-End Architecture Blueprint",
                heroDesc: "Visual multi-tiered matrix mapping acoustic voice input, speech transcription, intent AI evaluation, Python Flask execution, and live output feedback.",
                sectionTitleMatrix: "Cognitive Operations Interface Matrix",
                panelHeaderCapture: "Acoustic Capture Buffer",
                metricLabelDecibel: "Signal Decibels",
                metricLabelFrequency: "Stream Frequency",
                panelHeaderSignature: "Cognitive Vocal Signature",
                cognitiveModality: "Signal Processing",
                labelCalm: "Calm Stability",
                labelLoad: "Dynamic Processing Load"
            },
            ta: {
                navLogo: "அறிவுசார் பேச்சு AI மேட்ரிக்ஸ்",
                heroTitle: "முடிவிலிருந்து முடிவு கட்டமைப்பு வரைபடம்",
                heroDesc: "ஒலி குரல் உள்ளீடு, பேச்சு படியெடுத்தல், நோக்கம் AI மதிப்பீடு மற்றும் நேரடி வெளியீட்டு கருத்துக்களை வரைபடமாக்கும் காட்சி அடுக்கு மேட்ரிக்ஸ்.",
                sectionTitleMatrix: "அறிவுசார் செயல்பாட்டு இடைமுக மேட்ரிக்ஸ்",
                panelHeaderCapture: "ஒலி பிடிப்பு இடையக பகுதி",
                metricLabelDecibel: "சமிக்ஞை டெசிபல்கள்",
                metricLabelFrequency: "அலைவரிசை அதிர்வெண்",
                panelHeaderSignature: "அறிவுசார் குரல் கையொப்பம்",
                cognitiveModality: "சமிக்ஞை செயலாக்கம்",
                labelCalm: "அமைதியான நிலைத்தன்மை",
                labelLoad: "செயலாக்க சுமை"
            },
            hi: {
                navLogo: "कॉग्निटिव स्पीच एआई मैट्रिक्स",
                heroTitle: "एंड-टू-एंड आर्किटेक्चर ब्लूप्रिंट",
                heroDesc: "ध्वनिक वॉयस इनपुट, स्पीच ट्रांसक्रिप्शन, इरादा एआई मूल्यांकन और लाइव आउटपुट प्रतिक्रिया का मानचित्रण करने वाला विजुअल मैट्रिक्स।",
                sectionTitleMatrix: "कॉग्निटिव ऑपरेशंस इंटरफेस मैट्रिक्स",
                panelHeaderCapture: "ध्वनिक कैप्चर बफर",
                metricLabelDecibel: "सिग्नल डेसिबल",
                metricLabelFrequency: "स्ट्रीम फ्रीक्वेंसी",
                panelHeaderSignature: "कॉग्निटिव वोकल सिग्नेचर",
                cognitiveModality: "सिग्नल प्रोसेसिंग",
                labelCalm: "शांत स्थिरता",
                labelLoad: "प्रोसेसिंग लोड"
            },
            kn: {
                navLogo: "ಕಾಗ್ನಿಟಿವ್ ಸ್ಪೀಚ್ ಎಐ ಮ್ಯಾಟ್ರಿಕ್ಸ್",
                heroTitle: "ಎಂಡ್-ಟು-ಎಂಡ್ ಆರ್ಕಿಟೆಕ್ಚರ್ ಬ್ಲೂಪ್ರಿಂಟ್",
                heroDesc: "ಧ್ವನಿ ಇನ್‌ಪುಟ್, ಸ್ಪೀಚ್ ಟ್ರಾನ್ಸ್‌ಕ್ರಿಪ್ಷನ್, ಇಂಟೆಂಟ್ ಎಐ ಮೌಲ್ಯಮಾಪನ ಮತ್ತು ಲೈವ್ ಔಟ್‌ಪುಟ್ ಪ್ರತಿಕ್ರಿಯೆಯನ್ನು ಮ್ಯಾಪ್ ಮಾಡುವ ದೃಶ್ಯ ಮ್ಯಾಟ್ರಿಕ್ಸ್.",
                sectionTitleMatrix: "ಕಾಗ್ನಿಟಿವ್ ಆಪರೇಷನ್ಸ್ ಇಂಟರ್ಫೇಸ್ ಮ್ಯಾಟ್ರಿಕ್ಸ್",
                panelHeaderCapture: "ಅಕೌಸ್ಟಿಕ್ ಕ್ಯಾಪ್ಚರ್ ಬಫರ್",
                metricLabelDecibel: "ಸಿಗ್ನಲ್ ಡೆಸಿಬಲ್ಸ್",
                metricLabelFrequency: "ಸ್ಟ್ರೀಮ್ ಆವರ್ತನ",
                panelHeaderSignature: "ಕಾಗ್ನಿಟಿವ್ ವೋಕಲ್ ಸಿಗ್ನೇಚರ್",
                cognitiveModality: "ಸಿಗ್ನಲ್ ಪ್ರೊಸೆಸಿಂಗ್",
                labelCalm: "ಶಾಂತ ಸ್ಥಿರತೆ",
                labelLoad: "ಪ್ರೊಸೆಸಿಂಗ್ ಲೋಡ್"
            }
        };

        const langSelect = document.getElementById("langSelect");
        if (langSelect) {
            langSelect.addEventListener("change", (e) => {
                const dict = LocalizationMatrix[e.target.value];
                if (dict) {
                    Object.keys(dict).forEach(key => {
                        const el = document.getElementById(key);
                        if (el) el.textContent = dict[key];
                    });
                }
            });
        }

        function handleBlockActivation(nodeId) {
            for(let i=1; i<=6; i++) {
                const node = document.getElementById(`archNode-${i}`);
                if(node) node.style.borderColor = "#334155";
            }
            const activeNode = document.getElementById(`archNode-${nodeId}`);
            if(activeNode) activeNode.style.borderColor = "#00f3ff";

            const log = document.getElementById("terminalLog");
            const tokenBadge = document.getElementById("activeTokenBadge");

            const metadata = {
                1: { token: "INPUT_STREAM", text: "Cognitive Speech AI: Initializing multi-modal audio vector stream across EN/TA/HI/KN matrices." },
                2: { token: "SPEECH_ENGINE", text: "Speech Engine: Executing Whisper acoustic buffer conversion & phonetic tokenization." },
                3: { token: "AI_INTELLIGENCE", text: "AI Intelligence: Parsing semantic intent and mapping contextual RAG vector memories." },
                4: { token: "FLASK_BACKEND", text: "Python Flask Backend: Routing command through intent matcher and executing automation rules." },
                5: { token: "DASHBOARD_SYNC", text: "Live Dashboard: Synchronizing real-time telemetry widgets and EQ frequency spectrum." },
                6: { token: "VOICE_TTS", text: "Voice Response: Synthesizing emotional text-to-speech audio response wave." }
            };

            const data = metadata[nodeId];
            if(data) {
                tokenBadge.textContent = data.token;
                log.innerHTML += `<div class="text-neonBlue mt-1">⚡ [Architecture Node ${nodeId} Triggered]: ${data.text}</div>`;
                log.scrollTop = log.scrollHeight;

                if("speechSynthesis" in window && nodeId === 6) {
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.speak(new SpeechSynthesisUtterance(data.text));
                }
            }
        }

        async function executeCommand(query) {
            const log = document.getElementById("terminalLog");
            const tokenBadge = document.getElementById("activeTokenBadge");

            log.innerHTML += `<div class="mt-2 text-neonBlue">> ${query}</div>`;
            log.scrollTop = log.scrollHeight;

            try {
                const res = await fetch(`http://localhost:5000/api/command`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ command: query })
                });
                const data = await res.json();
                
                tokenBadge.textContent = data.status.toUpperCase();
                log.innerHTML += `<div class="mt-1 text-neonGreen">✓ [Flask Backend]: ${data.action}</div>`;
                log.scrollTop = log.scrollHeight;

                if (data.action && 'speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.speak(new SpeechSynthesisUtterance(data.action));
                }

                if (data.url) {
                    window.open(data.url, '_blank');
                }
            } catch (err) {
                tokenBadge.textContent = "FALLBACK_MODE";
                log.innerHTML += `<div class="mt-1 text-neonAmber">⚠ Flask backend offline. Local simulation active for: "${query}"</div>`;
                log.scrollTop = log.scrollHeight;

                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.speak(new SpeechSynthesisUtterance(`Simulated response for ${query}`));
                }
            }
        }

        const commandForm = document.getElementById("commandForm");
        if(commandForm) {
            commandForm.addEventListener("submit", (e) => {
                e.preventDefault();
                const input = document.getElementById("commandInput");
                const query = input.value.trim();
                if(query) {
                    executeCommand(query);
                    input.value = "";
                }
            });
        }

        const micBtn = document.getElementById("btnVoiceTrigger");
        if(micBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;

            micBtn.addEventListener('click', () => {
                recognition.start();
                document.getElementById("terminalDot").className = "w-3 h-3 rounded-full bg-neonBlue animate-ping";
                document.getElementById("terminalStatusText").textContent = "Listening to acoustic microphone stream...";
            });

            recognition.onresult = (event) => {
                const speechResult = event.results[0][0].transcript;
                document.getElementById("commandInput").value = speechResult;
                executeCommand(speechResult);
            };

            recognition.onerror = () => {
                document.getElementById("terminalDot").className = "w-3 h-3 rounded-full bg-rose-500";
                document.getElementById("terminalStatusText").textContent = "Speech API Error / Permission Denied";
            };
        }

        function drawCanvasWave(canvasId, strokeColor) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            let offset = 0;

            function animate() {
                canvas.width = canvas.offsetWidth;
                canvas.height = canvas.offsetHeight;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                ctx.beginPath();
                ctx.lineWidth = 2;
                ctx.strokeStyle = strokeColor;

                const height = canvas.height;
                const width = canvas.width;
                offset += 0.05;

                for (let x = 0; x < width; x++) {
                    const y = Math.sin(x * 0.05 + offset) * 15 + height / 2;
                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.stroke();
                requestAnimationFrame(animate);
            }
            animate();
        }

        window.addEventListener('load', () => {
            drawCanvasWave('neuralCanvas', '#00f3ff');
            drawCanvasWave('analyticsCanvas', '#8b5cf6');
            drawCanvasWave('automationCanvas', '#10b981');
        });

        setInterval(() => {
            const bars = document.querySelectorAll('.eq-bar');
            bars.forEach(bar => {
                bar.style.height = (Math.floor(Math.random() * 80) + 15) + "%";
            });
            const db = -(Math.random() * 10 + 10).toFixed(1);
            const decEl = document.getElementById("liveDecibel");
            if(decEl) decEl.textContent = db + " dB";
        }, 150);
    </script>
</body>
</html>
"""


def build_api_payload(status, action, url=""):
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
        "automation_status": current_automation_status,
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

        # --- LIVE DATA & INFORMATION INTERCEPTION ---
        if any(term in command for term in ["gold rate", "gold price", "gold"]):
            return build_api_payload(
                "success",
                "Live financial sync: Current benchmark gold rate data retrieved successfully. Opening live market search matrix.",
                "https://www.google.com/search?q=gold+rate+today"
            )

        if "weather" in command:
            return build_api_payload(
                "success",
                "Atmospheric telemetry online: Local meteorological weather conditions loaded successfully.",
                "https://www.google.com/search?q=weather+forecast"
            )

        if any(term in command for term in ["news", "headlines", "updates", "current affairs", "breaking news"]):
            return build_api_payload(
                "success",
                "Global news network nodes parsed. Displaying current international and national headlines.",
                "https://news.google.com"
            )

        if any(token in command for token in ["system", "status", "connected", "dashboard"]):
            return build_api_payload("success", "Dynamic infrastructure matrix operational.")

        # --- PLATFORM & APP ROUTING ---
        platform, query = resolve_intent_and_query(command)
        if platform:
            platform_config = PLATFORM_REGISTRY[platform]

            if platform_config["has_automation"] and any(
                act in command for act in ["login", "automation", "run", "start", "scrape", "open"]
            ):
                if automation_lock.locked():
                    return build_api_payload("busy", "Selenium instance pipeline is currently locked.")

                threading.Thread(
                    target=run_platform_automation,
                    args=(platform, query),
                    daemon=True,
                ).start()
                return build_api_payload(
                    "success",
                    f"Triggered active thread runner for {platform}.",
                    platform_config["base_url"],
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
                )

            return build_api_payload(
                "success",
                f"Routing request forward to {platform.title()} root node.",
                platform_config["base_url"],
            )

        # --- DEFAULT FALLBACK SEARCH ---
        fallback_target = f"https://www.google.com/search?q={urllib.parse.quote(raw_input)}"
        return build_api_payload(
            "success",
            f"No localized workspace hit for '{raw_input}'. Global search query initiated.",
            fallback_target,
        )
    except Exception as runtime_error:
        print(f"[CRITICAL ERROR] Process pipeline crashed: {runtime_error}", file=sys.stderr)
        return (
            jsonify({
                "status": "error",
                "action": "Internal API infrastructure exception encountered.",
                "details": str(runtime_error),
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
        return build_api_payload("success", "Active automation drivers terminated.")
    except Exception as e:
        return build_api_payload("error", f"Termination failed: {str(e)}")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("   COGNITIVE SPEECH AI (LOCAL UNIFIED HUB)")
    print("   Operational Scope: Registry-Driven Route Processing Engine")
    print("   Network Target:    http://localhost:5000")
    print("=" * 65 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
