@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
    echo Rode setup.bat primeiro.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

echo === Gerando dist\ReadAloud\ReadAloud.exe ===
pyinstaller --noconfirm --clean ReadAloud.spec || goto :error

echo.
echo Pronto: dist\ReadAloud\ReadAloud.exe
echo (copie a pasta dist\ReadAloud inteira para onde quiser; as vozes e os
echo  cards ficam em %%LOCALAPPDATA%%\ReadAloud e nao fazem parte do .exe)
pause
exit /b 0

:error
echo.
echo O build falhou. Veja a mensagem acima.
pause
exit /b 1
