"""Limpeza de texto (markdown, URLs, HTML) e divisão em trechos para a síntese."""

import re

# Trechos curtos fazem o áudio começar rápido; o player busca o próximo enquanto toca.
TARGET_SEGMENT_CHARS = 280
MAX_SEGMENT_CHARS = 450

_FENCE = re.compile(r"^\s*(```|~~~).*$", re.MULTILINE)
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_REF_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_LINK_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S+.*$", re.MULTILINE)
_URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_SETEXT = re.compile(r"^\s*(=+|-+)\s*$", re.MULTILINE)
_HR = re.compile(r"^\s*([-*_]\s*){3,}$", re.MULTILINE)
_QUOTE = re.compile(r"^\s*>+\s?", re.MULTILINE)
_BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", re.MULTILINE)
_EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1")
_INLINE_CODE = re.compile(r"`([^`]*)`")
_SPACES = re.compile(r"[ \t ]+")

_SENTENCE_END = re.compile(r"(?<=[.!?…;:])\s+")
_SOFT_BREAK = re.compile(r"(?<=[,;:)\]–—-])\s+")


def clean_for_speech(text: str) -> str:
    """Remove marcações que soariam estranhas lidas em voz alta."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _FENCE.sub("", text)
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _REF_LINK.sub(r"\1", text)
    text = _LINK_DEF.sub("", text)
    text = _URL.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _TABLE_SEP.sub("", text)
    text = _HR.sub("", text)
    text = _SETEXT.sub("", text)
    text = _HEADING.sub("", text)
    text = _QUOTE.sub("", text)
    text = _BULLET.sub("", text)
    text = _INLINE_CODE.sub(r"\1", text)
    for _ in range(2):  # ênfase aninhada, ex.: ***texto***
        text = _EMPHASIS.sub(r"\2", text)
    text = text.replace("|", ", ")
    text = _SPACES.sub(" ", text)
    lines = [line.strip(" ,") for line in text.split("\n")]
    return "\n".join(lines).strip()


def split_segments(text: str) -> list[str]:
    """Divide o texto limpo em trechos de até ~MAX_SEGMENT_CHARS, respeitando frases."""
    segments: list[str] = []
    for paragraph in re.split(r"\n\s*\n", clean_for_speech(text)):
        # Linhas soltas (listas, títulos) viram frases separadas.
        lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        sentences: list[str] = []
        for line in lines:
            if line[-1] not in ".!?…;:,":
                line += "."
            sentences.extend(s for s in _SENTENCE_END.split(line) if s.strip())
        segments.extend(_pack(sentences))
    return [s for s in segments if any(ch.isalnum() for ch in s)]


def _pack(sentences: list[str]) -> list[str]:
    """Junta frases curtas e quebra frases longas demais."""
    pieces: list[str] = []
    for sentence in sentences:
        pieces.extend(_split_long(sentence.strip()))

    packed: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 1 + len(piece) > TARGET_SEGMENT_CHARS:
            packed.append(current)
            current = piece
        else:
            current = f"{current} {piece}".strip()
    if current:
        packed.append(current)
    return packed


def _split_long(sentence: str) -> list[str]:
    if len(sentence) <= MAX_SEGMENT_CHARS:
        return [sentence]
    parts: list[str] = []
    current = ""
    for chunk in _SOFT_BREAK.split(sentence):
        while len(chunk) > MAX_SEGMENT_CHARS:  # sem pontuação: corta no último espaço
            cut = chunk.rfind(" ", 0, MAX_SEGMENT_CHARS)
            cut = cut if cut > 0 else MAX_SEGMENT_CHARS
            parts.append(chunk[:cut].strip())
            chunk = chunk[cut:].strip()
        if current and len(current) + 1 + len(chunk) > MAX_SEGMENT_CHARS:
            parts.append(current)
            current = chunk
        else:
            current = f"{current} {chunk}".strip()
    if current:
        parts.append(current)
    return parts


def make_title(text: str, max_chars: int = 80) -> str:
    """Primeira linha não vazia do texto limpo, encurtada."""
    for line in clean_for_speech(text).split("\n"):
        line = line.strip()
        if line:
            return line if len(line) <= max_chars else line[: max_chars - 1].rstrip() + "…"
    return ""
