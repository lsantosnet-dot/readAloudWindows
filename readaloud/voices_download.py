"""Baixa vozes Piper (uma única vez, com internet). Depois o app roda 100% offline."""

import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Vozes padrão: PT-BR e inglês americano, qualidade "medium" (~60 MB cada).
DEFAULT_VOICES = [
    "pt_BR-faber-medium",
    "pt_BR-cadu-medium",
    "pt_BR-jeff-medium",
    "en_US-lessac-medium",
    "en_US-amy-medium",
    "en_US-ryan-medium",
]


def download_voices(names: list[str], target: Path) -> list[str]:
    """Baixa as vozes indicadas para `target`. Retorna as que falharam."""
    from piper.download_voices import download_voice

    target.mkdir(parents=True, exist_ok=True)
    failed = []
    for name in names:
        print(f"Baixando voz {name} ...", flush=True)
        try:
            download_voice(name, target)
        except Exception as err:  # noqa: BLE001 - segue para a próxima voz
            failed.append(name)
            print(f"  falhou: {err}", flush=True)
            for leftover in target.glob(f"{name}.onnx*"):
                if leftover.stat().st_size == 0:
                    leftover.unlink()
    print(f"\nVozes em: {target}")
    if failed:
        print("Não foi possível baixar: " + ", ".join(failed))
    return failed
