# FUSED DEFINITIVE VERSION - MEMORY & STABILITY ENHANCED WITH SCREENSHOT
# This script navigates to a URL and keeps the session alive, displaying
# a screenshot of the browser's view on its own status page.
# VERSION 2.0: Added screenshot functionality.

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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# --- CONFIGURATION ---
TARGET_URL = "https://bloxd.io"
MAX_FAILURES = 5
MAIN_LOOP_POLLING_INTERVAL_SECONDS = 15.0 # How often to take a screenshot and check status.

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

if not TARGET_URL:
    logging.critical("FATAL: TARGET_URL environment variable is not set!")
    exit(1)

# --- GLOBAL STATE ---
driver = None
# This dictionary will be shared between the bot and Flask threads.
BOT_STATE = {
    "status": "Initializing...",
    "start_time": datetime.now(),
    "event_log": deque(maxlen=20),
    "last_screenshot_base64": None # NEW: To store the latest screenshot
}
# A lock to prevent race conditions when accessing shared state.
STATE_LOCK = threading.Lock()

def log_event(message):
    """Adds a timestamped message to the event log."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    full_message = f"[{timestamp}] {message}"
    with STATE_LOCK:
        BOT_STATE["event_log"].appendleft(full_message)
    logging.info(f"EVENT: {message}")

# --- BROWSER & FLASK SETUP ---
def setup_driver():
    """Configures and launches the headless Chrome browser."""
    logging.info("Launching headless browser with MEMORY-SAVING options...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # Set a window size for consistent screenshot dimensions
    chrome_options.add_argument("--window-size=1024,768")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--mute-audio")
    # Reduced graphics settings can help performance
    chrome_options.add_argument("--blink-settings=imagesEnabled=true") # Keep images enabled for the screenshot
    chrome_options.add_argument("--single-process")
    return webdriver.Chrome(options=chrome_options)

flask_app = Flask('')
@flask_app.route('/')
def health_check():
    """Provides a web endpoint to check the bot's status and view the screen."""
    with STATE_LOCK:
        status = BOT_STATE['status']
        uptime = str(datetime.now() - BOT_STATE['start_time']).split('.')[0]
        event_log = list(BOT_STATE['event_log'])
        screenshot_base64 = BOT_STATE['last_screenshot_base64']

    # NEW: The HTML is updated to include an image tag for the screenshot.
    # The image will auto-refresh every 15 seconds.
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="15">
        <title>Bot Status</title>
        <style>
            body {{ font-family: monospace; background-color: #1e1e1e; color: #d4d4d4; display: flex; }}
            .content {{ flex: 1; padding-right: 20px; }}
            .screenshot {{ flex: 1; }}
            h1, h2 {{ color: #569cd6; }}
            b {{ color: #9cdcfe; }}
            pre {{ white-space: pre-wrap; word-wrap: break-word; }}
            img {{ border: 2px solid #569cd6; max-width: 100%; }}
        </style>
    </head>
    <body>
        <div class="content">
            <h1>Selenium Bot Status</h1>
            <p><b>Status:</b> {status}</p>
            <p><b>Target URL:</b> {TARGET_URL}</p>
            <p><b>Uptime:</b> {uptime}</p>
            <h2>Event Log</h2>
            <pre>{'<br>'.join(event_log)}</pre>
        </div>
        <div class="screenshot">
            <h2>Browser View</h2>
            {"<img src='data:image/png;base64,{screenshot_base64}' alt='Browser Screenshot'>" if screenshot_base64 else "<p>No screenshot available yet.</p>"}
        </div>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

def run_flask():
    """Starts the Flask web server."""
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"Health check server listening on http://0.0.0.0:{port}")
    flask_app.run(host='0.0.0.0', port=port)

# --- CORE BOT FUNCTIONS ---
def start_bot():
    """Initializes the browser and navigates to the target URL."""
    global driver
    with STATE_LOCK:
        BOT_STATE["status"] = "Launching Browser..."
    log_event("Starting new Selenium session...")
    driver = setup_driver()
    log_event(f"Navigating to {TARGET_URL}...")
    driver.get(TARGET_URL)

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.XPATH, "//div[text()='Worlds']"))
    )
    log_event("✅ bloxd.io page loaded successfully.")

# --- MAIN EXECUTION & LIFECYCLE MANAGEMENT ---
def main():
    """The main entry point and lifecycle manager for the bot."""
    global driver

    threading.Thread(target=run_flask, daemon=True).start()

    failure_count = 0
    restart_timestamps = deque(maxlen=5)

    while failure_count < MAX_FAILURES:
        now = time.time()
        if len(restart_timestamps) == 5 and (now - restart_timestamps[0] < 600):
            log_event("CRITICAL: Bot is thrashing. Pausing for 5 minutes.")
            with STATE_LOCK:
                BOT_STATE["status"] = "CRASH LOOP DETECTED - Paused for 5 minutes."
            time.sleep(300)
            restart_timestamps.clear()

        restart_timestamps.append(now)

        try:
            start_bot()
            log_event("Bot is running. Monitoring session and taking screenshots.")
            with STATE_LOCK:
                BOT_STATE["status"] = "Running"
            failure_count = 0
            restart_timestamps.clear()

            # Main "do nothing" loop with periodic screenshots
            while True:
                time.sleep(MAIN_LOOP_POLLING_INTERVAL_SECONDS)
                try:
                    # NEW: Take screenshot and update global state
                    screenshot = driver.get_screenshot_as_base64() [6]
                    with STATE_LOCK:
                        BOT_STATE["last_screenshot_base64"] = screenshot
                    log_event("Screenshot captured.")
                except WebDriverException as e:
                    # If screenshot fails, the browser might be dead.
                    log_event(f"Failed to take screenshot, browser may be unresponsive: {e}")
                    raise # Re-raise the exception to trigger the restart logic.

        except WebDriverException as e:
            failure_count += 1
            log_event(f"WebDriver Exception (Failure #{failure_count}): {e.msg.splitlines()[0]}")
            with STATE_LOCK:
                BOT_STATE["status"] = f"Browser Unresponsive! Restarting... (Failure {failure_count}/{MAX_FAILURES})"
        except Exception as e:
            failure_count += 1
            log_event(f"CRITICAL ERROR (Failure #{failure_count}): {e}")
            with STATE_LOCK:
                BOT_STATE["status"] = f"Crashed! Restarting... (Failure {failure_count}/{MAX_FAILURES})"
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass
                driver = None
            gc.collect()

            if failure_count < MAX_FAILURES:
                log_event(f"Waiting 10 seconds before restart...")
                time.sleep(10)
            else:
                log_event(f"FATAL: Reached {MAX_FAILURES} consecutive failures. Bot is stopping.")
                with STATE_LOCK:
                    BOT_STATE["status"] = f"STOPPED after {MAX_FAILURES} failures."
                break

if __name__ == "__main__":
    main()
