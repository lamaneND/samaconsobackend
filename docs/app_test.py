"""
Configuration de test pour SamaConso API sans base de données
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.cache import init_redis, close_redis, get_redis

# Créer une application FastAPI minimale pour les tests
app = FastAPI(title="SamaConso API - Test Mode")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup() -> None:
    """Initialisation des services au démarrage"""
    await init_redis()
    print("✅ Redis initialisé")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Nettoyage des services à l'arrêt"""
    await close_redis()
    print("✅ Redis fermé")

@app.get("/")
async def hello_world():
    return {"message": "SAMA CONSO - Test Mode", "status": "OK"}

@app.get("/health/redis")
async def health_redis():
    try:
        client = get_redis()
        pong = await client.ping()
        return {"status": "ok", "pong": pong, "service": "redis"}
    except Exception as e:
        return {"status": "error", "detail": str(e), "service": "redis"}

@app.get("/health/rabbitmq")
async def health_rabbitmq():
    try:
        import aio_pika
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
        await connection.close()
        return {"status": "ok", "service": "rabbitmq"}
    except Exception as e:
        return {"status": "error", "detail": str(e), "service": "rabbitmq"}

@app.get("/test/cache")
async def test_cache():
    """Test simple du cache Redis"""
    try:
        client = get_redis()
        
        # Test d'écriture
        await client.set("test_docker", "Hello from Docker!", ex=30)
        
        # Test de lecture
        value = await client.get("test_docker")
        
        return {
            "status": "ok",
            "test": "cache_read_write", 
            "value": value,
            "message": "Cache fonctionne correctement"
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/test/notification-mock")
async def test_notification_mock():
    """Test mock d'une notification sans base de données"""
    return {
        "status": "ok",
        "message": "Notification mock créée",
        "notification": {
            "id": 999,
            "title": "Test Docker",
            "body": "Notification de test pour Docker",
            "type": "test"
        }
    }