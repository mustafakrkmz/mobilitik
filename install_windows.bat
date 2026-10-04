@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo           Mobilitik Kurulumu
echo ========================================
echo.

set "PY_EXE="
where py >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%P"
)

if not defined PY_EXE (
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%P in ('python -c "import sys; assert sys.version_info ^>= (3,10); print(sys.executable)" 2^>nul') do set "PY_EXE=%%P"
    )
)

if not defined PY_EXE (
    echo Python 3.10+ bulunamadi.
    if /I "%CI%"=="true" exit /b 1
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

    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 (
            for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%P"
        )
    )
)

if not defined PY_EXE (
    echo Python kuruldu ancak calistirilabilir dosya bulunamadi.
    echo Windows'u yeniden baslatip install_windows.bat dosyasini tekrar calistirin.
    pause
    exit /b 1
)

echo Kullanilan Python: %PY_EXE%
echo [1/4] Sanal ortam hazirlaniyor...
if not exist ".venv\Scripts\python.exe" (
    "%PY_EXE%" -m venv .venv
    if errorlevel 1 goto :error
)

echo [2/4] Python paketleri kuruluyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
if /I "%1"=="--dev" (
    echo Gelistirici paketleri (requirements-dev.txt) kuruluyor...
    ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
    if errorlevel 1 goto :error
)

echo [3/4] Chromium kuruluyor...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :error

echo [4/4] Masaustu kisayolu olusturuluyor...
if /I not "%CI%"=="true" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Mobilitik.lnk'; $s=$w.CreateShortcut($p); $s.TargetPath=(Resolve-Path '.\run_mobilitik.vbs').Path; $s.WorkingDirectory=(Get-Location).Path; $s.Description='Mobilitik Mobilya Sikayet Analizi'; $s.Save()" >nul 2>nul
)

echo.
echo ========================================
echo Kurulum tamamlandi.
echo Masaustundeki Mobilitik kisayolunu acabilirsiniz.
echo ========================================
if /I not "%CI%"=="true" pause
exit /b 0

:error
echo.
echo Kurulum sirasinda hata olustu. Yukaridaki hata mesajini kaydedin.
if /I not "%CI%"=="true" pause
exit /b 1
