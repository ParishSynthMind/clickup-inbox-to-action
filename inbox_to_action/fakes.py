"""In-memory stand-in for ClickUpClient, used by the dry run and the tests.

It serves tasks from JSON files and records every write instead of sending it.
"""
import copy


class FakeClickUp:
    def __init__(self, tasks: dict[str, dict]):
        self.tasks = {k: copy.deepcopy(v) for k, v in tasks.items()}
        self.writes: list[dict] = []

    def get_task(self, task_id: str) -> dict:
        return copy.deepcopy(self.tasks[task_id])

    def set_field(self, task_id: str, field_id: str, value):
        self.writes.append({"call": "set_field", "task_id": task_id, "field_id": field_id, "value": value})
        for f in self.tasks[task_id].get("custom_fields", []):
            if f["id"] == field_id:
                f["value"] = value
        return {}

    def post_comment(self, task_id: str, text: str, notify_all: bool = False):
        self.writes.append({"call": "post_comment", "task_id": task_id, "text": text})
        return {"id": f"comment-{len(self.writes)}"}
