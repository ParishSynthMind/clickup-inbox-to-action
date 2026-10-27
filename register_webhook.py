#!/usr/bin/env python3
"""Register (or list) the ClickUp webhook through the API.

Free-plan ClickUp has no "Call webhook" automation action, but webhooks made
through the public API work on every plan. This script makes one that fires
on taskCreated, scoped to the Intake list.

    python register_webhook.py --list
    python register_webhook.py --endpoint https://<public-url>/clickup/webhook

Needs CLICKUP_API_TOKEN, CLICKUP_TEAM_ID and (recommended) CLICKUP_INTAKE_LIST_ID.
The response contains the webhook's signing secret: it is written straight
into .env as CLICKUP_WEBHOOK_SECRET and never printed in full.
"""
import argparse
from pathlib import Path

from inbox_to_action.clickup import ClickUpClient
from inbox_to_action.config import Settings

ENV_FILE = Path.cwd() / ".env"


def save_secret(secret: str) -> None:
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    lines = [l for l in lines if not l.startswith("CLICKUP_WEBHOOK_SECRET=")]
    lines.append(f"CLICKUP_WEBHOOK_SECRET={secret}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ENV_FILE.chmod(0o600)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", help="public HTTPS URL ending in /clickup/webhook")
    ap.add_argument("--list", action="store_true", help="show existing webhooks and their health")
    args = ap.parse_args()

    s = Settings.from_env()
    if not s.team_id:
        raise SystemExit("Set CLICKUP_TEAM_ID (run setup_fields.py --workspaces to find it)")
    client = ClickUpClient(s.clickup_token)

    if args.list:
        for w in client.get_webhooks(s.team_id):
            h = w.get("health", {})
            print(f"{w['id']}  {w['endpoint']}  events={w.get('events')}  list={w.get('list_id')}  "
                  f"health={h.get('status')} fails={h.get('fail_count')}")
        return
    if not args.endpoint:
        ap.error("--endpoint is required unless --list is used")
    if not args.endpoint.startswith("https://"):
        raise SystemExit("Use an https:// endpoint")

    resp = client.create_webhook(s.team_id, args.endpoint, ["taskCreated"], s.intake_list_id or None)
    hook = resp.get("webhook", resp)
    secret = hook.get("secret", "")
    print(f"Webhook created: id={resp.get('id') or hook.get('id')}")
    if secret:
        save_secret(secret)
        print(f"Signing secret saved to {ENV_FILE} as CLICKUP_WEBHOOK_SECRET (value not shown)")
    else:
        print("No secret in the response; check the webhook with --list")


if __name__ == "__main__":
    main()
