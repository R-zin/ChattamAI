"""First-boot seeding and auto-ingest."""

from types import SimpleNamespace

import pytest

from app import bootstrap


class StubRag:
    def __init__(self, ready=True, size=0, fail=False):
        self.embeddings_ready = ready
        self.index_size = size
        self.fail = fail
        self.ingest_calls = 0

    def ingest(self):
        self.ingest_calls += 1
        if self.fail:
            raise RuntimeError("boom")
        self.index_size = 3
        return {"documents": 1, "chunks": 3, "index_size": 3, "skipped": 0}


@pytest.fixture
def dirs(tmp_path):
    seed = tmp_path / "seed"
    target = tmp_path / "data" / "kbr"
    seed.mkdir()
    (seed / "rules.pdf").write_bytes(b"%PDF")
    (seed / "excerpt.txt").write_text("Rule 5: setback 1.8m")
    (seed / "ignore.bin").write_bytes(b"x")
    return seed, target


# -- seed_kbr_documents ------------------------------------------------------
def test_seeds_supported_files_into_empty_target(dirs):
    seed, target = dirs
    copied = bootstrap.seed_kbr_documents(target, seed)
    assert sorted(copied) == ["excerpt.txt", "rules.pdf"]
    assert (target / "rules.pdf").exists()
    assert not (target / "ignore.bin").exists()


def test_does_not_seed_when_target_has_documents(dirs):
    seed, target = dirs
    target.mkdir(parents=True)
    (target / "mine.txt").write_text("user upload")
    assert bootstrap.seed_kbr_documents(target, seed) == []
    assert not (target / "rules.pdf").exists()


def test_missing_seed_dir_is_a_noop(tmp_path):
    assert bootstrap.seed_kbr_documents(tmp_path / "t", tmp_path / "nope") == []


def test_same_source_and_target_is_a_noop(dirs):
    seed, _ = dirs
    assert bootstrap.seed_kbr_documents(seed, seed) == []


# -- auto_ingest_if_empty ----------------------------------------------------
@pytest.fixture
def enabled(monkeypatch, dirs):
    seed, target = dirs
    monkeypatch.setenv("AUTO_INGEST", "1")
    monkeypatch.setenv("KBR_SEED_DIR", str(seed))
    monkeypatch.setattr(
        bootstrap, "get_settings", lambda: SimpleNamespace(kbr_data_dir=target)
    )
    return target


def test_ingests_and_seeds_when_index_empty(enabled):
    rag = StubRag()
    result = bootstrap.auto_ingest_if_empty(rag)
    assert result["index_size"] == 3
    assert rag.ingest_calls == 1
    assert (enabled / "rules.pdf").exists()


def test_skips_when_index_already_populated(enabled):
    rag = StubRag(size=10)
    assert bootstrap.auto_ingest_if_empty(rag) is None
    assert rag.ingest_calls == 0


def test_skips_when_embeddings_not_ready(enabled):
    rag = StubRag(ready=False)
    assert bootstrap.auto_ingest_if_empty(rag) is None
    assert rag.ingest_calls == 0


def test_skips_when_disabled(enabled, monkeypatch):
    monkeypatch.setenv("AUTO_INGEST", "0")
    rag = StubRag()
    assert bootstrap.auto_ingest_if_empty(rag) is None
    assert rag.ingest_calls == 0


def test_ingest_failure_is_swallowed(enabled):
    rag = StubRag(fail=True)
    assert bootstrap.auto_ingest_if_empty(rag) is None
    assert rag.ingest_calls == 1


def test_background_thread_runs_ingest(enabled):
    rag = StubRag()
    bootstrap.start_background_ingest(rag).join(timeout=5)
    assert rag.ingest_calls == 1
