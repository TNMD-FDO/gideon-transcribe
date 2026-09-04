"""The engine plumbing: the client's rules, the status row, and the stack's shape.

The AI assistant's engine is reached only from llm-worker, on the engine's own
network, with a token from a secret file. What is checked here is what would
be expensive to get wrong: a failure is always one of six reason classes and
never text; the status row turns the moment the answer changes; a stack with
no engine still starts; and the two compose files that make the shared engine
reachable say exactly what the architecture chapter fixes.
"""

import re
from pathlib import Path

import pytest
import yaml
from core import engine, settings_store

HERE = Path(__file__).resolve().parent.parent.parent
COMPOSE = HERE / "compose.yaml"
SHARED = HERE / "compose.shared-engine.yaml"
SCRIPT = HERE / "transcribe"
ENTRYPOINT = HERE / "app" / "entrypoint.sh"


# Reason classes -----------------------------------------------------------------


def test_every_failure_is_one_of_six_reason_classes():
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        PermissionDeniedError,
    )

    request = object()

    def status_error(cls, status, message):
        import httpx

        response = httpx.Response(status, request=httpx.Request("POST", "http://x"))
        return cls(message, response=response, body=None)

    assert engine.classify(APIConnectionError(request=request)) == engine.UNREACHABLE
    assert engine.classify(APITimeoutError(request=request)) == engine.TIMEOUT
    assert (
        engine.classify(status_error(AuthenticationError, 401, "no")) == engine.REFUSED
    )
    assert (
        engine.classify(status_error(PermissionDeniedError, 403, "no"))
        == engine.REFUSED
    )
    assert (
        engine.classify(
            status_error(BadRequestError, 400, "Input length exceeds context length")
        )
        == engine.TOO_LONG
    )
    assert engine.classify(status_error(BadRequestError, 400, "other")) == engine.ERROR
    assert engine.classify(RuntimeError("anything")) == engine.ERROR
    assert engine.classify(engine.Problem(engine.BAD_OUTPUT)) == engine.BAD_OUTPUT


def test_every_reason_class_has_a_line_for_the_person():
    for reason in (
        engine.UNREACHABLE,
        engine.TIMEOUT,
        engine.REFUSED,
        engine.TOO_LONG,
        engine.BAD_OUTPUT,
        engine.ERROR,
    ):
        assert reason in engine.WHAT_TO_SAY
        assert reason.startswith("llm_")


def test_the_audit_catalogue_names_the_same_six():
    from core.audit import Reason

    ours = {
        engine.UNREACHABLE,
        engine.TIMEOUT,
        engine.REFUSED,
        engine.TOO_LONG,
        engine.BAD_OUTPUT,
        engine.ERROR,
    }
    theirs = {value for name, value in vars(Reason).items() if name.startswith("LLM_")}
    assert ours == theirs


# The token ------------------------------------------------------------------------


def test_the_token_is_read_from_the_file_the_environment_names(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "TOKEN_PATH", tmp_path / "not-mounted")
    file = tmp_path / "llm_api_token"
    monkeypatch.setenv("LLM_API_TOKEN_FILE", str(file))

    assert engine.token() == ""
    assert not engine.token_is_set()

    file.write_text("  sk-something  \n", encoding="utf-8")
    assert engine.token() == "sk-something"
    assert engine.token_is_set()


def test_the_mounted_secret_wins_over_the_environment(tmp_path, monkeypatch):
    mounted = tmp_path / "run-secrets-token"
    mounted.write_text("mounted", encoding="utf-8")
    monkeypatch.setattr(engine, "TOKEN_PATH", mounted)
    other = tmp_path / "other"
    other.write_text("other", encoding="utf-8")
    monkeypatch.setenv("LLM_API_TOKEN_FILE", str(other))
    assert engine.token() == "mounted"


# The status row --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_status_row_turns_when_the_answer_changes():
    status = engine.EngineStatus.the_one()
    assert status.checked_at is None

    status.record(True, served_models=["gideon-generator"])
    first_since = status.since
    assert status.reachable and status.served_models == ["gideon-generator"]

    status.record(True, served_models=["gideon-generator"])
    assert status.since == first_since, "still reachable: since does not move"

    status.record(False, reason=engine.UNREACHABLE)
    assert not status.reachable
    assert status.since > first_since
    assert status.reason == engine.UNREACHABLE


@pytest.mark.django_db
def test_the_check_is_quiet_when_no_engine_is_configured(monkeypatch):
    monkeypatch.setattr(engine, "token_is_set", lambda: False)
    settings_store.set_to("assistant_available", False)

    def never(*_a, **_k):
        raise AssertionError("the network was touched")

    monkeypatch.setattr(engine, "list_models", never)
    status = engine.check()
    assert not status.reachable
    assert engine.status_for_the_panel()["state"] == "off"


@pytest.mark.django_db
def test_the_check_records_what_the_engine_serves(monkeypatch):
    monkeypatch.setattr(engine, "token_is_set", lambda: True)
    monkeypatch.setattr(engine, "list_models", lambda: ["gideon-generator"])
    settings_store.set_to("engine_model", "gideon-generator")

    status = engine.check()

    assert status.reachable
    assert status.served_models == ["gideon-generator"]
    told = engine.status_for_the_panel()
    assert told["state"] == "reachable"
    assert "gideon-generator" in told["says"]


@pytest.mark.django_db
def test_the_check_names_the_reason_when_the_engine_refuses(monkeypatch):
    import httpx
    from openai import AuthenticationError

    monkeypatch.setattr(engine, "token_is_set", lambda: True)

    def refused():
        response = httpx.Response(401, request=httpx.Request("GET", "http://x"))
        raise AuthenticationError("no", response=response, body=None)

    monkeypatch.setattr(engine, "list_models", refused)
    status = engine.check()

    assert not status.reachable
    assert status.reason == engine.REFUSED
    assert engine.status_for_the_panel()["state"] == "unreachable"


# The stack's shape -------------------------------------------------------------------


def compose_services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def test_llm_worker_is_the_fourth_service_on_its_own_queue():
    services = compose_services()
    worker = services["llm-worker"]
    assert worker["command"] == ["llm-worker"]
    assert worker["networks"] == ["transcribe"], (
        "only the shared-engine file adds another"
    )
    assert "llm_api_token" in worker["secrets"]
    assert "--queues llm" in ENTRYPOINT.read_text(encoding="utf-8")


def test_the_web_container_sees_the_token_only_to_say_set_or_missing():
    services = compose_services()
    assert "llm_api_token" in services["app"]["secrets"]
    for other in ("worker", "media-worker"):
        assert "llm_api_token" not in services[other]["secrets"]


def test_the_token_secret_always_has_a_file():
    # A secret whose file is missing stops the whole stack, and an office with
    # no engine still has to start. install and upgrade both make the file.
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ensure_the_token_file" in text
    upgrade = text[text.index("cmd_upgrade()") :]
    assert upgrade.index("ensure_the_token_file") < upgrade.index("compose up -d")


def test_the_shared_engine_file_joins_llm_worker_and_nothing_else():
    shared = yaml.safe_load(SHARED.read_text(encoding="utf-8"))
    assert list(shared["services"]) == ["llm-worker"]
    assert shared["services"]["llm-worker"]["networks"] == ["engine"]
    network = shared["networks"]["engine"]
    assert network["external"] is True
    assert "LLM_NETWORK" in network["name"]


def test_the_local_engine_is_off_by_default_and_pinned():
    vllm = compose_services()["vllm"]
    assert vllm["profiles"] == ["llm"]
    assert re.match(r"vllm/vllm-openai:v[\d.]+@sha256:[0-9a-f]{64}$", vllm["image"])
    assert "local-engine" in vllm["command"]
    assert "131072" in vllm["command"]
    assert vllm["environment"]["VLLM_USE_DEEP_GEMM"] == "0"
    assert "llm_api_token" in vllm["secrets"]


def test_the_database_is_reached_by_a_name_no_other_project_uses():
    """llm-worker sits on two networks, and the other one may have a postgres.

    It did: the office's platform project runs a service called postgres on
    the engine's network, Docker's DNS answered a bare `postgres` with that
    one, and llm-worker signed in to the wrong database ten times and never
    started. So the app reaches its database by an alias of its own, declared
    on the postgres service and used by every container.
    """
    text = COMPOSE.read_text(encoding="utf-8")
    whole = yaml.safe_load(text)
    postgres = whole["services"]["postgres"]
    aliases = postgres["networks"]["transcribe"]["aliases"]
    assert "transcribe-postgres" in aliases

    host = re.search(r"^\s+POSTGRES_HOST:\s*(\S+)", text, re.M).group(1)
    assert host == "transcribe-postgres"
    assert host != "postgres", "a bare service name resolves on any joined network"


def test_the_script_has_the_engine_step():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "cmd_engine()" in text
    assert 'engine) shift && cmd_engine "$@" ;;' in text
    assert "compose.yaml:compose.shared-engine.yaml" in text
