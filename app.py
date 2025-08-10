# FINAL CLEAN VERSION FOR BLOXD.IO
# This script is simple, correct, and matches the Dockerfile and requirements.

import os
import gc
import logging
import threading
import time
from datetime import datetime
from collections import deque
import base64

from flask import Flask, Response
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
TARGET_URL = "https://bloxd.io"
MAX_FAILURES = 5
MAIN_LOOP_POLLING_INTERVAL_SECONDS = 30.0 # Take screenshot every 30 seconds

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# --- GLOBAL STATE ---
driver = None
BOT_STATE = { "status": "Initializing...", "start_time": datetime.now(), "event_log": deque(maxlen=20), "last_screenshot_base64": None }
STATE_LOCK = threading.Lock()

def log_event(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    full_message = f"[{timestamp}] {message}"
    with STATE_LOCK:
        BOT_STATE["event_log"].appendleft(full_message)
    logging.info(f"EVENT: {message}")

# --- FLASK WEB SERVER ---
flask_app = Flask('')
@flask_app.route('/')
def health_check():
    with STATE_LOCK:
        status = BOT_STATE['status']
        uptime = str(datetime.now() - BOT_STATE['start_time']).split('.')[0]
        event_log = list(BOT_STATE['event_log'])
        screenshot_base64 = BOT_STATE['last_screenshot_base64']
    html = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta http-equiv="refresh" content="30"><title>Bot Status</title><style>body{{font-family:monospace;background-color:#1e1e1e;color:#d4d4d4;display:flex;padding:1em;}} .content{{flex:1;padding-right:20px;}} .screenshot{{flex:1;}} h1,h2{{color:#569cd6;}} b{{color:#9cdcfe;}} pre{{white-space:pre-wrap;word-wrap:break-word;}} img{{border:2px solid #569cd6;max-width:100%;}}</style></head><body><div class="content"><h1>Bot Status</h1><p><b>Status:</b> {status}</p><p><b>Target:</b> {TARGET_URL}</p><p><b>Uptime:</b> {uptime}</p><h2>Event Log</h2><pre>{'<br>'.join(event_log)}</pre></div><div class="screenshot"><h2>Browser View</h2>{"<img src='data:image/png;base64,{screenshot_base64}' alt='Browser Screenshot'>" if screenshot_base64 else "<p>No screenshot yet...</p>"}</div></body></html>
    """
    return Response(html, mimetype='text/html')

# --- CORE BOT LOGIC ---
def start_bot():
    """Initializes the browser inside the Docker container."""
    global driver
    with STATE_LOCK:
        BOT_STATE["status"] = "Starting Chrome..."
    log_event("Attempting to start Selenium session with Chromium...")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1024,768")
    
    log_event("Initializing webdriver.Chrome()...")
    driver = webdriver.Chrome(options=chrome_options)
    
    log_event("Navigating to URL...")
    driver.get(TARGET_URL)
    log_event(f"Waiting for page title 'Bloxd' (timeout: 120s)...")
    WebDriverWait(driver, 120).until(EC.title_contains("Bloxd"))
    log_event("✅ Page loaded successfully.")

def main_bot_loop():
    global driver
    failure_count = 0
    while failure_count < MAX_FAILURES:
        try:
            start_bot()
            with STATE_LOCK: BOT_STATE["status"] = "Running"
            failure_count = 0 
            
            while True:
                time.sleep(MAIN_LOOP_POLLING_INTERVAL_SECONDS)
                log_event("Capturing screenshot...")
                screenshot = driver.get_screenshot_as_base64()
                with STATE_LOCK: BOT_STATE["last_screenshot_base64"] = screenshot

        except Exception as e:
            failure_count += 1
            log_event(f"CRITICAL ERROR (Failure #{failure_count}): {e}")
            with STATE_LOCK: BOT_STATE["status"] = f"Crashed! Restarting... ({failure_count}/{MAX_FAILURES})"
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass
                driver = None
            gc.collect()
            if failure_count < MAX_FAILURES:
                log_event("Waiting 10s before restart...")
                time.sleep(10)
            else:
                log_event(f"STOPPED after {MAX_FAILURES} failures.")
                with STATE_LOCK: BOT_STATE["status"] = "STOPPED"
                break

if __name__ == "__main__":
    # Gunicorn runs this file, creating the flask_app instance.
    # We must start the bot's main logic in a background thread.
    log_event("Starting main bot loop in a background thread.")
    bot_thread = threading.Thread(target=main_bot_loop, daemon=True)
    bot_thread.start()
