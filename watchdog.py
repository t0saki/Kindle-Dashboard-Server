import time
import urllib.request
import os
import signal
import sys

# Configuration
# We use localhost and the standard port 5000. 
# If PORT env var is set, we could use it, but typically internal checks can rely on the known startup port.
# Let's check env var just in case.
PORT = os.environ.get("PORT", "5000")
URL = f"http://127.0.0.1:{PORT}/render"
CHECK_INTERVAL = 600  # Check every 600 seconds
TIMEOUT = 180        # Timeout for the request (rendering is slow)
MAX_FAILURES = 3    # Restart after 3 consecutive failures

print(f"[Watchdog] Starting... Monitor: {URL}, Interval: {CHECK_INTERVAL}s, Max Failures: {MAX_FAILURES}")

failures = 0

def restart_container():
    print("[Watchdog] Triggering container restart (sending SIGTERM to PID 1)...")
    # In Docker, PID 1 is the entrypoint. Killing it stops the container.
    # The orchestration layer (Docker restart policy) should then restart it.
    os.kill(1, signal.SIGTERM)

# Give the app some time to start up before the first check
initial_delay = 30
print(f"[Watchdog] Waiting {initial_delay}s for application to initialize...")
time.sleep(initial_delay)

while True:
    try:
        # print(f"[Watchdog] Checking {URL}...")
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as response:
            status_code = response.getcode()
            if status_code == 200:
                # print(f"[Watchdog] Check OK")
                failures = 0
            else:
                print(f"[Watchdog] Check FAILED: Status {status_code}")
                failures += 1
    except Exception as e:
        print(f"[Watchdog] Check ERROR: {e}")
        failures += 1
    
    if failures >= MAX_FAILURES:
        print(f"[Watchdog] CRTICAL: {failures} consecutive failures. Restarting now.")
        restart_container()
        # Sleep to allow the signal to take effect
        time.sleep(10)
        break
    
    time.sleep(CHECK_INTERVAL)
