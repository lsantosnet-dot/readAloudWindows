# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller --noconfirm --clean ReadAloud.spec  (ou build.bat)
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = [("readaloud/static", "readaloud/static")]
datas += collect_data_files("piper")       # espeak-ng-data (fonemas)
datas += collect_data_files("py3langid")   # modelo de detecção de idioma
binaries = collect_dynamic_libs("piper")   # espeakbridge
binaries += collect_dynamic_libs("onnxruntime")

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=["piper.espeakbridge", "piper.download_voices"],
    excludes=["piper.train", "torch", "tkinter", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ReadAloud",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ReadAloud", upx=False)
