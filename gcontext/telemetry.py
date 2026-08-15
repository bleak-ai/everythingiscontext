import json
import os
import platform
import ssl
import urllib.request

import certifi

DEFAULT_API = "https://api.gcontext.ai"


def _is_dev_install() -> bool:
    return "site-packages" not in os.path.abspath(__file__)


def ping_install(install_id: str, version: str) -> None:
    if os.environ.get("GCONTEXT_TELEMETRY") == "0" or _is_dev_install():
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
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=3, context=ctx):
            pass
    except Exception:
        pass
