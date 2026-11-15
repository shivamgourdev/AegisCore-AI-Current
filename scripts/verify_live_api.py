import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\shiva\OneDrive\Desktop\AegisCore-AI")
EVIDENCE = ROOT / "evidence" / "part-01-live-api-verification.txt"
SERVER_LOG = ROOT / "evidence" / "part-01-uvicorn.log"
BASE_URL = "http://127.0.0.1:8765"

results = []
process = None
log_handle = None
failed = False

def record(message):
    message = str(message)
    print(message, flush=True)
    results.append(message)

def request_json(path):
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        status = response.status
        body = response.read().decode("utf-8")
    return status, json.loads(body)

try:
    record("AEGISCORE AI - LIVE API VERIFICATION")
    record("Started: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    record("Base URL: " + BASE_URL)

    # Fail safely if the chosen port is already occupied.
    try:
        urllib.request.urlopen(BASE_URL + "/health", timeout=1)
    except urllib.error.HTTPError:
        pass
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    else:
        raise RuntimeError(
            "Port 8765 already serves an HTTP response. "
            "Stop and identify that process before retrying."
        )

    log_handle = open(SERVER_LOG, "w", encoding="utf-8")

    command = [
        sys.executable, "-m", "uvicorn",
        "aegiscore.main:app",
        "--app-dir", str(ROOT / "backend" / "app"),
        "--host", "127.0.0.1",
        "--port", "8765",
        "--log-level", "info",
    ]

    record("")
    record("CHECK 1: Starting actual Uvicorn server")

    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    ready = False
    deadline = time.time() + 20

    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "Uvicorn exited before becoming ready. "
                "Inspect evidence/part-01-uvicorn.log."
            )

        try:
            status, payload = request_json("/health")
            if status == 200 and payload.get("status") == "ok":
                ready = True
                break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            time.sleep(0.4)

    if not ready:
        raise RuntimeError(
            "Uvicorn did not become healthy within 20 seconds."
        )

    record("PASS: Live server started and /health returned HTTP 200.")

    record("")
    record("CHECK 2: GET /")

    status, payload = request_json("/")
    assert status == 200, "Root endpoint did not return HTTP 200."
    assert payload.get("service") == "aegiscore-api", payload
    assert payload.get("docs") == "/docs", payload

    record("PASS: Root endpoint returned HTTP 200.")
    record("Response: " + json.dumps(payload, sort_keys=True))

    record("")
    record("CHECK 3: GET /health")

    status, payload = request_json("/health")
    assert status == 200, "Health endpoint did not return HTTP 200."
    assert payload.get("status") == "ok", payload
    assert payload.get("service") == "aegiscore-api", payload
    assert payload.get("version"), "Application version is missing."

    record("PASS: Health endpoint returned expected JSON.")
    record("Response: " + json.dumps(payload, sort_keys=True))

    record("")
    record("CHECK 4: GET /openapi.json")

    status, payload = request_json("/openapi.json")
    assert status == 200, "OpenAPI endpoint did not return HTTP 200."
    assert payload.get("info", {}).get("title") == "AegisCore AI API"
    assert "/" in payload.get("paths", {})
    assert "/health" in payload.get("paths", {})

    record("PASS: Live OpenAPI schema contains expected endpoints.")
    record("Documented paths: " + ", ".join(sorted(payload["paths"])))

except Exception as exc:
    failed = True
    record("")
    record("CHECK FAILURE: " + repr(exc))

finally:
    if process is not None:
        record("")
        record("CHECK 5: Stopping verification server")

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    failed = True
                    record("FAIL: Server process could not be stopped.")
        if process.poll() is not None:
            record("PASS: Verification server process has stopped.")

    if log_handle is not None:
        log_handle.close()

    if failed and SERVER_LOG.exists():
        record("")
        record("Uvicorn log (last 40 lines):")
        try:
            log_lines = SERVER_LOG.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            results.extend(log_lines[-40:])
            for line in log_lines[-40:]:
                print(line, flush=True)
        except OSError as log_error:
            record("Could not read server log: " + str(log_error))

    record("")
    record("FINAL RESULT: " + ("FAIL" if failed else "PASS"))
    record("Finished: " + time.strftime("%Y-%m-%d %H:%M:%S"))

    EVIDENCE.write_text("\n".join(results) + "\n", encoding="utf-8")

sys.exit(1 if failed else 0)