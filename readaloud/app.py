"""Ponto de entrada: sobe a API local e abre a janela do app (WebView2)."""

import argparse
import logging
import socket
import sys
import threading
import time
import webbrowser

from . import __version__, config

_LOGGER = logging.getLogger("readaloud")


def _setup_logging(debug: bool) -> None:
    # No .exe sem console, stdout/stderr são None: tudo vai para o arquivo de log.
    if sys.stdout is None or sys.stderr is None:
        import os

        devnull = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        sys.stdout = sys.stdout or devnull
        sys.stderr = sys.stderr or devnull
    handlers: list[logging.Handler] = [
        logging.FileHandler(config.log_path(), encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ]
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(port: int):
    import uvicorn

    from .db import Database
    from .langdetect import LanguageDetector
    from .server import create_app
    from .tts import TTSEngine

    app = create_app(
        Database(config.db_path()),
        TTSEngine(config.voices_dir(), config.audio_cache_dir()),
        LanguageDetector(),
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False)
    )
    thread = threading.Thread(target=server.run, name="api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("Não foi possível iniciar o servidor local.")
        time.sleep(0.05)
    return server, thread


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ReadAloud", description="Leitor de textos em voz alta, offline.")
    parser.add_argument("--browser", action="store_true", help="abre no navegador em vez da janela do app")
    parser.add_argument("--port", type=int, default=0, help="porta local (padrão: aleatória)")
    parser.add_argument(
        "--download-voices",
        nargs="*",
        metavar="VOZ",
        help="baixa as vozes padrão (ou as indicadas, ex.: pt_BR-faber-medium) e sai",
    )
    parser.add_argument("--debug", action="store_true", help="logs detalhados")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.download_voices is not None:
        from .voices_download import DEFAULT_VOICES, download_voices

        failed = download_voices(args.download_voices or DEFAULT_VOICES, config.voices_dir())
        return 1 if failed else 0

    _setup_logging(args.debug)
    port = args.port or _free_port()
    url = f"http://127.0.0.1:{port}/"
    _LOGGER.info("ReadAloud %s em %s (dados em %s)", __version__, url, config.data_dir())
    server, thread = _start_server(port)

    if args.browser:
        webbrowser.open(url)
        print(f"ReadAloud rodando em {url} — Ctrl+C para sair.")
        try:
            thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
        return 0

    try:
        import webview
    except ImportError:
        _LOGGER.warning("pywebview não instalado; abrindo no navegador.")
        webbrowser.open(url)
        thread.join()
        return 0

    webview.create_window("ReadAloud", url, width=980, height=760, min_size=(520, 480))
    webview.start()
    server.should_exit = True
    thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
