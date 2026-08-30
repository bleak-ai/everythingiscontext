import json
import platform
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from unittest.mock import patch

from gcontext.telemetry import ping_install


class CaptureHandler(BaseHTTPRequestHandler):
    captured = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        CaptureHandler.captured.append(body)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_ping_install_sends_payload():
    CaptureHandler.captured = []
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    port = server.server_address[1]
    t = Thread(target=server.handle_request, daemon=True)
    t.start()

    # the suite runs from the dev checkout, which the dev-install guard mutes
    with patch.dict("os.environ", {
        "GCONTEXT_API": f"http://127.0.0.1:{port}",
        "GCONTEXT_TELEMETRY": "1",
    }), \
         patch("gcontext.telemetry._is_dev_install", return_value=False):
        ping_install("test-uuid-123", "0.5.0")

    t.join(timeout=5)
    server.server_close()

    assert len(CaptureHandler.captured) == 1
    payload = CaptureHandler.captured[0]
    assert payload["install_id"] == "test-uuid-123"
    assert payload["version"] == "0.5.0"
    assert payload["os"] == platform.system()
    assert payload["platform"] == platform.machine()


def test_ping_install_silently_fails_on_network_error():
    with patch.dict("os.environ", {
        "GCONTEXT_API": "http://127.0.0.1:1",
        "GCONTEXT_TELEMETRY": "1",
    }):
        ping_install("x", "0.0.0")


def test_ping_install_skipped_when_telemetry_disabled():
    CaptureHandler.captured = []
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    port = server.server_address[1]

    with patch.dict("os.environ", {
        "GCONTEXT_API": f"http://127.0.0.1:{port}",
        "GCONTEXT_TELEMETRY": "0",
    }):
        ping_install("x", "0.5.0")

    server.server_close()
    assert len(CaptureHandler.captured) == 0
