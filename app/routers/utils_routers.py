from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session

from app.cache import cache_get, cache_set
from app.cache_utils import (
    get_cache_stats, 
    get_cache_keys_by_pattern, 
    get_cache_key_info,
    warm_up_cache,
    flush_cache_by_pattern,
    cache_health_check
)
from app.rabbitmq import publish_message
from app.database import get_db_samaconso


utils_router = APIRouter(prefix="/utils", tags=["utils"])


@utils_router.post("/cache")
async def set_cache(key: str = Query(...), value: str = Query(...)):
    ok = await cache_set(key, value)
    return {"ok": ok}


@utils_router.get("/cache")
async def get_cache(key: str = Query(...)):
    value = await cache_get(key)
    return {"value": value}


@utils_router.post("/publish")
async def publish(msg: str = Query(...)):
    await publish_message(msg.encode("utf-8"))
    return {"published": True}


# Endpoints de monitoring du cache
@utils_router.get("/cache/stats")
async def get_redis_stats():
    """Récupère les statistiques du cache Redis"""
    return await get_cache_stats()


@utils_router.get("/cache/health")
async def check_cache_health():
    """Vérification de santé du cache"""
    return await cache_health_check()


@utils_router.get("/cache/keys")
async def list_cache_keys(pattern: str = Query("*", description="Pattern pour filtrer les clés")):
    """Liste les clés de cache selon un pattern"""
    keys = await get_cache_keys_by_pattern(pattern)
    return {"pattern": pattern, "count": len(keys), "keys": keys[:50]}  # Limité à 50 pour éviter surcharge


@utils_router.get("/cache/key/{key_name}")
async def get_key_info(key_name: str):
    """Récupère les informations d'une clé spécifique"""
    return await get_cache_key_info(key_name)


@utils_router.post("/cache/warmup")
async def warmup_cache(db: Session = Depends(get_db_samaconso)):
    """Précharge le cache avec les données couramment utilisées"""
    return await warm_up_cache(db)


@utils_router.delete("/cache/flush")
async def flush_cache(pattern: str = Query("*", description="Pattern des clés à supprimer")):
    """Supprime les clés de cache selon un pattern (ATTENTION: opération destructive)"""
    if pattern == "*":
        return {"error": "Utilisation du pattern '*' interdite pour des raisons de sécurité. Utilisez un pattern plus spécifique."}
    return await flush_cache_by_pattern(pattern)

