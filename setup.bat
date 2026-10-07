@echo off
setlocal
cd /d "%~dp0"

echo === ReadAloud: preparando ambiente ===
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist .venv (
    echo Criando ambiente virtual .venv ...
    %PY% -m venv .venv || goto :error
)

call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements-dev.txt || goto :error

echo.
echo === Baixando vozes PT-BR e EN (uma vez so, ~360 MB) ===
python -m readaloud --download-voices

echo.
echo Pronto! Use run.bat para abrir o app ou build.bat para gerar o .exe.
pause
exit /b 0

:error
echo.
echo Falhou. Veja a mensagem acima.
pause
exit /b 1
