from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.sic_routers import sic_router
from app.routers.postpaid_routers import postpaid_router
from app.routers.role_routers import role_router
from app.routers.user_routers import user_router
from app.routers.auth_routers import auth_router
from app.routers.sms_routers import sms_router
from app.routers.compteur_routers import compteur_router
from app.routers.etat_compteur_routers import etat_compteur_router
from app.routers.type_compteur_routers import type_router
from app.routers.user_compteur_routers import user_compteur_router
from app.routers.user_session_routers import user_session_router
from app.routers.type_notification_routers import type_notification_router
from app.routers.notification_routers import notification_router
from app.routers.websocket_routers import websocket_router
from app.routers.dashboard_routers import dashboard_router
from app.routers.agence_routers import agence_router
from app.routers.type_demande_routers import type_demande_router
from app.routers.demande_routers import demande_router
from app.routers.upload_routers import upload_router
from app.routers.seuil_tarif_routers import seuil_tarif_router
# from app.routers.simulateur_routers_old import simulateur_router
# from app.routers.simulateur_routers_v2 import simulateur_router_v2
# from app.routers.simulateur_routers_v3 import simulateur_router_v3
from app.routers.simulateur_routers import simulateur_router
from app.routers.logs_routers import logs_router
from app.firebase import *
from app.cache import init_redis, close_redis, get_redis
from app.rabbitmq import init_rabbitmq, close_rabbitmq
from app.routers.utils_routers import utils_router
from app.logging_config import init_logging, get_logger
from app.middleware.logging_middleware import RequestLoggingMiddleware, SecurityLoggingMiddleware
from app.services.minio_service import init_minio_service
from app import config
import requests
import os
import ssl
import urllib3
import sys
from pathlib import Path
def ssl_diag():
    return {
        "python": sys.version,
        "ssl.OPENSSL_VERSION": ssl.OPENSSL_VERSION,               # ex: OpenSSL 3.0.13 ...
        "ssl.OPENSSL_VERSION_INFO": ssl.OPENSSL_VERSION_INFO,     # tuple (major,minor,fix,patch, status)
        "_OPENSSL_API_VERSION": getattr(ssl, "_OPENSSL_API_VERSION", None),
        "HAS_TLS13": hasattr(ssl, "TLSVersion") and hasattr(ssl.TLSVersion, "TLSv1_3"),
        "default_verify_paths": ssl.get_default_verify_paths()._asdict(),
    }
# Get the path to the custom OpenSSL configuration file
BASE_DIR = Path(__file__).resolve().parent.parent
OPENSSL_CONF_PATH = BASE_DIR / "openssl_legacy.cnf"

# os.environ["REQUESTS_CA_BUNDLE"] ="E:/projets/samaconsoapi-dev_pcyn/venv/Lib/site-packages/certifi/cacert.pem"

# Ignorer les erreurs SSL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ssl._create_default_https_context = ssl._create_unverified_context

os.environ["HTTP_PROXY"] = "http://10.101.201.204:8080"
os.environ["HTTPS_PROXY"] = "http://10.101.201.204:8080"
proxies = {
    'http': 'http://10.101.201.204:8080',
    'https': 'http://10.101.201.204:8080',
}
try:
    r = requests.get("https://oauth2.googleapis.com/token",proxies=proxies,verify=False,timeout=10)
    print("Connexion réussie")
except Exception as e:
    print("Erreur :", e)


# Initialisation du système de logs
environment = os.getenv("ENVIRONMENT", "development")
log_manager = init_logging(environment)
main_logger = get_logger("app.main")

app = FastAPI(title="SamaConso API", version="2.0.0")

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ajouter les middlewares de logging
app.add_middleware(SecurityLoggingMiddleware)
app.add_middleware(RequestLoggingMiddleware, exclude_paths=["/health", "/docs", "/openapi.json", "/favicon.ico"])

main_logger.info("🚀 SamaConso API application initialized")
main_logger.info(f"🌍 Environment: {environment}")
main_logger.info(f"🔧 CORS configured for origins: {origins}")
main_logger.info("📊 Request logging middleware enabled")

app.include_router(sic_router)
app.include_router(postpaid_router)
app.include_router(role_router)
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(sms_router)
app.include_router(compteur_router)
app.include_router(etat_compteur_router)
app.include_router(type_router)
app.include_router(user_compteur_router)
app.include_router(user_session_router)
app.include_router(notification_router)
app.include_router(websocket_router)
app.include_router(type_notification_router)
app.include_router(dashboard_router)
app.include_router(agence_router)
app.include_router(type_demande_router)
app.include_router(demande_router)
app.include_router(upload_router)
app.include_router(seuil_tarif_router)
app.include_router(simulateur_router)
app.include_router(utils_router)
app.include_router(logs_router)


@app.on_event("startup")
async def on_startup() -> None:
    main_logger.info("🔄 Starting application services...")

    try:
        await init_redis()
        main_logger.info("✅ Redis connection initialized successfully")
    except Exception as e:
        main_logger.error(f"❌ Redis initialization failed: {e}")
        raise

    # RabbitMQ (Réactivé pour la production)
    try:
        await init_rabbitmq()
        main_logger.info("✅ RabbitMQ connection initialized successfully")
    except Exception as e:
        main_logger.warning(f"⚠️ RabbitMQ non disponible, continuons sans: {e}")

    # Initialisation MinIO
    try:
        init_minio_service(
            endpoint=config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
            bucket_name=config.MINIO_BUCKET_NAME
        )
        main_logger.info("✅ MinIO service initialized successfully")
    except Exception as e:
        main_logger.error(f"❌ MinIO initialization failed: {e}")
        # Ne pas bloquer le démarrage si MinIO n'est pas disponible
        main_logger.warning("⚠️ Application continuera sans MinIO")

    main_logger.info("🎯 All services started successfully")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    main_logger.info("🔄 Shutting down application services...")
    
    try:
        await close_redis()
        main_logger.info("✅ Redis connection closed successfully")
    except Exception as e:
        main_logger.error(f"❌ Error closing Redis connection: {e}")
    
    # RabbitMQ temporairement désactivé
    # try:
    #     await close_rabbitmq()
    #     main_logger.info("✅ RabbitMQ connection closed successfully")
    # except Exception as e:
    #     main_logger.warning(f"⚠️ Erreur lors de la fermeture RabbitMQ: {e}")
    
    main_logger.info("🏁 Application shutdown completed")


@app.get("/")
async def hello_world():
    main_logger.info("🏠 Home endpoint accessed")
    return {"message":"SAMA CONSO", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Endpoint de santé simple pour les health checks et load balancers"""
    return {"status": "ok", "message": "SamaConso API is running", "version": "2.0.0"}


@app.get("/health/redis")
async def health_redis():
    try:
        client = get_redis()
        pong = await client.ping()
        main_logger.info("✅ Redis health check successful")
        return {"status": "ok", "pong": pong}
    except Exception as e:
        main_logger.error(f"❌ Redis health check failed: {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/health/rabbitmq")
async def health_rabbitmq():
    try:
        # If startup initialized connection successfully, this will be fine
        main_logger.info("✅ RabbitMQ health check successful")
        return {"status": "ok"}
    except Exception as e:
        main_logger.error(f"❌ RabbitMQ health check failed: {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/health/logs")
async def health_logs():
    """Endpoint pour vérifier le système de logs"""
    try:
        main_logger.debug("🔍 Debug log test")
        main_logger.info("ℹ️ Info log test") 
        main_logger.warning("⚠️ Warning log test")
        
        return {
            "status": "ok",
            "message": "Logging system operational",
            "log_directory": str(Path("logs").absolute()),
            "environment": environment
        }
    except Exception as e:
        main_logger.error(f"❌ Logging system error: {e}")
        return {"status": "error", "detail": str(e)}

@app.post("/test/logs")
async def test_logging_system():
    """Endpoint pour tester tous les niveaux de logs"""
    try:
        # Test différents niveaux
        main_logger.debug("🐛 Test DEBUG: Message de débogage détaillé")
        main_logger.info("📝 Test INFO: Opération normale réussie")
        main_logger.warning("⚠️ Test WARNING: Attention requise")
        main_logger.error("❌ Test ERROR: Erreur simulée (test uniquement)")
        
        # Test logs spécialisés
        from app.logging_config import log_notification, log_security, log_database, log_cache
        
        log_notification(999, "Test notification système", 5, "FCM")
        log_security("Test security event", 999, "127.0.0.1", "Simulation d'événement sécuritaire")
        log_database("SELECT", "test_table", 10, 25.5)
        log_cache("GET", "test:cache:key", True, 300)
        
        main_logger.info("✅ Test logging system completed successfully")
        
        return {
            "status": "success",
            "message": "Test de logs effectué avec succès",
            "logs_generated": {
                "debug": 1,
                "info": 2,
                "warning": 1,
                "error": 1,
                "notification": 1,
                "security": 1,
                "database": 1,
                "cache": 1
            },
            "check_files": [
                "logs/samaconso.log",
                "logs/samaconso_errors.log",
                "logs/notifications.log"
            ]
        }
        
    except Exception as e:
        main_logger.error(f"❌ Error during logging system test: {e}")
        return {"status": "error", "detail": str(e)}
