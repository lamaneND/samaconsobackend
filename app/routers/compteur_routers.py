from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.models.models import Compteur
from app.schemas.compteur_schemas import CompteurCreateSchema 
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS, CACHE_TTL

compteur_router = APIRouter(prefix="/compteur", tags=["Compteur"])

@compteur_router.post("/")
async def create(data: CompteurCreateSchema, db: Session = Depends(get_db_samaconso)):
    key_by_num = CACHE_KEYS["COMPTEUR_BY_NUMERO"].format(numero=data.numero)
    cached = await cache_get(key_by_num)
    if cached:
        return json.loads(cached)
    db_obj = Compteur(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    payload = {
        "id": db_obj.id,
        "numero": db_obj.numero,
        "type_compteur": db_obj.type_compteur,
        "created_at": db_obj.created_at.strftime("%d/%m/%Y %H:%M:%S") if db_obj.created_at else None,
        "updated_at": db_obj.updated_at.strftime("%d/%m/%Y %H:%M:%S") if db_obj.updated_at else None,
    }
    try:
        await cache_set(key_by_num, json.dumps(payload))
        await cache_delete(CACHE_KEYS["COMPTEURS_ALL"])
    except Exception:
        pass
    return payload

@compteur_router.get("/")
async def list_all(db: Session = Depends(get_db_samaconso)):
    """Récupérer tous les compteurs avec cache optimisé"""
    key_all = CACHE_KEYS["COMPTEURS_ALL"]
    try:
        cached = await cache_get(key_all)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "compteurs": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    rows = db.query(Compteur).all()
    compteurs_data = []
    for r in rows:
        compteurs_data.append({
            "id": r.id,
            "numero": r.numero,
            "type_compteur": r.type_compteur,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        })
    
    # Cache avec TTL spécifique pour les compteurs (15 minutes)
    try:
        await cache_set(key_all, json.dumps(compteurs_data), ttl_seconds=900)  # CACHE_TTL["COMPTEURS"]
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(compteurs_data),
        "compteurs": compteurs_data,
        "cache_hit": False
    }

@compteur_router.get("/{compteur_id}")
async def get_one(compteur_id: int, db: Session = Depends(get_db_samaconso)):
    """Récupérer un compteur par ID avec cache"""
    cache_key = CACHE_KEYS["COMPTEUR_BY_ID"].format(id=compteur_id)
    try:
        cached = await cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "compteur": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    compteur = db.query(Compteur).filter(Compteur.id == compteur_id).first()
    if not compteur:
        raise HTTPException(status_code=404, detail="Compteur not found")
    
    compteur_data = {
        "id": compteur.id,
        "numero": compteur.numero,
        "type_compteur": compteur.type_compteur,
        "created_at": compteur.created_at.strftime("%d/%m/%Y %H:%M:%S") if compteur.created_at else None,
        "updated_at": compteur.updated_at.strftime("%d/%m/%Y %H:%M:%S") if compteur.updated_at else None,
    }
    
    try:
        await cache_set(cache_key, json.dumps(compteur_data), ttl_seconds=900)  # CACHE_TTL["COMPTEURS"]
    except Exception:
        pass
    
    return {
        "status": 200,
        "compteur": compteur_data,
        "cache_hit": False
    }


@compteur_router.put("/{compteur_id}")
async def update_etat(compteur_id: int, compteur_update: CompteurCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Mettre à jour un compteur avec invalidation cache intelligente"""
    compteur_db = db.query(Compteur).filter(Compteur.id == compteur_id).first()
    if not compteur_db:
        raise HTTPException(status_code=404, detail="Compteur not found")
    
    old_numero = compteur_db.numero
    for key, value in compteur_update.model_dump(exclude_unset=True).items():
        setattr(compteur_db, key, value)
    db.commit()
    db.refresh(compteur_db)
    
    # Invalidation intelligente du cache
    try:
        await cache_delete(CACHE_KEYS["COMPTEURS_ALL"])
        await cache_delete(CACHE_KEYS["COMPTEUR_BY_ID"].format(id=compteur_id))
        
        # Si le numéro a changé, invalider les deux clés
        if old_numero and old_numero != compteur_db.numero:
            await cache_delete(CACHE_KEYS["COMPTEUR_BY_NUMERO"].format(numero=old_numero))
        if compteur_db.numero:
            await cache_delete(CACHE_KEYS["COMPTEUR_BY_NUMERO"].format(numero=compteur_db.numero))
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "Compteur updated successfully",
        "compteur": {
            "id": compteur_db.id,
            "numero": compteur_db.numero,
            "type_compteur": compteur_db.type_compteur,
            "created_at": compteur_db.created_at.strftime("%d/%m/%Y %H:%M:%S") if compteur_db.created_at else None,
            "updated_at": compteur_db.updated_at.strftime("%d/%m/%Y %H:%M:%S") if compteur_db.updated_at else None,
        }
    }

@compteur_router.delete("/{compteur_id}")
async def delete_etat(compteur_id: int, db: Session = Depends(get_db_samaconso)):
    """Supprimer un compteur avec invalidation cache"""
    compteur_db = db.query(Compteur).filter(Compteur.id == compteur_id).first()
    if not compteur_db:
        raise HTTPException(status_code=404, detail="Compteur not found")
    
    numero = compteur_db.numero
    db.delete(compteur_db)
    db.commit()
    
    # Invalidation complète du cache
    try:
        await cache_delete(CACHE_KEYS["COMPTEURS_ALL"])
        await cache_delete(CACHE_KEYS["COMPTEUR_BY_ID"].format(id=compteur_id))
        if numero:
            await cache_delete(CACHE_KEYS["COMPTEUR_BY_NUMERO"].format(numero=numero))
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "Compteur deleted successfully"
    }

@compteur_router.get("/cache/inspect")
async def inspect_compteur_cache():
    """Inspecter l'état du cache des compteurs"""
    from app.cache import redis_client
    
    try:
        if not redis_client:
            return {"status": 500, "message": "Redis non disponible"}
        
        # Rechercher toutes les clés de compteurs
        compteur_patterns = ["compteurs:*", "compteur:*"]
        compteur_keys = []
        
        for pattern in compteur_patterns:
            keys = await redis_client.keys(pattern)
            compteur_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        
        cache_contents = {}
        for key in compteur_keys:
            try:
                ttl = await redis_client.ttl(key)
                content = await redis_client.get(key)
                if content:
                    cache_contents[key] = {
                        "ttl_seconds": ttl,
                        "size_bytes": len(content),
                        "preview": content[:100].decode() if isinstance(content, bytes) else str(content)[:100]
                    }
            except Exception as e:
                cache_contents[key] = {"error": str(e)}
        
        return {
            "status": 200,
            "message": "Cache inspection successful",
            "cache_info": {
                "redis_connected": True,
                "compteur_cache_keys": compteur_keys,
                "cache_contents": cache_contents
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "message": f"Erreur inspection cache: {str(e)}"
        }