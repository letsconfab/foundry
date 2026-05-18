import asyncio

from models import Confab
from services import hermes_deploy


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status = status
        self.payload = payload or {}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return self._text


class FakeOpenWebUISession:
    def __init__(self, responses, calls):
        self.responses = list(responses)
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


def _published_confab() -> Confab:
    return Confab(
        id=123,
        name="My Agent!",
        description="Does useful work",
        version="1.0.0",
        status="published",
        purpose="Answer policy questions",
        guardrails=[{"rule": "Use only approved policy", "enabled": True}],
        tests=[{"name": "Policy", "input": "Can I share it?", "expected_behavior": "Answer from policy"}],
        user_id=1,
    )


def test_normalizes_model_ids_deterministically():
    assert hermes_deploy.normalize_agent_name(" My_Agent!! 2026 ") == "my-agent-2026"
    assert hermes_deploy.normalize_agent_name("!!!") == "unnamed"


def test_renders_system_prompt_with_confab_expectations_and_workspace():
    prompt = hermes_deploy.render_confab_system_prompt(_published_confab(), "confabs/123")
    assert "My Agent!" in prompt
    assert "Answer policy questions" in prompt
    assert "Use only approved policy" in prompt
    assert "Can I share it?" in prompt
    assert "confabs/123" in prompt
    assert "no relevant result" in prompt


def test_deploy_updates_existing_openwebui_model(monkeypatch):
    calls = []
    responses = [
        FakeResponse(200, {"token": "tok"}),
        FakeResponse(200, {"id": "confab-123-my-agent"}),
    ]
    monkeypatch.setattr(
        hermes_deploy.aiohttp,
        "ClientSession",
        lambda: FakeOpenWebUISession(responses, calls),
    )

    result = asyncio.run(hermes_deploy.deploy_confab_to_openwebui(_published_confab(), "confabs/123"))

    assert result["status"] == "running"
    assert result["model_id"] == "confab-123-my-agent"
    assert calls[1][0] == "POST"
    assert calls[1][1].endswith("/api/v1/models/model/update")
    payload = calls[1][2]["json"]
    assert payload["base_model_id"] == "hermes-agent"
    assert payload["params"]["system"]


def test_deploy_creates_openwebui_model_when_update_misses(monkeypatch):
    calls = []
    responses = [
        FakeResponse(200, {"token": "tok"}),
        FakeResponse(404, text="missing"),
        FakeResponse(200, {"id": "confab-123-my-agent"}),
    ]
    monkeypatch.setattr(
        hermes_deploy.aiohttp,
        "ClientSession",
        lambda: FakeOpenWebUISession(responses, calls),
    )

    result = asyncio.run(hermes_deploy.deploy_confab_to_openwebui(_published_confab(), "confabs/123"))

    assert result["model_id"] == "confab-123-my-agent"
    assert calls[2][1].endswith("/api/v1/models/create")


def test_undeploy_deletes_openwebui_model(monkeypatch):
    calls = []
    responses = [
        FakeResponse(200, {"token": "tok"}),
        FakeResponse(200, {}),
    ]
    monkeypatch.setattr(
        hermes_deploy.aiohttp,
        "ClientSession",
        lambda: FakeOpenWebUISession(responses, calls),
    )

    success = asyncio.run(hermes_deploy.undeploy_confab_from_openwebui(_published_confab()))

    assert success is True
    assert calls[1][1].endswith("/api/v1/models/model/delete")
    assert calls[1][2]["json"] == {"id": "confab-123-my-agent"}


def test_status_reports_running_from_model_lookup(monkeypatch):
    calls = []
    responses = [
        FakeResponse(200, {"token": "tok"}),
        FakeResponse(200, {"data": [{"id": "confab-123-my-agent", "meta": {"rag_workspace": "confabs/123"}}]}),
    ]
    monkeypatch.setattr(
        hermes_deploy.aiohttp,
        "ClientSession",
        lambda: FakeOpenWebUISession(responses, calls),
    )
    monkeypatch.setattr(hermes_deploy, "OPENWEBUI_URL", "http://localhost:3001")

    status = asyncio.run(hermes_deploy.get_openwebui_deploy_status(_published_confab()))

    assert status == {
        "status": "running",
        "model_id": "confab-123-my-agent",
        "openwebui_url": "http://localhost:3001",
        "rag_workspace": "confabs/123",
    }


def test_status_returns_none_when_model_absent(monkeypatch):
    calls = []
    responses = [
        FakeResponse(200, {"token": "tok"}),
        FakeResponse(200, {"data": []}),
    ]
    monkeypatch.setattr(
        hermes_deploy.aiohttp,
        "ClientSession",
        lambda: FakeOpenWebUISession(responses, calls),
    )

    assert asyncio.run(hermes_deploy.get_openwebui_deploy_status(_published_confab())) is None
