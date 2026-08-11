import json
import os
import platform
import urllib.request

DEFAULT_API = "https://api.gcontext.ai"


def ping_install(install_id: str, version: str) -> None:
    if os.environ.get("GCONTEXT_TELEMETRY") == "0":
        return
    try:
        payload = json.dumps({
            "install_id": install_id,
            "version": version,
            "os": platform.system(),
            "platform": platform.machine(),
        }).encode()
        req = urllib.request.Request(
            f"{os.environ.get('GCONTEXT_API', DEFAULT_API)}/api/telemetry",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "gcontext-cli",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception:
        pass
