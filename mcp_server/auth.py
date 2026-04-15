"""Device auth flow for MCP setup.

Opens the user's browser, polls for completion, and saves the API key.
"""

import time
import webbrowser

from mcp_server.client import DatapointClient
from mcp_server.config import is_https_or_localhost, save_config


def run_device_auth(base_url: str | None = None) -> dict:
    """Run the full device auth flow.

    1. Call /auth/device/start to get codes
    2. Open browser to verification URL
    3. Poll until authorized or expired

    Returns {"status": "authenticated", "config_path": "..."} on success,
    or {"status": "failed", "error": "..."} on failure.
    """
    client = DatapointClient(api_key="none", base_url=base_url)

    # Start the flow
    try:
        start = client.device_auth_start()
    except Exception as e:
        return {"status": "failed", "error": f"Could not start device auth: {e}"}

    try:
        device_code = start["device_code"]
        user_code = start["user_code"]
        verification_url = start["verification_url"]
    except KeyError as e:
        return {"status": "failed", "error": f"Server response missing required field: {e}"}
    expires_in = min(start.get("expires_in", 900), 1800)
    poll_interval = min(max(start.get("poll_interval", 5), 2), 30)

    if not is_https_or_localhost(verification_url):
        return {"status": "failed", "error": "Refusing to open non-HTTPS verification URL."}

    try:
        browser_opened = webbrowser.open(verification_url)
    except Exception:
        browser_opened = False

    # Poll for completion
    deadline = time.time() + expires_in
    consecutive_failures = 0
    while time.time() < deadline:
        try:
            result = client.device_auth_poll(device_code)
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            if consecutive_failures >= 5:
                return {"status": "failed", "error": f"Polling failed after 5 consecutive errors: {e}"}
            time.sleep(poll_interval)
            continue

        if result["status"] == "authorized" and result.get("api_key"):
            config_path = save_config(
                api_key=result["api_key"],
                base_url=base_url,
            )
            return {
                "status": "authenticated",
                "config_path": config_path,
                "user_code": user_code,
                "verification_url": verification_url,
                "browser_opened": browser_opened,
            }

        if result["status"] == "expired":
            return {"status": "failed", "error": "Authorization code expired. Please try again."}

        time.sleep(poll_interval)

    return {"status": "failed", "error": "Authorization timed out. Please try again."}
