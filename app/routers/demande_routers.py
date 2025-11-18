# routers/demande.py
from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.orm import Session
from app.models.models import Demande
from app.schemas.demande_schemas import *
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS, CACHE_TTL

demande_router = APIRouter(prefix="/demandes", tags=["Demandes"])

@demande_router.post("/")
async def create_demande(demande, db: Session = Depends(get_db_samaconso)):
    """Créer une demande avec invalidation cache intelligente"""
    db_demande = Demande(**demande.model_dump())
    db.add(db_demande)
    db.commit()
    db.refresh(db_demande)
    
    # Invalidation cache avec nouveaux patterns
    try:
        await cache_delete(CACHE_KEYS["DEMANDES_ALL"])
        if demande.fait_par:
            await cache_delete(CACHE_KEYS["DEMANDES_BY_USER"].format(user_id=demande.fait_par))
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "Demande créée avec succès",
        "demande": {
            "id": db_demande.id,
            "fait_par": db_demande.fait_par,
            "traite_par": db_demande.traite_par,
            "user_compteur_id": db_demande.user_compteur_id,
            "type_demande": db_demande.type_demande,
            "commentaire": db_demande.commentaire,
            "fichier": db_demande.fichier,
            "created_at": db_demande.created_at.strftime("%d/%m/%Y %H:%M:%S") if db_demande.created_at else None,
            "updated_at": db_demande.updated_at.strftime("%d/%m/%Y %H:%M:%S") if db_demande.updated_at else None,
        }
    }

@demande_router.get("/")
async def get_demandes(db: Session = Depends(get_db_samaconso)):
    """Récupérer toutes les demandes avec cache dynamique (TTL court)"""
    key_all = CACHE_KEYS["DEMANDES_ALL"]
    try:
        cached = await cache_get(key_all)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "demandes": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    rows = db.query(Demande).all()
    demandes_data = []
    for r in rows:
        demandes_data.append({
            "id": r.id,
            "fait_par": r.fait_par,
            "traite_par": r.traite_par,
            "user_compteur_id": r.user_compteur_id,
            "type_demande": r.type_demande,
            "commentaire": r.commentaire,
            "fichier": r.fichier,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        })
    
    # Cache avec TTL court (5 minutes) pour données dynamiques
    try:
        await cache_set(key_all, json.dumps(demandes_data), ttl_seconds=300)  # CACHE_TTL["DEMANDES"]
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(demandes_data),
        "demandes": demandes_data,
        "cache_hit": False
    }

@demande_router.get("/user/{user_id}")
async def get_demandes_by_user(user_id: int, db: Session = Depends(get_db_samaconso)):
    """Récupérer les demandes d'un utilisateur avec cache"""
    cache_key = CACHE_KEYS["DEMANDES_BY_USER"].format(user_id=user_id)
    try:
        cached = await cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "demandes": data,
                "user_id": user_id,
                "cache_hit": True
            }
    except Exception:
        pass
    
    rows = db.query(Demande).filter(Demande.fait_par == user_id).all()
    demandes_data = []
    for r in rows:
        demandes_data.append({
            "id": r.id,
            "fait_par": r.fait_par,
            "traite_par": r.traite_par,
            "user_compteur_id": r.user_compteur_id,
            "type_demande": r.type_demande,
            "commentaire": r.commentaire,
            "fichier": r.fichier,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        })
    
    # Cache avec TTL court (5 minutes)
    try:
        await cache_set(cache_key, json.dumps(demandes_data), ttl_seconds=300)
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(demandes_data),
        "demandes": demandes_data,
        "user_id": user_id,
        "cache_hit": False
    }

@demande_router.get("/{demande_id}")
async def get_demande(demande_id: int, db: Session = Depends(get_db_samaconso)):
    """Récupérer une demande par ID avec cache"""
    cache_key = CACHE_KEYS["DEMANDE_BY_ID"].format(id=demande_id)
    try:
        cached = await cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "demande": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    demande = db.query(Demande).get(demande_id)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    
    demande_data = {
        "id": demande.id,
        "fait_par": demande.fait_par,
        "traite_par": demande.traite_par,
        "user_compteur_id": demande.user_compteur_id,
        "type_demande": demande.type_demande,
        "commentaire": demande.commentaire,
        "fichier": demande.fichier,
        "created_at": demande.created_at.strftime("%d/%m/%Y %H:%M:%S") if demande.created_at else None,
        "updated_at": demande.updated_at.strftime("%d/%m/%Y %H:%M:%S") if demande.updated_at else None,
    }
    
    try:
        await cache_set(cache_key, json.dumps(demande_data), ttl_seconds=300)
    except Exception:
        pass
    
    return {
        "status": 200,
        "demande": demande_data,
        "cache_hit": False
    }

@demande_router.put("/{demande_id}")
async def update_demande(demande_id: int, update_data: DemandeUpdateSchema, db: Session = Depends(get_db_samaconso)):
    demande = db.query(Demande).get(demande_id)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(demande, key, value)
    db.commit()
    db.refresh(demande)
    try:
        await cache_delete("demandes:all")
    except Exception:
        pass
    return demande

@demande_router.delete("/{demande_id}")
async def delete_demande(demande_id: int, db: Session = Depends(get_db_samaconso)):
    """Supprimer une demande avec invalidation cache complète"""
    demande = db.query(Demande).get(demande_id)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande non trouvée")
    
    user_id = demande.fait_par
    db.delete(demande)
    db.commit()
    
    # Invalidation complète du cache
    try:
        await cache_delete(CACHE_KEYS["DEMANDES_ALL"])
        await cache_delete(CACHE_KEYS["DEMANDE_BY_ID"].format(id=demande_id))
        if user_id:
            await cache_delete(CACHE_KEYS["DEMANDES_BY_USER"].format(user_id=user_id))
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "Demande supprimée avec succès"
    }

@demande_router.get("/cache/inspect")
async def inspect_demande_cache():
    """Inspecter l'état du cache des demandes"""
    from app.cache import redis_client
    
    try:
        if not redis_client:
            return {"status": 500, "message": "Redis non disponible"}
        
        # Rechercher toutes les clés de demandes
        demande_patterns = ["demandes:*", "demande:*"]
        demande_keys = []
        
        for pattern in demande_patterns:
            keys = await redis_client.keys(pattern)
            demande_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        
        cache_contents = {}
        for key in demande_keys:
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
                "demande_cache_keys": demande_keys,
                "cache_contents": cache_contents
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "message": f"Erreur inspection cache: {str(e)}"
        }
