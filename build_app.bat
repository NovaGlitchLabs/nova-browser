@echo off
rem ============================================================
rem  Builds "Nova Browser.exe" from nova_browser.pyw
rem  Put this file, nova_browser.pyw, nova_hub.py, nova_extras.py
rem  and nova.ico in the same folder, then double-click this file.
rem
rem  It builds in its OWN clean Python environment (outside OneDrive),
rem  so big libraries you have installed for other projects (torch,
rem  AI models...) never end up inside the app. The first run takes
rem  a few minutes to set that up; later builds are faster.
rem ============================================================
cd /d "%~dp0"

set "ENV=%LOCALAPPDATA%\NovaBrowserBuildEnv"
set "WORK=%LOCALAPPDATA%\NovaBrowserBuild"
set "PY=%ENV%\Scripts\python.exe"

if not exist "%PY%" (
    echo Making a clean Python environment just for building Nova Browser...
    python -m venv "%ENV%"
    if errorlevel 1 goto failed
)

echo Installing the build tools into it (only slow the first time)...
"%PY%" -m pip install --upgrade --disable-pip-version-check pip >nul
"%PY%" -m pip install --upgrade --disable-pip-version-check pyinstaller pyinstaller-hooks-contrib PyQt6 PyQt6-WebEngine vosk sounddevice
if errorlevel 1 goto failed

echo.
rem A running copy keeps its files locked, so the build can't replace them
tasklist /FI "IMAGENAME eq Nova Browser.exe" 2>nul | find /I "Nova Browser.exe" >nul
if not errorlevel 1 (
    echo Nova Browser is still open. Close it, then press a key to continue...
    pause >nul
)

rem Temporary build files go OUTSIDE OneDrive (OneDrive locks files while it syncs them)
if exist "%WORK%" rmdir /s /q "%WORK%" 2>nul
if exist "build" rmdir /s /q "build" 2>nul
if exist "Nova Browser.spec" del /q "Nova Browser.spec" 2>nul
if exist "dist\Nova Browser" rmdir /s /q "dist\Nova Browser" 2>nul
if exist "dist\Nova Browser" (
    echo.
    echo Couldn't remove the old dist\Nova Browser folder. Close Nova Browser and any File Explorer window
    echo showing that folder, or pause OneDrive syncing for a moment, then run this again.
    goto failed
)

echo Building Nova Browser...
"%PY%" -m PyInstaller --noconfirm --clean --windowed ^
    --workpath "%WORK%\work" --specpath "%WORK%" ^
    --name "Nova Browser" ^
    --icon "%~dp0nova.ico" ^
    --add-data "%~dp0nova.ico;." ^
    --hidden-import nova_hub --hidden-import nova_extras --hidden-import PyQt6.QtWebChannel ^
    --hidden-import PyQt6.QtTextToSpeech --collect-all vosk --collect-all sounddevice ^
    --exclude-module tkinter --exclude-module torch --exclude-module torchvision --exclude-module transformers ^
    --exclude-module scipy --exclude-module pandas --exclude-module matplotlib --exclude-module cv2 ^
    --exclude-module sklearn --exclude-module numba --exclude-module llvmlite --exclude-module librosa ^
    --exclude-module onnxruntime --exclude-module tensorflow --exclude-module IPython ^
    nova_browser.pyw
if errorlevel 1 goto failed

echo.
echo ============================================================
echo  Done! Your app is here:
echo     %~dp0dist\Nova Browser\Nova Browser.exe
echo  Keep the whole "Nova Browser" folder together.
echo  Next: build the installer with nova_browser_installer.iss
echo  (Inno Setup), or right-click the .exe and "Pin to taskbar".
echo ============================================================
pause
exit /b 0

:failed
echo.
echo Something went wrong. Scroll up to see the error, and send me a screenshot.
pause
exit /b 1
