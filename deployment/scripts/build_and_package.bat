@echo off
setlocal EnableDelayedExpansion
title Build et packaging SamaConso

echo.
echo =====================================================
echo   Build et packaging SamaConso pour deploiement
echo   Images exportees dans le dossier deploy\
echo =====================================================
echo.

:: ─── Verification de l'environnement ─────────────────────────────────────────

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker n'est pas demarree ou accessible.
    echo         Lancez Docker Desktop puis reessayez.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas dans le PATH.
    pause
    exit /b 1
)

:: ─── Verification du fichier Firebase ────────────────────────────────────────

if not exist "app\samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json" (
    echo [ERREUR] Fichier Firebase manquant :
    echo         app\samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
    echo         Ce fichier est necessaire pour le build.
    pause
    exit /b 1
)

:: ─── Preparation du dossier deploy ───────────────────────────────────────────

if not exist deploy mkdir deploy

echo [1/6] Build de l'image Docker samaconso_api...
echo       (inclut : ODBC SQL Server, Firebase, dependances Python)
echo.
docker build -t samaconso_api:latest .
if errorlevel 1 (
    echo.
    echo [ERREUR] Build Docker echoue. Verifiez les logs ci-dessus.
    pause
    exit /b 1
)
echo.
echo       Image samaconso_api:latest construite avec succes.
echo.

:: ─── Recuperer Redis 7-alpine ────────────────────────────────────────────────

echo [2/6] Recuperation de l'image Redis 7-alpine...
docker image inspect redis:7-alpine >nul 2>&1
if errorlevel 1 (
    echo       Image absente localement - pull depuis Docker Hub...
    docker pull redis:7-alpine
    if errorlevel 1 (
        echo [ERREUR] Impossible de puller redis:7-alpine
        pause
        exit /b 1
    )
) else (
    echo       Image redis:7-alpine deja presente localement.
)
echo.

:: ─── Export des images Docker ─────────────────────────────────────────────────

echo [3/6] Export de l'image samaconso_api (peut prendre quelques minutes)...
docker save samaconso_api:latest -o deploy\samaconso_api.tar
if errorlevel 1 (
    echo [ERREUR] Export de samaconso_api.tar echoue.
    pause
    exit /b 1
)
echo       samaconso_api.tar cree.
echo.

echo [4/6] Export de l'image redis:7-alpine...
docker save redis:7-alpine -o deploy\redis_7_alpine.tar
if errorlevel 1 (
    echo [ERREUR] Export de redis_7_alpine.tar echoue.
    pause
    exit /b 1
)
echo       redis_7_alpine.tar cree.
echo.

:: ─── Copie des scripts de deploiement ────────────────────────────────────────

echo [5/6] Copie des scripts de deploiement...
copy /Y deploy_srv1.sh deploy\ >nul
copy /Y deploy_srv2.sh deploy\ >nul
copy /Y deploy\start_flower.sh deploy\ >nul 2>&1 || echo       (start_flower.sh deja present dans deploy\)
echo       deploy_srv1.sh, deploy_srv2.sh et start_flower.sh copies.
echo.

:: ─── Recapitulatif ────────────────────────────────────────────────────────────

echo [6/6] Package pret. Contenu du dossier deploy\ :
echo.
dir deploy\ /B
echo.

:: Tailles
for %%F in (deploy\samaconso_api.tar) do set SIZE_API=%%~zF
for %%F in (deploy\redis_7_alpine.tar) do set SIZE_REDIS=%%~zF
set /a SIZE_API_MB=!SIZE_API! / 1048576
set /a SIZE_REDIS_MB=!SIZE_REDIS! / 1048576
echo   samaconso_api.tar  : ~!SIZE_API_MB! MB
echo   redis_7_alpine.tar : ~!SIZE_REDIS_MB! MB
echo.

echo =====================================================
echo   ETAPE SUIVANTE — servir les fichiers aux serveurs
echo =====================================================
echo.
echo   cd deploy
echo   python -m http.server 8888
echo.
echo   Puis sur chaque serveur (en SSH) :
echo.
echo   Sur SRV-MOBAPP1 (10.101.1.210) :
echo     wget http://VOTRE_IP:8888/deploy_srv1.sh
echo     chmod +x deploy_srv1.sh
echo     sudo ./deploy_srv1.sh VOTRE_IP
echo.
echo   Sur SRV-MOBAPP2 (10.101.1.211) :
echo     wget http://VOTRE_IP:8888/deploy_srv2.sh
echo     chmod +x deploy_srv2.sh
echo     sudo ./deploy_srv2.sh VOTRE_IP
echo.
pause
