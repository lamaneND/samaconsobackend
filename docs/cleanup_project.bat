@echo off
REM Script de nettoyage du projet SamaConso
REM Supprime les fichiers obsolètes et garde uniquement les essentiels
REM IMPORTANT: Ne supprime PAS les fichiers .pfx

echo ============================================================
echo   NETTOYAGE DU PROJET SAMACONSO
echo ============================================================
echo.
echo Ce script va supprimer les fichiers obsoletes...
echo Les fichiers .pfx seront PRESERVES
echo.
pause

cd /d "%~dp0"

echo.
echo [1/7] Suppression de la documentation obsolete/dupliquee...
del /F /Q "BEFORE_AFTER_COMPARISON.md" 2>nul
del /F /Q "CHECKLIST_VALIDATION.md" 2>nul
del /F /Q "COMPARAISON_AVANT_APRES_OPTIMISATION.md" 2>nul
del /F /Q "DEPLOYMENT_READY.md" 2>nul
del /F /Q "DOCKER_README.md" 2>nul
del /F /Q "GUIDE_DEPLOYMENT_DOCKER.md" 2>nul
del /F /Q "GUIDE_PROBLEME_SSL.md" 2>nul
del /F /Q "INSTRUCTIONS_FINALES.txt" 2>nul
del /F /Q "PRODUCTION_GUIDE.md" 2>nul
del /F /Q "QUICK_START.md" 2>nul
del /F /Q "QUICKSTART_DOCKER_FIX.md" 2>nul
del /F /Q "README_DOCKER_FIX.md" 2>nul
del /F /Q "RESUME_FINAL.txt" 2>nul
del /F /Q "SUCCES_DEPLOIEMENT.md" 2>nul
echo    ✓ Documentation obsolete supprimee

echo.
echo [2/7] Suppression de la documentation de features non utilisees...
del /F /Q "WEBSOCKET_NOTIFICATIONS_GUIDE.md" 2>nul
del /F /Q "MONITORING_DECISION_GUIDE.md" 2>nul
echo    ✓ Documentation features non utilisees supprimee

echo.
echo [3/7] Suppression de la documentation technique obsolete...
del /F /Q "CACHE_GUIDE.md" 2>nul
del /F /Q "CACHE_STRATEGY.md" 2>nul
del /F /Q "CELERY_RABBITMQ_GUIDE.md" 2>nul
del /F /Q "compare_logging_systems.md" 2>nul
del /F /Q "DEDUPLICATION_REPORT.md" 2>nul
del /F /Q "GLOBAL_NOTIFICATIONS_OPTIMIZATION.md" 2>nul
del /F /Q "GUIDE_TESTS_OPTIMISATIONS.md" 2>nul
del /F /Q "INTEGRATION_MINIO_COMPLETE.md" 2>nul
del /F /Q "LOGGING_GUIDE.md" 2>nul
del /F /Q "LOGGING_IMPACT_CONCLUSION.md" 2>nul
del /F /Q "LOGGING_IMPLEMENTATION_SUMMARY.md" 2>nul
del /F /Q "LOGGING_INTEGRATION_PLAN.md" 2>nul
del /F /Q "LOGGING_INTEGRATION_TEMPLATES.md" 2>nul
del /F /Q "LOGGING_OPTIMIZATION_EXAMPLE.md" 2>nul
del /F /Q "LOGGING_OPTIMIZATION_GUIDE.md" 2>nul
del /F /Q "LOGGING_OPTIMIZATION_SUMMARY.md" 2>nul
del /F /Q "LOGGING_PERFORMANCE_ANALYSIS.md" 2>nul
del /F /Q "MIGRATION_CELERY.md" 2>nul
del /F /Q "MINIO_SETUP.md" 2>nul
del /F /Q "OPTIMISATIONS_NOTIFICATIONS.md" 2>nul
del /F /Q "OPTIMIZATIONS_SUMMARY.md" 2>nul
del /F /Q "PERFORMANCE_TEST_RESULTS.md" 2>nul
del /F /Q "POURQUOI_GARDER_LES_LOGS.md" 2>nul
del /F /Q "QUICK_START_ANTI_DOUBLONS.md" 2>nul
del /F /Q "QUICK_START_MINIO.md" 2>nul
del /F /Q "README_LOGGING_OPTIMIZATION.md" 2>nul
del /F /Q "SCHEMA_FIX.md" 2>nul
del /F /Q "SESSION_MANAGEMENT_IMPROVEMENTS.md" 2>nul
del /F /Q "SESSIONS_CLEANUP_GUIDE.md" 2>nul
del /F /Q "SOLUTION_DOUBLONS_NOTIFICATIONS.md" 2>nul
del /F /Q "TEST_RESULTS.md" 2>nul
del /F /Q "TOKENS_FCM_GUIDE.md" 2>nul
del /F /Q "USER_ROUTERS_INTEGRATION_SUMMARY.md" 2>nul
del /F /Q "USER_SESSIONS_FIXES.md" 2>nul
echo    ✓ Documentation technique obsolete supprimee

echo.
echo [4/7] Suppression des scripts obsoletes...
del /F /Q "configure_proxy_senelec.bat" 2>nul
del /F /Q "configure_senelec_proxy.bat" 2>nul
del /F /Q "deploy_fix.bat" 2>nul
del /F /Q "deploy_fix_no_rebuild.bat" 2>nul
del /F /Q "deploy_sans_rebuild.bat" 2>nul
del /F /Q "diagnose_docker_ssl.bat" 2>nul
del /F /Q "patch_conteneurs_actuels.bat" 2>nul
del /F /Q "start_celery_worker.bat" 2>nul
del /F /Q "start_celery_workers.bat" 2>nul
del /F /Q "start_server.bat" 2>nul
del /F /Q "stop_celery_workers.bat" 2>nul
del /F /Q "test_proxy.bat" 2>nul
del /F /Q "test_setup.bat" 2>nul
del /F /Q "fix_firebase_ssl.bat" 2>nul
echo    ✓ Scripts obsoletes supprimes

echo.
echo [5/7] Suppression des docker-compose obsoletes...
del /F /Q "docker-compose.celery.yml" 2>nul
del /F /Q "docker-compose.production.yml" 2>nul
del /F /Q "docker-compose.test.yml" 2>nul
del /F /Q "docker-compose.yml" 2>nul
echo    ✓ Docker-compose obsoletes supprimes

echo.
echo [6/7] Suppression des requirements obsoletes...
del /F /Q "requirements-simple.txt" 2>nul
echo    ✓ Requirements obsoletes supprimes

echo.
echo [7/7] Suppression de la documentation specifique obsolete...
del /F /Q "FIX_DOCKER_SSL.md" 2>nul
echo    ✓ Documentation specifique obsolete supprimee

echo.
echo ============================================================
echo   NETTOYAGE TERMINE
echo ============================================================
echo.
echo Fichiers GARDES (essentiels):
echo   ✓ QUICKSTART.md
echo   ✓ README_DOCKER.md
echo   ✓ GUIDE_UTILISATION_DOCKER.md
echo   ✓ INDEX_DOCUMENTATION.md
echo   ✓ RECAPITULATIF_FINAL.md
echo   ✓ PROBLEMES_RESOLUS_FINAL.md
echo   ✓ SUCCES_COMPLET.md
echo   ✓ DEPLOIEMENT_AVEC_PROXY.md
echo   ✓ FIREBASE_PROXY_SENELEC.md
echo   ✓ FIX_CELERY_QUEUES.md
echo   ✓ SOLUTIONS_DOCKER.md
echo   ✓ check_health.bat
echo   ✓ send_test_notification.bat
echo   ✓ docker-compose.fixed.yml
echo   ✓ requirements.txt
echo   ✓ Tous les fichiers .pfx (PRESERVES)
echo.
echo Fichiers SUPPRIMES: ~70 fichiers obsoletes
echo.
pause
