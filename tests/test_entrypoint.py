"""entrypoint.sh: real writability probe and /tmp fallback."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = ROOT / "entrypoint.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or os.geteuid() == 0,
    reason="needs bash and a non-root user (root ignores directory permissions)",
)


@pytest.fixture
def stub_bin(tmp_path):
    """Fake alembic/uvicorn that record what the entrypoint exported."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("alembic", "uvicorn"):
        script = bin_dir / name
        script.write_text(
            "#!/bin/sh\n"
            f'echo "{name} KBR=$KBR_DATA_DIR INDEX=$INDEX_DIR DB=$DATABASE_URL"\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def run_entrypoint(tmp_path, stub_bin, env_extra):
    env = {
        "PATH": f"{stub_bin}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        **env_extra,
    }
    # Run from a dir without alembic.ini so only uvicorn's stub runs, plus a copy
    # with alembic.ini to confirm migrations run exactly once.
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / "alembic.ini").write_text("")
    return subprocess.run(
        ["bash", str(ENTRYPOINT)],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_writable_dirs_are_used_as_is(tmp_path, stub_bin):
    data = tmp_path / "data"
    result = run_entrypoint(
        tmp_path,
        stub_bin,
        {
            "KBR_DATA_DIR": str(data / "kbr"),
            "INDEX_DIR": str(data / "index"),
            "DATABASE_URL": f"sqlite:///{data}/app.db",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "Falling back" not in result.stdout
    assert f"KBR={data}/kbr" in result.stdout
    assert result.stdout.count("alembic KBR=") == 1
    assert not list(data.rglob(".write-probe*")), "probe file must be cleaned up"


def test_readonly_existing_dir_triggers_tmp_fallback(tmp_path, stub_bin):
    """mkdir -p succeeds on an existing read-only dir; the probe must not."""
    data = tmp_path / "data"
    (data / "kbr").mkdir(parents=True)
    (data / "index").mkdir()
    data.chmod(0o555)
    (data / "kbr").chmod(0o555)
    (data / "index").chmod(0o555)
    try:
        result = run_entrypoint(
            tmp_path,
            stub_bin,
            {
                "KBR_DATA_DIR": str(data / "kbr"),
                "INDEX_DIR": str(data / "index"),
                "DATABASE_URL": f"sqlite:///{data}/app.db",
            },
        )
    finally:
        for p in (data / "kbr", data / "index", data):
            p.chmod(0o755)
    assert result.returncode == 0, result.stderr
    assert "Falling back to /tmp/chattamai" in result.stdout
    assert "uvicorn KBR=/tmp/chattamai/kbr INDEX=/tmp/chattamai/index" in result.stdout
    assert "DB=sqlite:////tmp/chattamai/chattamai.db" in result.stdout


def test_non_sqlite_database_url_is_left_alone(tmp_path, stub_bin):
    data = tmp_path / "data"
    result = run_entrypoint(
        tmp_path,
        stub_bin,
        {
            "KBR_DATA_DIR": str(data / "kbr"),
            "INDEX_DIR": str(data / "index"),
            "DATABASE_URL": "postgresql://u:p@db/app",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "DB=postgresql://u:p@db/app" in result.stdout
