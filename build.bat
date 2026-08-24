@echo off
echo ============================================
echo   MicBoost - Build Script
echo   Gerando executavel (.exe)
echo ============================================
echo.

:: Verifica se Python esta instalado
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado! Instale Python 3.11+ primeiro.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Cria ambiente virtual
echo [1/4] Criando ambiente virtual...
if not exist "venv" (
    py -m venv venv
)

:: Ativa ambiente virtual
call venv\Scripts\activate.bat

:: Instala dependencias
echo [2/4] Instalando dependencias...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

:: Gera o executavel
echo [3/4] Gerando executavel com PyInstaller...
echo       Isso pode demorar alguns minutos...
echo.

pyinstaller --noconfirm ^
    --onedir ^
    --windowed ^
    --name "MicBoost" ^
    --add-data "audio_engine.py;." ^
    --add-data "system_optimizer.py;." ^
    --hidden-import sounddevice ^
    --hidden-import numpy ^
    --hidden-import customtkinter ^
    --hidden-import _sounddevice_data ^
    --collect-all sounddevice ^
    --collect-all customtkinter ^
    main.py

:: Verifica se o build foi bem sucedido
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao gerar o executavel!
    echo Verifique os erros acima.
    pause
    exit /b 1
)

echo.
echo [4/4] Build concluido!
echo ============================================
echo.
echo   Executavel gerado em:
echo   dist\MicBoost\MicBoost.exe
echo.
echo   Para distribuir, copie a pasta inteira:
echo   dist\MicBoost\
echo.
echo ============================================

:: Desativa ambiente virtual
deactivate

pause
