import json
import functools
from typing import Optional, Callable, Any
from app.cache import cache_get, cache_set


def cached(key_prefix: str, ttl_seconds: Optional[int] = None):
    """
    Décorateur pour mettre en cache les résultats des fonctions.
    
    Args:
        key_prefix: Préfixe pour la clé de cache
        ttl_seconds: TTL personnalisé (optionnel)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Génère une clé unique basée sur les arguments
            cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
            
            # Tente de récupérer depuis le cache
            try:
                cached_result = await cache_get(cache_key)
                if cached_result:
                    return json.loads(cached_result)
            except Exception:
                pass
            
            # Exécute la fonction si pas en cache
            result = await func(*args, **kwargs)
            
            # Met en cache le résultat
            try:
                await cache_set(cache_key, json.dumps(result, default=str), ttl_seconds)
            except Exception:
                pass
            
            return result
        return wrapper
    return decorator


def cache_invalidate(*keys: str):
    """
    Décorateur pour invalider des clés de cache après l'exécution d'une fonction.
    
    Args:
        *keys: Clés de cache à invalider
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)
            
            # Invalide les clés spécifiées
            from app.cache import cache_delete
            try:
                for key in keys:
                    await cache_delete(key)
            except Exception:
                pass
            
            return result
        return wrapper
    return decorator