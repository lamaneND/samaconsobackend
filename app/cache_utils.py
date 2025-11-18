"""
Utilitaires de monitoring et gestion du cache Redis
"""
from app.cache import get_redis
from app.config import CACHE_KEYS
import json
from typing import Dict, List, Optional


async def get_cache_stats() -> Dict:
    """
    Récupère les statistiques du cache Redis
    """
    try:
        client = get_redis()
        info = await client.info()
        
        stats = {
            "redis_version": info.get("redis_version"),
            "used_memory": info.get("used_memory_human"),
            "used_memory_peak": info.get("used_memory_peak_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "expired_keys": info.get("expired_keys", 0),
        }
        
        # Calcul du hit rate
        hits = stats["keyspace_hits"]
        misses = stats["keyspace_misses"]
        total = hits + misses
        if total > 0:
            stats["hit_rate_percent"] = round((hits / total) * 100, 2)
        else:
            stats["hit_rate_percent"] = 0.0
            
        return stats
    except Exception as e:
        return {"error": f"Failed to get cache stats: {e}"}


async def get_cache_keys_by_pattern(pattern: str = "*") -> List[str]:
    """
    Récupère toutes les clés correspondant au pattern
    """
    try:
        client = get_redis()
        keys = await client.keys(pattern)
        return keys
    except Exception as e:
        return []


async def get_cache_key_info(key: str) -> Dict:
    """
    Récupère les informations d'une clé de cache spécifique
    """
    try:
        client = get_redis()
        
        # Vérifier si la clé existe
        exists = await client.exists(key)
        if not exists:
            return {"error": f"Key '{key}' does not exist"}
        
        # Récupérer les informations
        ttl = await client.ttl(key)
        key_type = await client.type(key)
        value = await client.get(key)
        
        info = {
            "key": key,
            "type": key_type,
            "ttl_seconds": ttl,
            "size_bytes": len(value.encode('utf-8')) if value else 0,
        }
        
        # Ajouter des infos spécifiques selon le type
        if key_type == "string":
            info["value_preview"] = value[:100] + "..." if len(value) > 100 else value
            
        return info
    except Exception as e:
        return {"error": f"Failed to get key info: {e}"}


async def warm_up_cache(db_session) -> Dict[str, int]:
    """
    Précharge le cache avec les données les plus couramment utilisées
    """
    from app.cache import cache_set
    from app.models.models import Agence, Role, EtatCompteur, TypeCompteur
    
    results = {"success": 0, "errors": 0}
    
    try:
        # Précharger les agences
        agences = db_session.query(Agence).all()
        agences_data = []
        for a in agences:
            agences_data.append({
                "id": a.id,
                "nom": a.nom,
                "nom_corrige": a.nom_corrige,
                "created_at": a.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "updated_at": a.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
            })
        
        await cache_set(CACHE_KEYS["AGENCES_ALL"], json.dumps(agences_data))
        results["success"] += 1
        
        # Précharger les rôles
        roles = db_session.query(Role).all()
        roles_data = []
        for r in roles:
            roles_data.append({
                "id": r.id,
                "label": r.label,
                "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
            })
        
        await cache_set(CACHE_KEYS["ROLES_ALL"], json.dumps(roles_data))
        results["success"] += 1
        
        # Précharger les états compteur
        etats = db_session.query(EtatCompteur).all()
        etats_data = []
        for e in etats:
            etats_data.append({
                "id": e.id,
                "label": e.label,
                "created_at": e.created_at.strftime("%d/%m/%Y %H:%M:%S") if e.created_at else None,
                "updated_at": e.updated_at.strftime("%d/%m/%Y %H:%M:%S") if e.updated_at else None,
            })
        
        await cache_set(CACHE_KEYS["ETAT_COMPTEUR_ALL"], json.dumps(etats_data))
        results["success"] += 1
        
    except Exception as e:
        results["errors"] += 1
        results["error_detail"] = str(e)
    
    return results


async def flush_cache_by_pattern(pattern: str) -> Dict[str, int]:
    """
    Supprime toutes les clés correspondant au pattern
    """
    try:
        client = get_redis()
        keys = await client.keys(pattern)
        
        if keys:
            deleted = await client.delete(*keys)
            return {"deleted": deleted, "keys": keys}
        else:
            return {"deleted": 0, "keys": []}
            
    except Exception as e:
        return {"error": f"Failed to flush cache: {e}"}


async def cache_health_check() -> Dict:
    """
    Vérification de santé du cache Redis
    """
    try:
        client = get_redis()
        
        # Test de connectivité
        pong = await client.ping()
        if not pong:
            return {"status": "unhealthy", "error": "Redis ping failed"}
        
        # Test d'écriture/lecture
        test_key = "_health_check_test"
        test_value = "test_value"
        
        await client.set(test_key, test_value, ex=5)  # Expire en 5 secondes
        retrieved_value = await client.get(test_key)
        
        if retrieved_value != test_value:
            return {"status": "unhealthy", "error": "Redis read/write test failed"}
        
        await client.delete(test_key)
        
        return {
            "status": "healthy",
            "redis_ping": True,
            "read_write_test": True,
        }
        
    except Exception as e:
        return {"status": "unhealthy", "error": f"Health check failed: {e}"}