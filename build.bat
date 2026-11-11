@echo off
REM Builds dist\KeyRepeater.exe (single file, no console window).
REM Requires Python 3.8+ for Windows from python.org (with tcl/tk, the default).
python -m pip install --upgrade pyinstaller || goto :error
python -m PyInstaller --noconfirm --onefile --windowed --name KeyRepeater key_repeater.py || goto :error
echo.
echo Done: dist\KeyRepeater.exe
pause
exit /b 0

:error
echo Build failed.
pause
exit /b 1
