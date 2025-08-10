# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# --- Install Google Chrome and ChromeDriver ---

# 1. Install necessary dependencies for Chrome
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    --no-install-recommends

# 2. Download and install Google Chrome (stable version)
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb

# 3. Download and install the correct ChromeDriver
# Using the new Chrome for Testing JSON endpoints for reliability
RUN CHROME_VERSION=$(google-chrome --version | cut -d " " -f3 | cut -d "." -f1-3) && \
    DRIVER_VERSION=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" | jq -r ".versions[] | select(.version | startswith(\"$CHROME_VERSION\")) | .downloads.chromedriver[0].url") && \
    wget -q $DRIVER_VERSION && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm chromedriver-linux64.zip

# --- Install Python Dependencies ---

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy Application and Run ---

# Copy the rest of the application code into the container
COPY . .

# Tell Render what command to run when the container starts
# The port is set by Render's PORT environment variable
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "1", "app:flask_app"]
```**(Note: This Dockerfile is more complex because installing Chrome is a multi-step process. You can just copy-paste it directly).**

#### Step 2: Update `app.py` for Docker

Now that we have a controlled environment, we must tell Selenium exactly where to find Chrome and ChromeDriver inside our container.

You need to import `Service` from Selenium and modify the `start_bot` function. Here is the **complete, final `app.py` script** with the necessary changes.

```python
# FUSED DEFINITIVE VERSION - DOCKERIZED FOR RELIABILITY
# VERSION 3.0: Adapted for a Docker environment with explicit paths.
# This is the most robust version for deployment on platforms like Render.

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
from selenium.webdriver.chrome.service import Service # <-- IMPORT THIS
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

# --- CONFIGURATION ---
TARGET_URL = "https://bloxd.io"
MAX_FAILURES = 5
MAIN_LOOP_POLLING_INTERVAL_SECONDS = 20.0

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

# --- BROWSER & FLASK SETUP ---
def setup_driver_options():
    """Configures Chrome options for the Docker environment."""
    chrome_options = Options()
    # These paths are fixed inside our Docker container
    chrome_options.binary_location = "/usr/bin/google-chrome"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1024,768")
    return chrome_options

flask_app = Flask('')
@flask_app.route('/')
def health_check():
    # ... (This function does not need to change)
    with STATE_LOCK:
        status, uptime, event_log, screenshot_base64 = BOT_STATE['status'], str(datetime.now() - BOT_STATE['start_time']).split('.')[0], list(BOT_STATE['event_log']), BOT_STATE['last_screenshot_base64']
    html = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta http-equiv="refresh" content="20"><title>Bot Status</title><style>body{{font-family:monospace;background-color:#1e1e1e;color:#d4d4d4;display:flex;}}.content{{flex:1;padding-right:20px;}}.screenshot{{flex:1;}}h1,h2{{color:#569cd6;}}b{{color:#9cdcfe;}}pre{{white-space:pre-wrap;word-wrap:break-word;}}img{{border:2px solid #569cd6;max-width:100%;}}</style></head><body><div class="content"><h1>Selenium Bot Status</h1><p><b>Status:</b> {status}</p><p><b>Target URL:</b> {TARGET_URL}</p><p><b>Uptime:</b> {uptime}</p><h2>Event Log</h2><pre>{'<br>'.join(event_log)}</pre></div><div class="screenshot"><h2>Browser View</h2>{"<img src='data:image/png;base64,{screenshot_base64}' alt='Browser Screenshot'>" if screenshot_base64 else "<p>No screenshot available yet. Waiting for bot to start...</p>"}</div></body></html>
    """
    return Response(html, mimetype='text/html')

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"Health check server listening on http://0.0.0.0:{port}")
    # The CMD in the Dockerfile handles running gunicorn now, so this function is only used for local testing if needed.
    # When deployed, the CMD line is used instead. We keep this function for conceptual clarity.
    # In a real deployment, flask_app.run() is not used; gunicorn runs the app.

# --- CORE BOT FUNCTIONS ---
# UPDATED FUNCTION FOR DOCKER
def start_bot():
    """Initializes the browser inside the Docker container."""
    global driver
    with STATE_LOCK:
        BOT_STATE["status"] = "Launching Browser..."
    log_event("Attempting to start new Selenium session inside Docker...")

    try:
        log_event("1/4: Configuring Chrome options...")
        chrome_options = setup_driver_options()
        
        # Define the service with the explicit path to chromedriver
        chromedriver_service = Service(executable_path="/usr/bin/chromedriver")
        
        log_event("2/4: Initializing webdriver.Chrome() with service...")
        driver = webdriver.Chrome(service=chromedriver_service, options=chrome_options)
        
        log_event("3/4: ✅ Webdriver initialized. Navigating to URL...")
        driver.get(TARGET_URL)
        log_event(f"4/4: ✅ Navigation initiated to {TARGET_URL}. Waiting for page title 'Bloxd' (timeout: 120s)...")
        WebDriverWait(driver, 120).until(EC.title_contains("Bloxd"))
        log_event("✅ bloxd.io page loaded successfully.")

    except Exception as e:
        log_event(f"CRITICAL FAILURE during startup: {e}")
        # Try to get a screenshot for debugging
        try:
            b64_screenshot = driver.get_screenshot_as_base64()
            with STATE_LOCK: BOT_STATE["last_screenshot_base64"] = b64_screenshot
            log_event("Saved a screenshot of the failure state.")
        except Exception as ss_error:
            log_event(f"Could not even take a screenshot. Error: {ss_error}")
        raise

# --- MAIN EXECUTION & LIFECYCLE MANAGEMENT ---
def main():
    # ... (This function does not need to change)
    global driver
    # In Docker, gunicorn starts Flask, so we don't need a separate thread for it here.
    # The run_flask() function is effectively replaced by the Docker CMD.
    # The main loop now just runs the bot logic.

    failure_count = 0
    restart_timestamps = deque(maxlen=5)

    while failure_count < MAX_FAILURES:
        now = time.time()
        if len(restart_timestamps) == 5 and (now - restart_timestamps[0] < 600):
            log_event("CRITICAL: Bot is thrashing. Pausing for 5 minutes.")
            with STATE_LOCK: BOT_STATE["status"] = "CRASH LOOP DETECTED - Paused for 5 minutes."
            time.sleep(300)
            restart_timestamps.clear()

        restart_timestamps.append(now)

        try:
            start_bot()
            log_event("Bot is running. Monitoring session.")
            with STATE_LOCK: BOT_STATE["status"] = "Running"
            failure_count = 0
            restart_timestamps.clear()
            while True:
                time.sleep(MAIN_LOOP_POLLING_INTERVAL_SECONDS)
                try:
                    screenshot = driver.get_screenshot_as_base64()
                    with STATE_LOCK: BOT_STATE["last_screenshot_base64"] = screenshot
                except WebDriverException as e:
                    log_event(f"Browser unresponsive during screenshot: {e}")
                    raise
        except Exception as e:
            failure_count += 1
            log_event(f"CRITICAL ERROR (Failure #{failure_count}): {e}")
            with STATE_LOCK: BOT_STATE["status"] = f"Crashed! Restarting... (Failure {failure_count}/{MAX_FAILURES})"
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass
                driver = None
            gc.collect()
            if failure_count < MAX_FAILURES:
                time.sleep(10)
            else:
                log_event(f"FATAL: Reached {MAX_FAILURES} failures. Bot is stopping.")
                with STATE_LOCK: BOT_STATE["status"] = f"STOPPED after {MAX_FAILURES} failures."
                break

# THIS IS A CRITICAL CHANGE FOR DOCKER DEPLOYMENT
if __name__ == "__main__":
    # When gunicorn runs this file, it provides the web server.
    # We need to start the bot logic in a separate thread so it doesn't
    # block the web server from responding to health checks.
    bot_thread = threading.Thread(target=main, daemon=True)
    bot_thread.start()
    
    # This part is now handled by the CMD in the Dockerfile.
    # We don't call run_flask() or app.run() here. Gunicorn does it.
    # The script will be loaded by gunicorn, the bot thread will start,
    # and gunicorn will serve the flask_app object.
