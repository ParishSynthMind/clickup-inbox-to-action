#!/usr/bin/env python3
"""Run the whole pipeline on a sample webhook, with no ClickUp account.

    python dry_run.py --offline          # no API key needed, canned AI step
    python dry_run.py                    # real Claude call (needs ANTHROPIC_API_KEY)

Steps shown: sign the sample payload the way ClickUp would, verify the
signature, "fetch" the task from samples/, run the AI triage, and print the
exact ClickUp writes (custom fields + comment) that would be made.
"""
import argparse
import json
import os
from pathlib import Path

from inbox_to_action.config import Settings
from inbox_to_action.fakes import FakeClickUp
from inbox_to_action.llm import AnthropicTriager, OfflineTriager
from inbox_to_action.pipeline import process_event
from inbox_to_action.signature import compute_signature, is_valid_signature

HERE = Path(__file__).parent
DEMO_SECRET = "dry-run-demo-secret-not-a-real-one"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--payload", default=str(HERE / "samples/webhook_task_created.json"))
    ap.add_argument("--offline", action="store_true", help="skip the real LLM call")
    args = ap.parse_args()

    raw = Path(args.payload).read_bytes()
    payload = json.loads(raw)
    tasks = {p.stem.removeprefix("task_"): json.loads(p.read_text()) for p in (HERE / "samples").glob("task_*.json")}

    print("1. Signature check")
    sig = compute_signature(DEMO_SECRET, raw)
    print(f"   X-Signature (demo secret): {sig[:16]}...  valid={is_valid_signature(DEMO_SECRET, raw, sig)}")
    print(f"   tampered body valid={is_valid_signature(DEMO_SECRET, raw + b' ', sig)}")

    settings = Settings(
        intake_list_id="901234567",
        ai_summary_field_id="f-ai-summary",
        ai_priority_field_id="f-ai-priority",
        llm_model=os.environ.get("LLM_MODEL", "claude-opus-5-5"),
    )
    if args.offline or not os.environ.get("ANTHROPIC_API_KEY"):
        if not args.offline:
            print("\n   (ANTHROPIC_API_KEY not set, falling back to --offline)")
        triager, mode = OfflineTriager(), "offline canned triage"
    else:
        triager, mode = AnthropicTriager(model=settings.llm_model), f"live {settings.llm_model}"

    clickup = FakeClickUp(tasks)
    print(f"\n2. Pipeline ({mode})")
    result = process_event(payload, clickup, triager, settings)
    print(f"   status: {result['status']}  actions: {result.get('actions', result.get('reason'))}")

    print("\n3. ClickUp writes that would be sent")
    for w in clickup.writes:
        if w["call"] == "set_field":
            print(f"   POST /v2/task/{w['task_id']}/field/{w['field_id']}  value={w['value']!r}")
        else:
            print(f"   POST /v2/task/{w['task_id']}/comment\n")
            print("   " + w["text"].replace("\n", "\n   "))

    print("\n4. Re-delivery of the same event (ClickUp retry)")
    again = process_event(payload, clickup, triager, settings)
    print(f"   status: {again['status']}  ({again.get('reason')})")


if __name__ == "__main__":
    main()
