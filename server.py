import logging
import os
import re
import sys
import threading
import urllib.parse
from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
# SYSTEM SETUP & CONFIGURATION
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
automation_lock = threading.Lock()
active_driver = None
# ... [Keep your PLATFORM_REGISTRY, resolve_intent_and_query, and execution pipelines here] ...
if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 65)
    print("   COGNITIVE SPEECH AI (CLOUD/CODESPACE EDITION)")
    print(f"   Network Target:    http://0.0.0.0:{port}")
    print("=" * 65 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
