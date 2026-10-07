"""API HTTP local (FastAPI) usada pela interface."""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .db import Database
from .langdetect import BASE_LANGUAGES, LanguageDetector
from .textproc import make_title, split_segments
from .tts import NoVoicesError, TTSEngine

_LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_SETTINGS = {
    "speed": 1.0,             # velocidade de reprodução (0.5 a 2.0)
    "default_lang": "pt",     # usado quando a detecção não tem confiança
    "default_voices": {},     # {"pt": "pt_BR-faber-medium", "en": "en_US-lessac-medium"}
}


class NewCard(BaseModel):
    text: str
    source: Optional[str] = Field(default=None, max_length=260)


class CardUpdate(BaseModel):
    voice: Optional[str] = None


class SettingsUpdate(BaseModel):
    speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    default_lang: Optional[str] = Field(default=None, max_length=8)
    default_voices: Optional[dict[str, str]] = None


def create_app(db: Database, tts: TTSEngine, detector: LanguageDetector) -> FastAPI:
    app = FastAPI(title="ReadAloud", version=__version__, docs_url=None, redoc_url=None)

    def settings() -> dict:
        return {**DEFAULT_SETTINGS, **db.get_settings()}

    def card_payload(card: dict) -> dict:
        try:
            voice = tts.resolve_voice(card["voice"], card["lang"], settings()["default_voices"])
            voice_id = voice.id
        except NoVoicesError:
            voice_id = None
        return {
            **card,
            "title": make_title(card["text"]),
            "effective_voice": voice_id,
        }

    def require_card(card_id: int) -> dict:
        card = db.get_card(card_id)
        if not card:
            raise HTTPException(404, "Card não encontrado.")
        return card

    # Remove áudios em cache de cards que não existem mais.
    existing = {str(card["id"]) for card in db.list_cards()}
    for entry in tts.cache_dir.iterdir():
        if entry.is_dir() and entry.name.isdigit() and entry.name not in existing:
            tts.clear_cache(int(entry.name))

    # ----------------------------------------------------------------- cards

    @app.get("/api/cards")
    def list_cards():
        return [card_payload(card) for card in db.list_cards()]

    @app.post("/api/cards", status_code=201)
    def add_card(body: NewCard):
        text = body.text.replace("\x00", "").strip()
        if not text:
            raise HTTPException(400, "Texto vazio.")
        if not split_segments(text):
            raise HTTPException(400, "O texto não tem nada que possa ser lido.")
        current = settings()
        lang = detector.detect(
            text,
            candidates=set(BASE_LANGUAGES) | tts.languages(),
            default=current["default_lang"],
        )
        card = db.add_card(text, lang, body.source)
        _LOGGER.info("Card %s criado (%s, %d caracteres)", card["id"], lang, len(text))
        return card_payload(card)

    @app.patch("/api/cards/{card_id}")
    def update_card(card_id: int, body: CardUpdate):
        require_card(card_id)
        if body.voice == "":  # volta para a voz automática do idioma
            db.update_card(card_id, voice=None)
        elif body.voice is not None:
            voice = next((v for v in tts.voices() if v.id == body.voice), None)
            if voice is None:
                raise HTTPException(400, "Voz desconhecida.")
            # Escolher uma voz de outro idioma também corrige o idioma do card.
            db.update_card(card_id, voice=voice.id, lang=voice.lang)
        return card_payload(db.get_card(card_id))

    @app.delete("/api/cards/{card_id}", status_code=204)
    def delete_card(card_id: int):
        if not db.delete_card(card_id):
            raise HTTPException(404, "Card não encontrado.")
        tts.clear_cache(card_id)
        return Response(status_code=204)

    @app.delete("/api/cards", status_code=204)
    def delete_all_cards():
        db.delete_all_cards()
        tts.clear_cache()
        return Response(status_code=204)

    # ---------------------------------------------------------------- áudio

    @app.get("/api/cards/{card_id}/segments")
    def card_segments(card_id: int):
        card = require_card(card_id)
        return {"segments": split_segments(card["text"])}

    @app.get("/api/cards/{card_id}/audio/{index}")
    def card_audio(card_id: int, index: int):
        card = require_card(card_id)
        segments = split_segments(card["text"])
        if not 0 <= index < len(segments):
            raise HTTPException(404, "Trecho inexistente.")
        try:
            voice = tts.resolve_voice(card["voice"], card["lang"], settings()["default_voices"])
        except NoVoicesError as err:
            raise HTTPException(409, f"{err} Veja o README para baixar as vozes.") from err
        try:
            data = tts.synthesize(card_id, index, segments[index], voice)
        except Exception as err:  # noqa: BLE001 - erro do Piper/onnxruntime vai para a UI
            _LOGGER.exception("Falha ao sintetizar card %s trecho %s", card_id, index)
            raise HTTPException(500, f"Falha ao gerar o áudio: {err}") from err
        return Response(data, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    # ------------------------------------------------------- vozes/ajustes

    @app.get("/api/voices")
    def list_voices():
        return [v.to_dict() for v in tts.voices()]

    @app.post("/api/voices/refresh")
    def refresh_voices():
        tts.refresh_voices()
        return [v.to_dict() for v in tts.voices()]

    @app.post("/api/voices/open-folder", status_code=204)
    def open_voices_folder():
        folder = str(tts.voices_dir)
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 - abre o Explorer na pasta de vozes
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return Response(status_code=204)

    @app.get("/api/settings")
    def get_settings():
        return {**settings(), "voices_dir": str(tts.voices_dir), "version": __version__}

    @app.put("/api/settings")
    def put_settings(body: SettingsUpdate):
        db.set_settings(body.model_dump(exclude_none=True))
        return get_settings()

    # ------------------------------------------------------------ interface

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
