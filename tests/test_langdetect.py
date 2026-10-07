import pytest

from readaloud.langdetect import LanguageDetector


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Olá, tudo bem? Vamos ler este texto em voz alta.", "pt"),
        ("Hello, how are you? Let's read this text out loud.", "en"),
        ("# Notas\n\n- comprar **pão**\n- ligar para o médico", "pt"),
        ("The quick brown fox jumps over the lazy dog.", "en"),
    ],
)
def test_detect(detector, text, expected):
    assert detector.detect(text, {"pt", "en"}, default="pt") == expected


def test_fallback_to_default(detector):
    assert detector.detect("12345 !!!", {"pt", "en"}, default="en") == "en"
    assert detector.detect("ok", {"pt", "en"}, default="pt") == "pt"
