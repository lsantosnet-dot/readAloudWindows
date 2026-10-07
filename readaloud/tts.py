"""Vozes Piper instaladas localmente e síntese com cache em disco."""

import io
import json
import logging
import re
import shutil
import threading
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Ex.: pt_BR-faber-medium, en_US-lessac-high, en-us-lessac-low (formato antigo)
_VOICE_NAME = re.compile(
    r"^(?P<lang>[a-z]{2,3})[_-](?P<region>[A-Za-z]{2})-(?P<name>.+?)(-(?P<quality>x_low|low|medium|high))?$"
)


class NoVoicesError(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceInfo:
    id: str          # nome do arquivo sem .onnx
    lang: str        # 'pt', 'en'
    locale: str      # 'pt_BR', 'en_US'
    name: str        # 'Faber'
    quality: str     # 'medium'

    @property
    def label(self) -> str:
        quality = f" ({self.quality})" if self.quality else ""
        return f"{self.name}{quality} · {self.locale.replace('_', '-')}"

    def to_dict(self) -> dict:
        return {**asdict(self), "label": self.label}


def _read_voice_info(model_path: Path) -> Optional[VoiceInfo]:
    config_path = model_path.with_name(model_path.name + ".json")
    if not config_path.exists():
        _LOGGER.warning("Voz sem arquivo .onnx.json ignorada: %s", model_path)
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _LOGGER.exception("Configuração de voz inválida: %s", config_path)
        return None

    stem = model_path.stem
    match = _VOICE_NAME.match(stem)
    locale = (config.get("language") or {}).get("code") or ""
    if not locale and match:
        locale = f"{match['lang']}_{match['region'].upper()}"
    if not locale:  # formato antigo: só o espeak sabe o idioma
        espeak_voice = (config.get("espeak") or {}).get("voice", "")
        locale = espeak_voice.replace("-", "_")
    if not locale:
        _LOGGER.warning("Não foi possível identificar o idioma da voz: %s", model_path)
        return None

    name = (config.get("dataset") or (match["name"] if match else stem)).replace("_", " ")
    quality = (config.get("audio") or {}).get("quality") or (match["quality"] if match else "") or ""
    return VoiceInfo(
        id=stem,
        lang=locale.split("_")[0].lower(),
        locale=locale,
        name=name.title(),
        quality=quality,
    )


class TTSEngine:
    """Carrega vozes sob demanda e gera WAVs, guardando-os em cache por card."""

    def __init__(self, voices_dir: Path, cache_dir: Path):
        self.voices_dir = voices_dir
        self.cache_dir = cache_dir
        self._voices: dict[str, VoiceInfo] = {}
        self._loaded: dict[str, object] = {}
        self._lock = threading.Lock()
        self._voice_locks: dict[str, threading.Lock] = {}
        self.refresh_voices()

    # ---------------------------------------------------------------- vozes

    def refresh_voices(self) -> list[VoiceInfo]:
        voices = {}
        for model_path in sorted(self.voices_dir.glob("*.onnx")):
            info = _read_voice_info(model_path)
            if info:
                voices[info.id] = info
        with self._lock:
            self._voices = voices
            self._loaded = {k: v for k, v in self._loaded.items() if k in voices}
        _LOGGER.info("Vozes encontradas: %s", ", ".join(voices) or "nenhuma")
        return list(voices.values())

    def voices(self) -> list[VoiceInfo]:
        return sorted(self._voices.values(), key=lambda v: (v.lang, v.locale, v.name))

    def languages(self) -> set[str]:
        return {v.lang for v in self._voices.values()}

    def resolve_voice(self, voice_id: Optional[str], lang: str, defaults: dict) -> VoiceInfo:
        """Voz escolhida no card → padrão do idioma → qualquer voz do idioma → qualquer voz."""
        voices = self._voices
        if not voices:
            raise NoVoicesError("Nenhuma voz Piper instalada.")
        for candidate in (voice_id, defaults.get(lang)):
            if candidate and candidate in voices:
                return voices[candidate]
        same_lang = [v for v in self.voices() if v.lang == lang]
        return same_lang[0] if same_lang else self.voices()[0]

    def _get_model(self, voice_id: str):
        with self._lock:
            model = self._loaded.get(voice_id)
            if model is not None:
                return model, self._voice_locks[voice_id]
        from piper import PiperVoice  # import tardio: onnxruntime demora a carregar

        model_path = self.voices_dir / f"{voice_id}.onnx"
        _LOGGER.info("Carregando voz %s", voice_id)
        model = PiperVoice.load(model_path)
        with self._lock:
            self._loaded.setdefault(voice_id, model)
            lock = self._voice_locks.setdefault(voice_id, threading.Lock())
            return self._loaded[voice_id], lock

    # --------------------------------------------------------------- síntese

    def synthesize(self, card_id: int, index: int, text: str, voice: VoiceInfo) -> bytes:
        cache_file = self.cache_dir / str(card_id) / f"{voice.id}-{index}.wav"
        if cache_file.exists():
            return cache_file.read_bytes()

        model, lock = self._get_model(voice.id)
        buffer = io.BytesIO()
        with lock, wave.open(buffer, "wb") as wav_file:
            model.synthesize_wav(text, wav_file)
        data = buffer.getvalue()

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(cache_file)
        return data

    def clear_cache(self, card_id: Optional[int] = None) -> None:
        target = self.cache_dir / str(card_id) if card_id is not None else self.cache_dir
        shutil.rmtree(target, ignore_errors=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
