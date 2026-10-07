"""Entrada usada pelo PyInstaller (o pacote precisa ser importado de forma absoluta)."""

import sys

from readaloud.app import main

if __name__ == "__main__":
    sys.exit(main())
