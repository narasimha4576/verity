from pathlib import Path

from app.store import VectorStore


def test_store_path_can_come_from_the_environment(tmp_path, monkeypatch):
    target = tmp_path / "from_env"
    monkeypatch.setenv("CHROMA_PATH", str(target))
    VectorStore()
    assert target.exists()


def test_dockerignore_keeps_secrets_and_data_out_of_the_image():
    lines = Path(".dockerignore").read_text(encoding="utf-8").split()
    for name in (".env", ".venv", "chroma_db", "data"):
        assert name in lines


def test_dockerfile_never_copies_the_env_file():
    text = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY .env" not in text
    assert "COPY . " not in text
