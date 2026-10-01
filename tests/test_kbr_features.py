"""Tests for KBR document management, rule search, and model switching (offline)."""

from __future__ import annotations

import io


def test_list_kbr_documents(app_client):
    resp = app_client.get("/api/kbr/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert isinstance(docs, list)


def test_search_rules(app_client):
    # app_client preloads rules into the vector store
    resp = app_client.get("/api/rules/search?q=setback&limit=5")
    assert resp.status_code == 200
    results = resp.json()
    assert isinstance(results, list)
    if results:
        r = results[0]
        assert "rule_id" in r
        assert "score" in r
        assert "excerpt" in r


def test_upload_kbr_document(app_client):
    from pathlib import Path

    dest = Path("data/kbr/rule_sample.txt")
    try:
        file_content = b"Rule 99: All staircases shall be constructed with non-combustible materials."
        files = {"file": ("rule_sample.txt", io.BytesIO(file_content), "text/plain")}
        resp = app_client.post("/api/kbr/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "rule_sample.txt"
        assert body["status"] == "uploaded"
    finally:
        dest.unlink(missing_ok=True)


def test_set_model(app_client):
    resp = app_client.post(
        "/api/setmodel", json={"model_provider": "anthropic/claude-3-7-sonnet"}
    )
    assert resp.status_code == 200
    assert "Active model set" in resp.json()["status"]
