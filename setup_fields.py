#!/usr/bin/env python3
"""Find the IDs this service needs and check the custom fields are set up right.

ClickUp's public API (v2) can read and fill custom fields but has no endpoint
to create one, so the fields are created once in the ClickUp UI (see
WORKSPACE-BUILD-GUIDE.md) and this script maps them by name.

    python setup_fields.py --workspaces           # print Workspace (team) IDs
    python setup_fields.py                        # check Intake list fields, print .env lines

Needs CLICKUP_API_TOKEN, and CLICKUP_INTAKE_LIST_ID for the field check.
Field names can be overridden with AI_SUMMARY_FIELD_NAME / AI_PRIORITY_FIELD_NAME.
"""
import argparse
import os

from inbox_to_action.clickup import ClickUpClient
from inbox_to_action.config import Settings
from inbox_to_action.llm import URGENCY_LEVELS

TEXT_TYPES = {"text", "short_text"}


def check_fields(fields: list[dict], summary_name: str, priority_name: str, service_types: list[str]) -> tuple[dict, list[str]]:
    """Return ({env_var: field_id}, [problems])."""
    by_name = {f["name"].strip().lower(): f for f in fields}
    found, problems = {}, []

    summary = by_name.get(summary_name.lower())
    if not summary:
        problems.append(f"Missing field '{summary_name}' (type Text)")
    elif summary["type"] not in TEXT_TYPES:
        problems.append(f"'{summary_name}' is type {summary['type']}, expected Text")
    else:
        found["CLICKUP_AI_SUMMARY_FIELD_ID"] = summary["id"]

    priority = by_name.get(priority_name.lower())
    if not priority:
        problems.append(f"Missing field '{priority_name}' (type Dropdown: {', '.join(URGENCY_LEVELS)})")
    elif priority["type"] != "drop_down":
        problems.append(f"'{priority_name}' is type {priority['type']}, expected Dropdown")
    else:
        names = {o["name"].strip().lower() for o in priority.get("type_config", {}).get("options", [])}
        missing = [u for u in URGENCY_LEVELS if u.lower() not in names]
        if missing:
            problems.append(f"'{priority_name}' dropdown is missing options: {', '.join(missing)}")
        found["CLICKUP_AI_PRIORITY_FIELD_ID"] = priority["id"]

    service = by_name.get("service type")
    if service and service["type"] == "drop_down":
        options = [o["name"] for o in service.get("type_config", {}).get("options", [])]
        if options and options != service_types:
            found["SERVICE_TYPES"] = ",".join(options)
    return found, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspaces", action="store_true")
    args = ap.parse_args()

    s = Settings.from_env()
    client = ClickUpClient(s.clickup_token)
    if args.workspaces:
        for t in client.get_workspaces():
            print(f"CLICKUP_TEAM_ID={t['id']}   # {t['name']}")
        return
    if not s.intake_list_id:
        raise SystemExit("Set CLICKUP_INTAKE_LIST_ID (the number in the Intake list's URL)")

    found, problems = check_fields(
        client.get_list_fields(s.intake_list_id),
        os.environ.get("AI_SUMMARY_FIELD_NAME", "AI Summary"),
        os.environ.get("AI_PRIORITY_FIELD_NAME", "AI Priority"),
        s.service_types,
    )
    for p in problems:
        print(f"PROBLEM: {p}")
    if found:
        print("\nAdd these to .env:")
        for k, v in found.items():
            print(f"{k}={v}")
    if problems:
        raise SystemExit(1)
    print("\nAll fields look right.")


if __name__ == "__main__":
    main()
