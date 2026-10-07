import json

import pytest
from fastapi.testclient import TestClient

from readaloud.db import Database
from readaloud.langdetect import LanguageDetector
from readaloud.server import create_app
from readaloud.tts import TTSEngine


class FakeTTS(TTSEngine):
    """Não carrega o Piper: devolve um WAV mínimo e registra as chamadas."""

    calls: list

    def synthesize(self, card_id, index, text, voice):
        self.calls.append((card_id, index, text, voice.id))
        path = self.cache_dir / str(card_id) / f"{voice.id}-{index}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return b"RIFF"


def make_voice(folder, name, code):
    (folder / f"{name}.onnx").write_bytes(b"")
    (folder / f"{name}.onnx.json").write_text(
        json.dumps({"language": {"code": code}, "dataset": name.split("-")[1], "audio": {"quality": "medium"}})
    )


@pytest.fixture
def env(tmp_path):
    voices = tmp_path / "voices"
    voices.mkdir()
    make_voice(voices, "pt_BR-faber-medium", "pt_BR")
    make_voice(voices, "pt_BR-cadu-medium", "pt_BR")
    make_voice(voices, "en_US-lessac-medium", "en_US")
    tts = FakeTTS(voices, tmp_path / "cache")
    tts.calls = []
    (tmp_path / "cache").mkdir(exist_ok=True)
    app = create_app(Database(tmp_path / "db.sqlite"), tts, LanguageDetector())
    return TestClient(app), tts


def test_card_lifecycle(env):
    client, tts = env
    assert client.get("/").status_code == 200
    assert client.get("/api/cards").json() == []

    pt = client.post("/api/cards", json={"text": "Bom dia, este é um texto em português."}).json()
    en = client.post("/api/cards", json={"text": "Good morning, this is English text.", "source": "a.txt"}).json()
    assert pt["lang"] == "pt" and pt["effective_voice"].startswith("pt_BR")
    assert en["lang"] == "en" and en["effective_voice"] == "en_US-lessac-medium"
    assert [c["id"] for c in client.get("/api/cards").json()] == [en["id"], pt["id"]]

    segments = client.get(f"/api/cards/{pt['id']}/segments").json()["segments"]
    assert segments
    res = client.get(f"/api/cards/{pt['id']}/audio/0")
    assert res.status_code == 200 and res.headers["content-type"] == "audio/wav"
    assert client.get(f"/api/cards/{pt['id']}/audio/99").status_code == 404

    # voz por card: escolher voz inglesa muda o idioma
    updated = client.patch(f"/api/cards/{pt['id']}", json={"voice": "en_US-lessac-medium"}).json()
    assert updated["voice"] == "en_US-lessac-medium" and updated["lang"] == "en"
    client.get(f"/api/cards/{pt['id']}/audio/0")
    assert tts.calls[-1][3] == "en_US-lessac-medium"
    reset = client.patch(f"/api/cards/{pt['id']}", json={"voice": ""}).json()
    assert reset["voice"] is None
    assert client.patch(f"/api/cards/{pt['id']}", json={"voice": "nope"}).status_code == 400

    assert (tts.cache_dir / str(pt["id"])).exists()
    assert client.delete(f"/api/cards/{pt['id']}").status_code == 204
    assert not (tts.cache_dir / str(pt["id"])).exists()
    assert client.delete(f"/api/cards/{pt['id']}").status_code == 404

    assert client.delete("/api/cards").status_code == 204
    assert client.get("/api/cards").json() == []


def test_rejects_empty_text(env):
    client, _ = env
    assert client.post("/api/cards", json={"text": "   "}).status_code == 400
    assert client.post("/api/cards", json={"text": "---\n***"}).status_code == 400


def test_settings_and_default_voice(env):
    client, _ = env
    assert client.get("/api/settings").json()["speed"] == 1.0
    client.put("/api/settings", json={"speed": 1.5, "default_voices": {"pt": "pt_BR-faber-medium"}})
    assert client.get("/api/settings").json()["speed"] == 1.5
    assert client.put("/api/settings", json={"speed": 5}).status_code == 422
    card = client.post("/api/cards", json={"text": "Uma frase qualquer em português."}).json()
    assert card["effective_voice"] == "pt_BR-faber-medium"


def test_no_voices(tmp_path):
    (tmp_path / "voices").mkdir()
    tts = TTSEngine(tmp_path / "voices", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    client = TestClient(create_app(Database(tmp_path / "db.sqlite"), tts, LanguageDetector()))
    card = client.post("/api/cards", json={"text": "Olá mundo, tudo bem com você?"}).json()
    assert card["effective_voice"] is None
    res = client.get(f"/api/cards/{card['id']}/audio/0")
    assert res.status_code == 409 and "voz" in res.json()["detail"].lower()
