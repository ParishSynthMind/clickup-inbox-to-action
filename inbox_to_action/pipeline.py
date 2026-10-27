"""Webhook event -> ClickUp task -> AI triage -> results written back to ClickUp."""
import logging

from .config import Settings
from .llm import TriageResult, Triager

log = logging.getLogger("inbox_to_action")

# Long Text custom fields hold plenty, but keep the summary tidy.
SUMMARY_MAX_CHARS = 2000


def field_display_value(field: dict):
    """Human-readable value of a custom field from a Get Task response.

    Dropdown values come back as the option's orderindex (an int) in Get Task,
    so map them to the option name. Other simple types pass through.
    """
    value = field.get("value")
    if value is None or value == "":
        return None
    if field.get("type") == "drop_down":
        for opt in field.get("type_config", {}).get("options", []):
            if str(opt.get("orderindex")) == str(value) or opt.get("id") == value:
                return opt.get("name")
    return value


def task_to_request_text(task: dict, skip_field_ids: set[str]) -> str:
    """Flatten a task (form submission) into plain text for the model."""
    lines = [f"Title: {task.get('name', '').strip()}"]
    description = (task.get("markdown_description") or task.get("text_content")
                   or task.get("description") or "").strip()
    if description:
        lines.append(f"Description:\n{description}")
    for f in task.get("custom_fields", []):
        if f.get("id") in skip_field_ids:
            continue
        value = field_display_value(f)
        if value is not None:
            lines.append(f"{f.get('name')}: {value}")
    return "\n".join(lines)


def dropdown_option_id(field: dict, option_name: str) -> str | None:
    for opt in field.get("type_config", {}).get("options", []):
        if opt.get("name", "").strip().lower() == option_name.strip().lower():
            return opt.get("id")
    return None


def format_comment(result: TriageResult) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items) if items else "- (none)"

    return (
        "AI triage (draft, needs a human check before anything is sent)\n\n"
        "SUMMARY\n" + "\n".join(result.summary) + "\n\n"
        f"SERVICE TYPE: {result.service_type}\n"
        f"URGENCY: {result.urgency} ({result.urgency_reason})\n\n"
        "PROPOSAL OUTLINE\n" + bullets(result.proposal_outline) + "\n\n"
        "MISSING INFO TO ASK FOR\n" + bullets(result.missing_info) + "\n\n"
        "DRAFT REPLY EMAIL\n" + result.reply_email + "\n\n"
        "To approve: review the draft, then move this task to Approved."
    )


def process_event(payload: dict, clickup, triager: Triager, settings: Settings) -> dict:
    """Handle one webhook payload. Returns a dict describing what happened."""
    if payload.get("event") != "taskCreated":
        return {"status": "ignored", "reason": f"event {payload.get('event')!r} not handled"}
    task_id = payload.get("task_id")
    if not task_id:
        return {"status": "ignored", "reason": "no task_id in payload"}

    task = clickup.get_task(task_id)
    if task.get("parent"):
        # Subtasks (e.g. the kickoff checklist a template adds) are not new enquiries.
        return {"status": "ignored", "reason": "subtask"}
    list_id = str(task.get("list", {}).get("id", ""))
    if settings.intake_list_id and list_id != str(settings.intake_list_id):
        return {"status": "ignored", "reason": f"task is in list {list_id}, not the Intake list"}

    fields_by_id = {f.get("id"): f for f in task.get("custom_fields", [])}
    summary_field = fields_by_id.get(settings.ai_summary_field_id)
    if summary_field and summary_field.get("value"):
        # Already triaged (e.g. ClickUp retried the delivery). Don't double-post.
        return {"status": "skipped", "reason": "AI Summary already filled", "task_id": task_id}

    ai_field_ids = {settings.ai_summary_field_id, settings.ai_priority_field_id}
    request_text = task_to_request_text(task, ai_field_ids)
    result = triager.triage(request_text, settings.service_types)

    actions = []
    if settings.ai_summary_field_id:
        summary_text = "\n".join(result.summary)[:SUMMARY_MAX_CHARS]
        clickup.set_field(task_id, settings.ai_summary_field_id, summary_text)
        actions.append("set AI Summary")
    if settings.ai_priority_field_id:
        priority_field = fields_by_id.get(settings.ai_priority_field_id, {})
        option_id = dropdown_option_id(priority_field, result.urgency)
        if option_id:
            clickup.set_field(task_id, settings.ai_priority_field_id, option_id)
            actions.append(f"set AI Priority = {result.urgency}")
        else:
            log.warning("AI Priority has no option named %r; skipped", result.urgency)
            actions.append(f"AI Priority option {result.urgency!r} not found, skipped")
    if settings.post_comment:
        clickup.post_comment(task_id, format_comment(result))
        actions.append("posted triage comment")

    return {
        "status": "processed",
        "task_id": task_id,
        "task_name": task.get("name"),
        "actions": actions,
        "triage": result.to_dict(),
        "comment": format_comment(result),
    }
