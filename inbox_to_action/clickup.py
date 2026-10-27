"""Minimal ClickUp API v2 client (standard library only).

Endpoints used, as documented at developer.clickup.com/reference:
  GET  /v2/team                        Get Authorized Workspaces
  GET  /v2/task/{task_id}              Get Task
  GET  /v2/list/{list_id}/field        Get List Custom Fields
  POST /v2/task/{task_id}/field/{id}   Set Custom Field Value
  POST /v2/task/{task_id}/comment      Create Task Comment
  POST /v2/team/{team_id}/webhook      Create Webhook
  GET  /v2/team/{team_id}/webhook      Get Webhooks

Auth: personal API token (starts "pk_") in the Authorization header.
"""
import json
import urllib.error
import urllib.request

API_BASE = "https://api.clickup.com/api/v2"


class ClickUpError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"ClickUp API error {status}: {body[:300]}")
        self.status = status
        self.body = body


class ClickUpClient:
    def __init__(self, token: str, base_url: str = API_BASE, timeout: float = 20.0):
        if not token:
            raise ValueError("CLICKUP_API_TOKEN is not set")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Authorization": self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode() or "{}"
        except urllib.error.HTTPError as e:
            raise ClickUpError(e.code, e.read().decode(errors="replace")) from e
        return json.loads(raw)

    # --- reads ---
    def get_workspaces(self) -> list[dict]:
        return self._request("GET", "/team").get("teams", [])

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"/task/{task_id}?include_markdown_description=true")

    def get_list_fields(self, list_id: str) -> list[dict]:
        return self._request("GET", f"/list/{list_id}/field").get("fields", [])

    def get_webhooks(self, team_id: str) -> list[dict]:
        return self._request("GET", f"/team/{team_id}/webhook").get("webhooks", [])

    # --- writes ---
    def set_field(self, task_id: str, field_id: str, value) -> dict:
        """Text fields take a string; dropdowns take the option's UUID."""
        return self._request("POST", f"/task/{task_id}/field/{field_id}", {"value": value})

    def post_comment(self, task_id: str, text: str, notify_all: bool = False) -> dict:
        return self._request(
            "POST", f"/task/{task_id}/comment", {"comment_text": text, "notify_all": notify_all}
        )

    def create_webhook(self, team_id: str, endpoint: str, events: list[str], list_id: str | None = None) -> dict:
        body: dict = {"endpoint": endpoint, "events": events}
        if list_id:
            body["list_id"] = int(list_id)
        return self._request("POST", f"/team/{team_id}/webhook", body)
