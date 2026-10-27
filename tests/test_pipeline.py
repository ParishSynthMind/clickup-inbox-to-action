import io
import json
import queue
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbox_to_action.clickup import ClickUpClient
from inbox_to_action.config import Settings
from inbox_to_action.fakes import FakeClickUp
from inbox_to_action.llm import AnthropicTriager, TriageResult
from inbox_to_action.pipeline import field_display_value, process_event, task_to_request_text
from inbox_to_action.server import make_handler
from inbox_to_action.signature import compute_signature, is_valid_signature
from setup_fields import check_fields

SAMPLES = Path(__file__).parent.parent / "samples"
PAYLOAD = json.loads((SAMPLES / "webhook_task_created.json").read_text())
TASK = json.loads((SAMPLES / "task_86demo001.json").read_text())


def settings(**kw):
    base = dict(intake_list_id="901234567", ai_summary_field_id="f-ai-summary", ai_priority_field_id="f-ai-priority")
    base.update(kw)
    return Settings(**base)


class StubTriager:
    def __init__(self, urgency="High"):
        self.urgency = urgency
        self.calls = []

    def triage(self, request_text, service_types):
        self.calls.append(request_text)
        return TriageResult(
            summary=["Dental group, 3 clinics.", "Wants enquiries as tasks.", "Deadline: next month."],
            service_type="Workspace setup", urgency=self.urgency, urgency_reason="Hard deadline.",
            proposal_outline=["Discovery", "Build"], reply_email="Hi Sam, thanks...", missing_info=["Website platform"],
        )


# --- signature ---------------------------------------------------------------

def test_signature_matches_clickup_doc_example():
    # Same body and key as the Node.js sample on developer.clickup.com/docs/webhooksignature
    body = b'{"webhook_id":"7689a169-a000-4985-8676-6902b96d6627","event":"taskCreated","task_id":"c0j"}'
    sig = compute_signature("secret", body)
    assert len(sig) == 64 and is_valid_signature("secret", body, sig)


def test_signature_rejects_tampering_and_missing():
    body = b'{"a":1}'
    sig = compute_signature("s3cret", body)
    assert not is_valid_signature("s3cret", b'{"a":2}', sig)
    assert not is_valid_signature("wrong", body, sig)
    assert not is_valid_signature("s3cret", body, None)
    assert not is_valid_signature("", body, sig)


# --- pipeline ----------------------------------------------------------------

def test_full_pipeline_writes_fields_and_comment():
    cu, llm = FakeClickUp({"86demo001": TASK}), StubTriager("High")
    result = process_event(PAYLOAD, cu, llm, settings())
    assert result["status"] == "processed"
    calls = [(w["call"], w.get("field_id"), w.get("value")) for w in cu.writes]
    assert ("set_field", "f-ai-summary", "Dental group, 3 clinics.\nWants enquiries as tasks.\nDeadline: next month.") in calls
    assert ("set_field", "f-ai-priority", "opt-p-1") in calls  # dropdown takes the option UUID
    comment = [w for w in cu.writes if w["call"] == "post_comment"][0]["text"]
    assert "DRAFT REPLY EMAIL" in comment and "Website platform" in comment


def test_request_text_includes_form_fields_but_not_ai_fields():
    text = task_to_request_text(TASK, {"f-ai-summary", "f-ai-priority"})
    assert "Brightside Dental Group" in text
    assert "Budget band: $500 - $2,000" in text  # dropdown orderindex mapped to name
    assert "AI Priority" not in text


def test_dropdown_value_mapping():
    field = TASK["custom_fields"][1]
    assert field_display_value(field) == "$500 - $2,000"
    assert field_display_value({"type": "text", "value": ""}) is None


def test_retry_of_same_event_is_skipped():
    cu, llm = FakeClickUp({"86demo001": TASK}), StubTriager()
    process_event(PAYLOAD, cu, llm, settings())
    again = process_event(PAYLOAD, cu, llm, settings())
    assert again["status"] == "skipped" and len(llm.calls) == 1


def test_other_lists_and_events_ignored():
    cu, llm = FakeClickUp({"86demo001": TASK}), StubTriager()
    assert process_event(PAYLOAD, cu, llm, settings(intake_list_id="999"))["status"] == "ignored"
    assert process_event({**PAYLOAD, "event": "taskUpdated"}, cu, llm, settings())["status"] == "ignored"
    assert cu.writes == [] and llm.calls == []


def test_subtasks_are_ignored():
    cu, llm = FakeClickUp({"86demo001": {**TASK, "parent": "86parent"}}), StubTriager()
    assert process_event(PAYLOAD, cu, llm, settings())["reason"] == "subtask"
    assert llm.calls == []


def test_unconfigured_fields_are_skipped_to_save_free_plan_uses():
    cu = FakeClickUp({"86demo001": TASK})
    process_event(PAYLOAD, cu, StubTriager(), settings(ai_summary_field_id="", ai_priority_field_id=""))
    assert [w["call"] for w in cu.writes] == ["post_comment"]


def test_missing_priority_option_does_not_crash():
    cu = FakeClickUp({"86demo001": TASK})
    result = process_event(PAYLOAD, cu, StubTriager("Whenever"), settings())
    assert any("not found" in a for a in result["actions"])


# --- LLM adapter (Anthropic client mocked) -----------------------------------

class FakeAnthropic:
    def __init__(self, text, stop_reason="end_turn"):
        self.kwargs = None
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.kwargs = kwargs
                return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])

        self.beta = SimpleNamespace(messages=_Messages())


def test_anthropic_triager_parses_structured_output():
    data = {"summary": ["a", "b", "c", "d"], "service_type": "Automation", "urgency": "Urgent",
            "urgency_reason": "x", "proposal_outline": ["p"], "reply_email": "Hi", "missing_info": []}
    fake = FakeAnthropic(json.dumps(data))
    r = AnthropicTriager(model="claude-opus-5-5", client=fake).triage("text", ["Automation", "Consulting / other"])
    assert r.summary == ["a", "b", "c"] and r.urgency == "Urgent"
    schema = fake.kwargs["output_config"]["format"]["schema"]
    assert schema["properties"]["service_type"]["enum"] == ["Automation", "Consulting / other"]
    assert "<client_request>" in fake.kwargs["messages"][0]["content"]


def test_anthropic_triager_normalises_bad_values_and_handles_refusal():
    data = {"summary": [], "service_type": "Made up", "urgency": "Panic"}
    r = AnthropicTriager(client=FakeAnthropic(json.dumps(data))).triage("t", ["A", "Other"])
    assert r.service_type == "Other" and r.urgency == "Normal"
    with pytest.raises(RuntimeError):
        AnthropicTriager(client=FakeAnthropic("", stop_reason="refusal")).triage("t", ["A"])


# --- ClickUp client (HTTP mocked) --------------------------------------------

def test_clickup_client_request_shapes(monkeypatch):
    sent = []

    def fake_urlopen(req, timeout):
        sent.append((req.get_method(), req.full_url, req.headers, json.loads(req.data) if req.data else None))
        return io.BytesIO(b'{"id": "1"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    c = ClickUpClient("pk_test")
    c.set_field("t1", "f1", "opt-uuid")
    c.post_comment("t1", "hello")
    c.create_webhook("42", "https://x.example/clickup/webhook", ["taskCreated"], "901")
    (m1, u1, h1, b1), (m2, u2, _, b2), (m3, u3, _, b3) = sent
    assert (m1, u1, b1) == ("POST", "https://api.clickup.com/api/v2/task/t1/field/f1", {"value": "opt-uuid"})
    assert h1["Authorization"] == "pk_test"
    assert (u2, b2) == ("https://api.clickup.com/api/v2/task/t1/comment", {"comment_text": "hello", "notify_all": False})
    assert (u3, b3) == ("https://api.clickup.com/api/v2/team/42/webhook",
                        {"endpoint": "https://x.example/clickup/webhook", "events": ["taskCreated"], "list_id": 901})


# --- setup_fields mapping ----------------------------------------------------

def test_check_fields_maps_ids_and_flags_problems():
    found, problems = check_fields(TASK["custom_fields"], "AI Summary", "AI Priority",
                                   ["Workspace setup", "Automation", "Integration / API", "AI assistant", "Consulting / other"])
    assert found == {"CLICKUP_AI_SUMMARY_FIELD_ID": "f-ai-summary", "CLICKUP_AI_PRIORITY_FIELD_ID": "f-ai-priority"}
    assert problems == []
    _, problems = check_fields([], "AI Summary", "AI Priority", [])
    assert len(problems) == 2


# --- HTTP server: signature gate and fast 200 --------------------------------

@pytest.fixture
def server():
    jobs = queue.Queue()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Settings(webhook_secret="hook-secret"), jobs))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", jobs
    srv.shutdown()


def post(url, body, sig):
    req = urllib.request.Request(url, data=body, method="POST", headers={"X-Signature": sig, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_server_queues_signed_request(server):
    base, jobs = server
    body = json.dumps(PAYLOAD).encode()
    assert post(f"{base}/clickup/webhook", body, compute_signature("hook-secret", body)) == 200
    assert jobs.get_nowait()["task_id"] == "86demo001"


def test_server_rejects_bad_signature_with_403_not_401(server):
    base, jobs = server
    body = json.dumps(PAYLOAD).encode()
    assert post(f"{base}/clickup/webhook", body, "deadbeef") == 403
    assert jobs.empty()
