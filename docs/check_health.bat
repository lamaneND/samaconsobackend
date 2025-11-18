@echo off
REM Script de vérification de santé - SamaConso API
REM Utilisation: check_health.bat

echo ============================================================
echo   SAMA CONSO - Verification de Sante
echo ============================================================
echo.

echo [1/8] Etat des conteneurs...
echo.
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr samaconso
echo.

echo [2/8] Test API Health Check...
curl -s http://localhost:8000 > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [32m✅ API accessible[0m
    curl -s http://localhost:8000
) else (
    echo [31m❌ API non accessible[0m
)
echo.

echo [3/8] Test Drivers ODBC...
docker exec samaconso_api python -c "import pyodbc; drivers = pyodbc.drivers(); print('✅ ODBC OK' if 'ODBC Driver 18 for SQL Server' in drivers else '❌ ODBC manquant')" 2>nul
echo.

echo [4/8] Test Connexion SQL Server SIC...
docker exec samaconso_api python -c "from app.database import get_db_connection_sic; print('✅ SIC OK' if get_db_connection_sic() else '❌ SIC FAIL')" 2>nul
echo.

echo [5/8] Test Connexion SQL Server Postpaid...
docker exec samaconso_api python -c "from app.database import get_db_connection_postpaid; print('✅ Postpaid OK' if get_db_connection_postpaid() else '❌ Postpaid FAIL')" 2>nul
echo.

echo [6/8] Test Firebase...
docker exec samaconso_api python -c "import firebase_admin; print('✅ Firebase OK')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [31m❌ Firebase FAIL[0m
)
echo.

echo [7/8] Test Redis...
docker exec samaconso_redis redis-cli ping 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [32m✅ Redis OK[0m
) else (
    echo [31m❌ Redis FAIL[0m
)
echo.

echo [8/8] Test RabbitMQ...
docker exec samaconso_rabbitmq rabbitmq-diagnostics ping 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [32m✅ RabbitMQ OK[0m
) else (
    echo [31m❌ RabbitMQ FAIL[0m
)
echo.

echo ============================================================
echo   Services Web Disponibles
echo ============================================================
echo.
echo   API Swagger:      http://localhost:8000/docs
echo   Flower (Celery):  http://localhost:5555  (admin/admin)
echo   RabbitMQ:         http://localhost:15672 (guest/guest)
echo   MinIO:            http://localhost:9001  (minioadmin/minioadmin)
echo.

echo ============================================================
echo   Verification terminee
echo ============================================================
echo.
pause
