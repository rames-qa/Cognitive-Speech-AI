from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import threading
import urllib.parse
import logging

# FLASK INITIALIZATION
app = Flask(__name__)

# Cleans up CORS scoping across all dynamic front-end pathways
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)

# GLOBAL SYSTEM STATE
automation_lock = threading.Lock()
active_driver = None

def sanitize_query(text, extra_tags=None):
    if extra_tags is None:
        extra_tags = []
    cleaned = text.lower()
    removal_tokens = [
        "search for",
        "search",
        "open",
        "show me",
        "find",
        "go to",
        "launch",
        "start",
        "play",
        "tell me about",
        "details of",
        "open up",
        "route to"
    ] + extra_tags

    for token in removal_tokens:
        cleaned = cleaned.replace(token.lower(), "")
    return cleaned.strip()

def generate_response(action, url=""):
    return jsonify({
        "status": "success",
        "action": action,
        "url": url
    })

# AMAZON AUTOMATION ENGINE
def run_amazon_automation():
    global active_driver

    if not automation_lock.acquire(blocking=False):
        print("[AUTOMATION] Existing session already running.")
        return
        
    print("\n[SELENIUM] Launching Amazon automation sequence...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("detach", True)
    
    try:
        service = Service(ChromeDriverManager().install())
        active_driver = webdriver.Chrome(
            service=service,
            options=options
        )
        active_driver.get("https://www.amazon.in")
        wait = WebDriverWait(active_driver, 15)
        signin_button = wait.until(
            EC.element_to_be_clickable(
                (By.ID, "nav-link-accountList")
            )
        )
        signin_button.click()
        print("[SELENIUM] Amazon login page opened successfully.")
    except Exception as e:
        print(f"[SELENIUM ERROR] Fault discovered during execution: {e}")
        if active_driver:
            try:
                active_driver.quit()
            except:
                pass
            active_driver = None
    finally:
        automation_lock.release()

# COMMAND ENGINE
@app.route("/api/command", methods=["POST"])
def handle_command():
    try:
        data = request.get_json(force=True) or {}
        print("\n=================================================")
        print("RAW REQUEST:", data)
        print("=================================================\n")
        
        raw_command = data.get("command", "").strip()
        if not raw_command:
            return jsonify({
                "status": "empty",
                "action": "No command received",
                "url": ""
            })
            
        command = raw_command.lower()
        print(f"[VOICE INPUT] -> {command}")
        
        # SYSTEM COMMANDS
        if any(x in command for x in ["system", "status", "connected", "dashboard"]):
            return generate_response("All cognitive systems operational.")
            
        # AMAZON
        elif "amazon" in command:
            if "login" in command or "automation" in command:
                if automation_lock.locked():
                    return jsonify({
                        "status": "busy",
                        "action": "Automation engine already active.",
                        "url": ""
                    })
                threading.Thread(
                    target=run_amazon_automation,
                    daemon=True
                ).start()
                return generate_response(
                    "Launching Amazon automation engine.",
                    "https://www.amazon.in"
                )
            query = sanitize_query(command, ["amazon"])
            if query:
                url = "https://www.amazon.in/s?k=" + urllib.parse.quote(query)
                return generate_response(f"Searching Amazon for {query}", url)
            return generate_response("Opening Amazon India.", "https://www.amazon.in")
            
        # FLIPKART
        elif "flipkart" in command:
            query = sanitize_query(command, ["flipkart"])
            if query:
                url = "https://www.flipkart.com/search?q=" + urllib.parse.quote(query)
                return generate_response(f"Searching Flipkart for {query}", url)
            return generate_response("Opening Flipkart.", "https://www.flipkart.com")
            
        # GMAIL
        elif any(x in command for x in ["gmail", "mail", "inbox"]):
            query = sanitize_query(command, ["gmail", "mail", "inbox"])
            if query:
                url = "https://mail.google.com/mail/u/0/#search/" + urllib.parse.quote(query)
                return generate_response(f"Searching Gmail for {query}", url)
            return generate_response("Opening Gmail workspace.", "https://mail.google.com")
            
        # YOUTUBE
        elif any(x in command for x in ["youtube", "video", "song", "music"]):
            query = sanitize_query(command, ["youtube", "video", "song", "music"])
            if query:
                url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
                return generate_response(f"Opening YouTube results for {query}", url)          
            return generate_response("Opening YouTube Home.", "https://www.youtube.com")
            
        # MAPS (Updated with stable fallback endpoints)
        elif any(x in command for x in ["map", "route", "direction", "location"]):
            query = sanitize_query(command, ["map", "route", "direction", "location"])
            if query:
                url = "https://www.google.com/maps/search/" + urllib.parse.quote(query)
                return generate_response(f"Opening maps for {query}", url)          
            return generate_response("Opening Google Maps.", "https://maps.google.com")
            
        # NEWS
        elif "news" in command:
            query = sanitize_query(command, ["news"])
            url = "https://news.google.com/search?q=" + urllib.parse.quote(query)
            return generate_response(f"Opening news feed for {query}", url)
            
        # OPEN WEBSITES
        elif "google" in command:
            return generate_response("Opening Google.", "https://www.google.com")
        elif "github" in command:
            return generate_response("Opening GitHub.", "https://github.com")
        elif "linkedin" in command:
            return generate_response("Opening LinkedIn.", "https://www.linkedin.com")
            
        # FALLBACK SEARCH
        else:
            fallback_url = "https://www.google.com/search?q=" + urllib.parse.quote(command)
            return generate_response(f"Searching web for {command}", fallback_url)
            
    except Exception as e:
        print(f"\n[BACKEND ERROR] {e}\n")
        return jsonify({
            "status": "error",
            "action": str(e),
            "url": ""
        }), 500

# HEALTH CHECK
@app.route("/")
def health_check():
    return jsonify({
        "status": "online",
        "message": "Cognitive AI backend operational"
    })

# SERVER BOOT
if __name__ == "__main__":
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    
    print("\n" + "=" * 60)
    print("   COGNITIVE SPEECH AI BACKEND SERVER ONLINE")
    print("   Voice + Selenium + Automation Ready")
    print("   Local Instance: http://127.0.0.1:5000")
    print("   Public Tunnel:  https://abcd1234.ngrok-free.app/api/command")
    print("=" * 60 + "\n")
    
    # Must run on port 5000 locally so ngrok can look inside and intercept requests
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
