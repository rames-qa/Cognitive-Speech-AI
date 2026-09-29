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
CORS(app, resources={r"/api/*": {"origins": "*"}})
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
      r"\bon\b",  # Fixed \b regex pattern
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
        target_url += (
            f"{platform_config['search_path']}{urllib.parse.quote(query)}"
        )
      local_driver.get(target_url)
      time.sleep(4)

      headlines = local_driver.find_elements(By.TAG_NAME, "h4")
      top_stories = [h.text for h in headlines[:3] if h.text]
      if top_stories:
        current_automation_status = (
            f"News update: {', '.join(top_stories[:2])}"
        )
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


# --- BUILT-IN FRONTEND DASHBOARD ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognitive Speech AI</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 2rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 90%; max-width: 500px; text-align: center; }
        h2 { margin-bottom: 1.5rem; color: #38bdf8; }
        .btn { background: #0284c7; color: white; border: none; padding: 0.8rem 1.5rem; border-radius: 8px; font-size: 1rem; cursor: pointer; transition: 0.2s; width: 100%; margin-top: 10px; }
        .btn:hover { background: #0369a1; }
        .btn-speak { background: #10b981; margin-bottom: 15px; }
        .btn-speak:hover { background: #059669; }
        input[type="text"] { width: 100%; padding: 0.8rem; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: white; margin-bottom: 10px; }
        .status-box { margin-top: 20px; padding: 10px; background: #0f172a; border-radius: 6px; font-size: 0.9rem; color: #94a3b8; text-align: left; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Cognitive Speech AI</h2>
        
        <button id="mic-btn" class="btn btn-speak">🎤 Speak Command</button>
        
        <form id="cmd-form">
            <input type="text" id="cmd-input" placeholder="Or type e.g., 'Open Amazon' or 'Search news Python'">
            <button type="submit" class="btn">Execute Command</button>
        </form>

        <div class="status-box">
            <strong>Status:</strong> <span id="status-text">Ready</span><br>
            <strong>Action:</strong> <span id="action-text">None</span>
        </div>
    </div>

    <script>
        const statusText = document.getElementById('status-text');
        const actionText = document.getElementById('action-text');
        const cmdInput = document.getElementById('cmd-input');

        // FUNCTION TO SEND COMMAND TO FLASK BACKEND
        async function sendCommand(commandStr) {
            statusText.innerText = "Processing...";
            actionText.innerText = "Sending payload to /api/command";

            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: commandStr })
                });
                const data = await res.json();
                
                statusText.innerText = data.status.toUpperCase();
                actionText.innerText = data.action;

                // Open link automatically if returned
                if (data.url) {
                    window.open(data.url, '_blank');
                }
            } catch (err) {
                statusText.innerText = "Error";
                actionText.innerText = "Failed to connect to backend.";
                console.error(err);
            }
        }

        // HANDLE MANUAL FORM SUBMISSION
        document.getElementById('cmd-form').addEventListener('submit', (e) => {
            e.preventDefault();
            const val = cmdInput.value.trim();
            if (val) sendCommand(val);
        });

        // HANDLE SPEECH RECOGNITION (WEB SPEECH API)
        const micBtn = document.getElementById('mic-btn');
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();

            micBtn.addEventListener('click', () => {
                recognition.start();
                statusText.innerText = "Listening...";
            });

            recognition.onresult = (event) => {
                const speechResult = event.results[0][0].transcript;
                cmdInput.value = speechResult;
                sendCommand(speechResult);
            };

            recognition.onerror = () => {
                statusText.innerText = "Mic Error";
            };
        } else {
            micBtn.disabled = true;
            micBtn.innerText = "Speech API Not Supported";
        }
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
      return build_api_payload(
          "empty", "No payload execution vector supplied."
      )

    command = raw_input.lower()
    print(f"[INGRESS] Routing Vector Received -> {command}")

    if any(
        token in command
        for token in ["system", "status", "connected", "dashboard"]
    ):
      return build_api_payload(
          "success", "Dynamic infrastructure matrix operational."
      )

    platform, query = resolve_intent_and_query(command)
    if platform:
      platform_config = PLATFORM_REGISTRY[platform]

      if platform_config["has_automation"] and any(
          act in command
          for act in ["login", "automation", "run", "start", "scrape", "open"]
      ):
        if automation_lock.locked():
          return build_api_payload(
              "busy", "Selenium instance pipeline is currently locked."
          )

        threading.Thread(
            target=run_platform_automation,
            args=(platform, query),
            daemon=True,
        ).start()
        return build_api_payload(
            "success",
            f"Triggered active automation workflow on {platform.title()}.",
            platform_config["base_url"],
        )

      if query:
        if platform == "myntra":
          target_url = (
              f"{platform_config['base_url']}/{urllib.parse.quote(query)}"
          )
        else:
          target_url = f"{platform_config['base_url']}{platform_config['search_path']}{urllib.parse.quote(query)}"

        return build_api_payload(
            "success",
            (
                f"Dynamic routing mapping for {platform.title()} searching for"
                f" '{query}'."
            ),
            target_url,
        )

      return build_api_payload(
          "success",
          f"Routing request forward to {platform.title()} root node.",
          platform_config["base_url"],
      )

    fallback_target = (
        f"https://www.google.com/search?q={urllib.parse.quote(raw_input)}"
    )
    return build_api_payload(
        "success",
        "No localized workspace hit. Default fallback query initiated.",
        fallback_target,
    )
  except Exception as runtime_error:
    print(
        f"[CRITICAL ERROR] Process pipeline crashed: {runtime_error}",
        file=sys.stderr,
    )
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
  app.run(host="0.0.0.0", port=5000, debug=True)
