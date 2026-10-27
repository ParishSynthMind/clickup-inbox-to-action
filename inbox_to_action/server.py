"""Webhook receiver (standard library HTTP server).

POST /clickup/webhook  ClickUp sends taskCreated events here.
GET  /health           Simple liveness check.

ClickUp marks a webhook as failing if the reply takes longer than 7 seconds,
and an LLM call can take longer than that. So the handler only checks the
signature, queues the event and answers 200 straight away; a background
worker does the slow part.

A bad signature gets 403, not 401: ClickUp suspends a webhook immediately if
it ever receives a 401, so one misconfigured secret would otherwise switch
the whole integration off.
"""
import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .clickup import ClickUpClient
from .config import Settings
from .llm import AnthropicTriager
from .pipeline import process_event
from .signature import is_valid_signature

log = logging.getLogger("inbox_to_action")
WEBHOOK_PATH = "/clickup/webhook"
MAX_BODY_BYTES = 1_000_000


def make_handler(settings: Settings, jobs: "queue.Queue[dict]"):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                return self._reply(200, {"ok": True})
            self._reply(404, {"error": "not found"})

        def do_POST(self):
            if self.path != WEBHOOK_PATH:
                return self._reply(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                return self._reply(400, {"error": "bad body size"})
            raw = self.rfile.read(length)
            if not is_valid_signature(settings.webhook_secret, raw, self.headers.get("X-Signature")):
                log.warning("Rejected request with missing or bad X-Signature")
                return self._reply(403, {"error": "invalid signature"})
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return self._reply(400, {"error": "invalid json"})
            jobs.put(payload)
            self._reply(200, {"queued": True})

        def log_message(self, fmt, *args):  # route http.server logs through logging
            log.info("%s - %s", self.address_string(), fmt % args)

    return Handler


def worker(jobs: "queue.Queue[dict]", clickup, triager, settings: Settings):
    seen: set[str] = set()
    while True:
        payload = jobs.get()
        key = f"{payload.get('webhook_id')}:{payload.get('event')}:{payload.get('task_id')}"
        if key in seen:
            log.info("Duplicate delivery %s ignored", key)
            continue
        seen.add(key)
        try:
            result = process_event(payload, clickup, triager, settings)
            log.info("Event %s -> %s %s", key, result["status"], result.get("actions", result.get("reason")))
        except Exception:
            log.exception("Failed to process %s", key)
            seen.discard(key)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.webhook_secret:
        raise SystemExit("CLICKUP_WEBHOOK_SECRET is not set (run register_webhook.py first)")
    clickup = ClickUpClient(settings.clickup_token)
    triager = AnthropicTriager(model=settings.llm_model)
    jobs: "queue.Queue[dict]" = queue.Queue()
    threading.Thread(target=worker, args=(jobs, clickup, triager, settings), daemon=True).start()
    server = ThreadingHTTPServer((settings.host, settings.port), make_handler(settings, jobs))
    log.info("Listening on http://%s:%s%s", settings.host, settings.port, WEBHOOK_PATH)
    server.serve_forever()


if __name__ == "__main__":
    main()
