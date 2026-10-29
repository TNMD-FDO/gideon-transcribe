"""Phase 11 stage 0: the two OpenAPI documents under docs/api parse and keep
their shape, so a document that no longer reads fails CI before anybody
builds on it. The reason classes in the pipeline's document are the app's
own, and every path's answers name a schema that exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from core.jobs import Reason

API = Path(__file__).resolve().parent.parent.parent / "docs" / "api"


def _load(name: str) -> dict:
    return yaml.safe_load((API / name).read_text(encoding="utf-8"))


def _refs(node, found: set) -> set:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                found.add(value)
            else:
                _refs(value, found)
    elif isinstance(node, list):
        for one in node:
            _refs(one, found)
    return found


@pytest.mark.parametrize("name", ["pipeline-v1.yaml", "product-v1.yaml"])
def test_the_document_parses_and_every_reference_resolves(name):
    doc = _load(name)
    assert doc["openapi"].startswith("3.1")
    assert doc["info"]["title"] and doc["info"]["version"]
    assert doc["paths"], name
    components = doc["components"]
    for ref in _refs(doc, set()):
        assert ref.startswith("#/components/"), ref
        _, _, kind, key = ref.split("/")
        assert key in components[kind], ref
    # Every operation has a summary and at least one response.
    for path, item in doc["paths"].items():
        for method, operation in item.items():
            if method in ("parameters", "servers"):
                continue
            assert operation.get("summary"), (path, method)
            assert operation.get("responses"), (path, method)


def test_the_pipeline_documents_reason_classes_are_the_apps_own():
    doc = _load("pipeline-v1.yaml")
    listed = set(doc["components"]["schemas"]["ReasonClass"]["enum"])
    ours = {
        value
        for key, value in vars(Reason).items()
        if key.isupper() and isinstance(value, str)
    }
    assert listed == ours
    states = set(doc["components"]["schemas"]["State"]["properties"]["state"]["enum"])
    assert {"preparing", "queued", "running", "done", "held", "failed"} <= states
    result = doc["components"]["schemas"]["Result"]
    assert result["properties"]["result_version"]["const"] == 1
    for field in ("audio", "language", "speakers", "segments", "provenance"):
        assert field in result["required"]


def test_the_product_document_covers_the_first_two_sections():
    doc = _load("product-v1.yaml")
    paths = set(doc["paths"])
    assert {"/sign-in", "/sign-out", "/me"} <= paths
    assert {"/cases", "/cases/{case_id}", "/cases/{case_id}/recordings"} <= paths
    assert {
        "/recordings/{recording_id}",
        "/recordings/{recording_id}/again",
        "/uploads",
    } <= paths
    # The sign-in is the cookie on the app's origin, never a token.
    assert doc["components"]["securitySchemes"]["session"]["in"] == "cookie"
    assert "bearer" not in doc["components"]["securitySchemes"]
