@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo           Mobilitik Kurulumu
echo ========================================
echo.

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys; print(sys.version)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py -3.12"
)

if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo Python 3.10+ bulunamadi.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Lutfen Python 3.12 kurun ve bu dosyayi yeniden calistirin.
        echo https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    echo Python 3.12 winget ile kurulacak.
    winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo Python kurulumu basarisiz oldu.
        pause
        exit /b 1
    )
    set "PY_CMD=py -3.12"
)

echo [1/4] Sanal ortam hazirlaniyor...
if not exist ".venv\Scripts\python.exe" (
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

echo [2/4] Python paketleri kuruluyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/4] Chromium kuruluyor...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :error

echo [4/4] Masaustu kisayolu olusturuluyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Mobilitik.lnk'; $s=$w.CreateShortcut($p); $s.TargetPath=(Resolve-Path '.\run_mobilitik.vbs').Path; $s.WorkingDirectory=(Get-Location).Path; $s.Description='Mobilitik Mobilya Sikayet Analizi'; $s.Save()" >nul 2>nul

echo.
echo ========================================
echo Kurulum tamamlandi.
echo Masaustundeki Mobilitik kisayolunu acabilirsiniz.
echo ========================================
pause
exit /b 0

:error
echo.
echo Kurulum sirasinda hata olustu. Yukaridaki hata mesajini kaydedin.
pause
exit /b 1
