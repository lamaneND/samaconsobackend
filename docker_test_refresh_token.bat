@echo off
REM Script Windows pour tester le refresh token avec Docker

echo ============================================
echo   TEST REFRESH TOKEN - SamaConso API
echo ============================================

REM Vérifier si Docker est en cours d'exécution
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker n'est pas en cours d'exécution
    echo    Veuillez démarrer Docker Desktop
    exit /b 1
)

REM Vérifier si les conteneurs existent
docker ps --filter "name=samaconso_api" --format "{{.Names}}" | findstr "samaconso_api" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Le conteneur samaconso_api n'est pas en cours d'exécution
    echo    Démarrage des conteneurs Docker...
    docker-compose up -d
    echo    Attente du démarrage de l'API (30 secondes)...
    timeout /t 30 /nobreak >nul
)

REM Vérifier que l'API répond
echo Vérification de la santé de l'API...
curl -f http://localhost:8000/ >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] API non accessible sur http://localhost:8000
    echo    Vérifiez les logs: docker logs samaconso_api
    exit /b 1
) else (
    echo [OK] API accessible
)

REM Exécuter la migration Alembic
echo.
echo Exécution de la migration Alembic...
docker exec samaconso_api alembic upgrade head
if errorlevel 1 (
    echo [WARNING] Erreur lors de la migration (peut-être déjà appliquée)
) else (
    echo [OK] Migration exécutée avec succès
)

REM Exécuter les tests Python
echo.
echo Exécution des tests Python...
docker exec -it samaconso_api python /app/test_refresh_token.py

echo.
echo ============================================
echo   Tests terminés
echo ============================================
pause

