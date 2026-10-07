"""Detecção automática de idioma, offline (py3langid)."""

import threading
from typing import Iterable

from py3langid.langid import MODEL_DIR, MODEL_FILE, LanguageIdentifier

from .textproc import clean_for_speech

# Idiomas iniciais do app. Idiomas de vozes instaladas são adicionados automaticamente.
BASE_LANGUAGES = ("pt", "en")
MIN_CONFIDENCE = 0.6


class LanguageDetector:
    def __init__(self) -> None:
        self._identifier = LanguageIdentifier.from_modelpath(
            MODEL_DIR / MODEL_FILE, norm_probs=True
        )
        self._lock = threading.Lock()
        self._known = set(self._identifier.nb_classes)

    def detect(self, text: str, candidates: Iterable[str], default: str) -> str:
        """Retorna o código ISO 639-1 (ex.: 'pt', 'en') mais provável entre os candidatos."""
        langs = sorted({c for c in candidates if c in self._known})
        sample = clean_for_speech(text)[:5000]
        if not langs or not any(ch.isalpha() for ch in sample):
            return default
        if len(langs) == 1:
            return langs[0]
        with self._lock:  # set_languages altera o estado do identificador
            self._identifier.set_languages(langs)
            lang, confidence = self._identifier.classify(sample)
        return lang if confidence >= MIN_CONFIDENCE else default
