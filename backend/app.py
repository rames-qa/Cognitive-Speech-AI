from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import urllib.parse
import logging
import sys
import re

# SYSTEM SETUP & CONFIGURATION
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# GLOBAL CONCURRENCY STATE
automation_lock = threading.Lock()
active_driver = None

# HELPER FUNCTIONS (Moved outside the dictionary block to fix syntax errors)
def build_google_maps_search(query):
    return (
        f"https://www.google.com/maps/search/"
        f"{urllib.parse.quote(query)}"
    )

def build_google_maps_direction(source, destination):
    return (
        f"https://www.google.com/maps/dir/"
        f"{urllib.parse.quote(source)}/"
        f"{urllib.parse.quote(destination)}"
    )

# COMPLETELY DYNAMIC REGISTRY CONFIGURATION
PLATFORM_REGISTRY = {
    "amazon": {
        "base_url": "https://www.amazon.in",
        "search_path": "/s?k=",
        "has_automation": True
    },
    "flipkart": {
        "base_url": "https://www.flipkart.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "myntra": {
        "base_url": "https://www.myntra.com",
        "search_path": "/",
        "aliases": ["fashion", "clothes", "shopping"],
        "has_automation": False
    },
    "gmail": {
        "base_url": "https://mail.google.com",
        "search_path": "/mail/u/0/#search/",
        "aliases": ["mail", "inbox"],
        "has_automation": False
    },
    "youtube": {
        "base_url": "https://www.youtube.com",
        "search_path": "/results?search_query=",
        "aliases": ["video", "song", "music"],
        "has_automation": False
    },
    "news": {
        "base_url": "https://news.google.com",
        "search_path": "/search?q=",
        "aliases": ["world news", "global news", "updates", "breaking news", "current affairs"],
        "has_automation": False
    },
    "reuters": {
        "base_url": "https://www.reuters.com",
        "search_path": "/search/ui/?q=",
        "aliases": ["international news", "business updates"],
        "has_automation": False
    },
    "bbc news": {
        "base_url": "https://www.bbc.com/news",
        "search_path": "/search?q=",
        "aliases": ["bbc"],
        "has_automation": False
    },
    "github": {
        "base_url": "https://github.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "linkedin": {
        "base_url": "https://www.linkedin.com",
        "search_path": "/search/results/all/?keywords=",
        "has_automation": False
    },
    "google": {
        "base_url": "https://www.google.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "bing": {
        "base_url": "https://www.bing.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "duckduckgo": {
        "base_url": "https://duckduckgo.com",
        "search_path": "/?q=",
        "has_automation": False
    },
    "yahoo": {
        "base_url": "https://search.yahoo.com",
        "search_path": "/search/p=",
        "has_automation": False
    },
    "stackoverflow": {
        "base_url": "https://stackoverflow.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "reddit": {
        "base_url": "https://www.reddit.com",
        "search_path": "/search/?q=",
        "has_automation": False
    },
    "wikipedia": {
        "base_url": "https://en.wikipedia.org",
        "search_path": "/wiki/Special:Search?search=",
        "has_automation": False
    },
    "twitter": {
        "base_url": "https://twitter.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "facebook": {
        "base_url": "https://www.facebook.com",
        "search_path": "/search/top?q=",
        "has_automation": False
    },
    "instagram": {
        "base_url": "https://www.instagram.com",
        "search_path": "/explore/tags/",
        "has_automation": False
    },
    "npm": {
        "base_url": "https://www.npmjs.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "pypi": {
        "base_url": "https://pypi.org",
        "search_path": "/search/?q=",
        "has_automation": False
    },
    "medium": {
        "base_url": "https://medium.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "quora": {
        "base_url": "https://www.quora.com",
        "search_path": "/search?q=",
        "has_automation": False
    },
    "bus": {
        "base_url": "https://www.busbud.com",
        "search_path": "/en/search/-/USD/",
        "aliases": ["book bus", "bus ticket", "greyhound", "coach"],
        "has_automation": False
    },
    "train": {
        "base_url": "https://www.amtrak.com",
        "search_path": "/home.html",
        "aliases": ["book train", "train ticket", "railway ticket", "amtrak", "eurostar"],
        "has_automation": False
    },
    "flights": {
        "base_url": "https://www.expedia.com",
        "search_path": "/Flights-Search?leg1=from::to:,departure::T&mode=search&passengers=adults:1",
        "aliases": ["air ticket", "book flight", "flight ticket", "airline ticket", "plane ticket"],
        "has_automation": False
    }
}

# DYNAMIC NLP PARSING ENGINE
def resolve_intent_and_query(command):
    command = command.lower().strip()
    matched_platform = None
    
    sorted_platforms = sorted(
        PLATFORM_REGISTRY.items(), 
        key=lambda item: max([len(term) for term in [item[0]] + item[1].get("aliases", [])]), 
        reverse=True
    )
    for target_key, config in sorted_platforms:
        search_terms = [target_key] + config.get("aliases", [])
        for term in search_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', command):
                matched_platform = target_key
                command = re.sub(r'\b' + re.escape(term) + r'\b', '', command).strip()
                break
        if matched_platform:
            break

    action_patterns = [
        r"\btell me about\b", r"\bdetails of\b", r"\bsearch for\b", 
        r"\bopen up\b", r"\broute to\b", r"\bshow me\b", r"\bgo to\b", 
        r"\bsearch\b", r"\blaunch\b", r"\bstart\b", r"\bplay\b", r"\bfind\b", r"\bopen\b",
        r"\bon\b", r"\bfor\b", r"\bat\b", r"\band\b"
    ]   
    clean_query = command
    for pattern in action_patterns:
        clean_query = re.sub(pattern, " ", clean_query) 
    extracted_query = " ".join(clean_query.split())
    return matched_platform, extracted_query

def build_api_payload(status, action, url=""):
    return jsonify({"status": status, "action": action, "url": url})

# ASYNC AUTOMATION PIPELINE RUNNER
def execute_amazon_pipeline():
    global active_driver
    if not automation_lock.acquire(blocking=False):
        print("[WORKER BLOCKED] Engine is busy processing an open test pipeline.")
        return     
    print("\n[SELENIUM] Initializing autonomous Codespace driver orchestration sequence...")
    try:
        options = webdriver.ChromeOptions()
        
        # --- CRITICAL CODESPACE/HEADLESS ENVIRONMENT ARGUMENTS ---
        options.add_argument("--headless=new") 
        options.add_argument("--disable-gpu")     
        options.add_argument("--window-size=1920,1080") 
        
        # Original Sandbox safety setups
        options.add_argument("--start-maximized")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("detach", True)       
        
        active_driver = webdriver.Chrome(options=options)
        active_driver.get(PLATFORM_REGISTRY["amazon"]["base_url"])      
        
        wait = WebDriverWait(active_driver, 12)
        signin_node = wait.until(EC.element_to_be_clickable((By.ID, "nav-link-accountList")))
        signin_node.click()
        print("[SELENIUM] Routine target reached inside Codespace: Login target node located safely.")
    except Exception as error:
        print(f"[SELENIUM ERROR] Codespace automation execution faulted: {error}", file=sys.stderr)
        if active_driver:
            try: active_driver.quit()
            except: pass
            active_driver = None
    finally:
        automation_lock.release()

# DYNAMIC ENDPOINT ROUTING MANAGEMENT
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
            if platform_config["has_automation"] and any(act in command for act in ["login", "automation", "run"]):
                if automation_lock.locked():
                    return build_api_payload("busy", "Selenium instance pipeline is currently locked.")              
                threading.Thread(target=execute_amazon_pipeline, daemon=True).start()
                return build_api_payload("success", f"Triggered active thread runner for {platform}.", platform_config["base_url"])          
            if query:
                if platform == "myntra":
                    target_url = f"{platform_config['base_url']}/{urllib.parse.quote(query)}"
                else:
                    target_url = f"{platform_config['base_url']}{platform_config['search_path']}{urllib.parse.quote(query)}"                 
                return build_api_payload("success", f"Dynamic mapping to {platform} query parameter: '{query}'", target_url)         
            return build_api_payload("success", f"Routing request forward to {platform} root interface.", platform_config["base_url"])           
        fallback_target = f"https://www.google.com/search?q={urllib.parse.quote(raw_input)}"
        return build_api_payload("success", f"No localized workspace hit. Fallback query to open web: {raw_input}", fallback_target)           
    except Exception as runtime_error:
        print(f"[CRITICAL ERROR] Process pipeline crashed: {runtime_error}", file=sys.stderr)
        return jsonify({
            "status": "error",
            "action": "Internal API infrastructure exception encountered.",
            "details": str(runtime_error)
        }), 500

@app.route("/api/close_session", methods=["POST"])
def terminate_orphaned_drivers():
    global active_driver
    try:
        if active_driver:
            active_driver.quit()
            active_driver = None
            return build_api_payload("success", "Active infrastructure nodes terminated cleanly.")
        return build_api_payload("empty", "No standalone processes found active.")
    except Exception as error:
        return build_api_payload("error", f"Node teardown exception: {str(error)}")

@app.route("/")
def health_check():
    return jsonify({"status": "online", "service": "Adaptive Codespace Pipeline"})

if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)    
    print("\n" + "=" * 65)
    print("   COGNITIVE SPEECH AI (CODESPACE EDITION)")
    print("   Operational Scope: Registry-Driven Route Processing Engine")
    print("   Network Target:    http://0.0.0.0:5000")
    print("=" * 65 + "\n")   
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
