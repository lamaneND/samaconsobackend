from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.orm import Session
from app.models.models import TypeCompteur
from app.schemas.type_compteur_schemas import  TypeCompteurCreateSchema,TypeCompteurResponseSchema
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS

type_router = APIRouter(prefix="/type_compteur", tags=["TypeCompteur"])

@type_router.post("/")
async def create(data, db: Session = Depends(get_db_samaconso)):
    """Créer un type de compteur avec cache longue durée (données de référence)"""
    # Éviter les doublons rapidement via cache
    cache_key_by_label = CACHE_KEYS["TYPE_COMPTEUR_BY_LABEL"].format(label=data.label)
    cached = await cache_get(cache_key_by_label)
    if cached:
        return {"status": 409, "message": "Ce type de compteur existe déjà"}
    
    db_obj = TypeCompteur(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    type_data = {
        "id": db_obj.id,
        "label": db_obj.label,
        "created_at": db_obj.created_at.strftime("%d/%m/%Y %H:%M:%S") if db_obj.created_at else None,
        "updated_at": db_obj.updated_at.strftime("%d/%m/%Y %H:%M:%S") if db_obj.updated_at else None,
    }
    
    # Cache avec TTL très long (2 heures) pour données de référence
    try:
        await cache_set(cache_key_by_label, json.dumps(type_data), ttl_seconds=7200)
        await cache_delete(CACHE_KEYS["TYPE_COMPTEUR_ALL"])
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "Type de compteur créé avec succès",
        "type_compteur": type_data
    }

@type_router.get("/")
async def list_all(db: Session = Depends(get_db_samaconso)):
    """Récupérer tous les types de compteurs avec cache très long (données de référence)"""
    cache_key_all = CACHE_KEYS["TYPE_COMPTEUR_ALL"]
    try:
        cached = await cache_get(cache_key_all)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "type_compteurs": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    rows = db.query(TypeCompteur).all()
    type_compteurs_data = []
    for r in rows:
        type_compteurs_data.append({
            "id": r.id,
            "label": r.label,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        })
    
    # Cache avec TTL très long (2 heures) pour données de référence
    try:
        await cache_set(cache_key_all, json.dumps(type_compteurs_data), ttl_seconds=7200)
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(type_compteurs_data),
        "type_compteurs": type_compteurs_data,
        "cache_hit": False
    }

@type_router.get("/{type_id}")
def get_one(type_id:int,db: Session = Depends(get_db_samaconso)):
    return db.query(TypeCompteur).filter(TypeCompteur.id == type_id).first()


@type_router.put("/{type_id}")
def update_etat(type_id:int,type_update : TypeCompteurCreateSchema,db: Session = Depends(get_db_samaconso)):
    type_compteur_db = db.query(TypeCompteur).filter(TypeCompteur.id == type_id).first()
    if not type_compteur_db:
        raise HTTPException(status_code=404, detail="Type Compteur not found")
    for key, value in type_update.model_dump(exclude_unset=True).items():
        setattr(type_compteur_db, key, value)
    db.commit()
    db.refresh(type_compteur_db)
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("type_compteur:all"))
        if type_compteur_db.label:
            loop.create_task(cache_delete(f"type_compteur:label:{type_compteur_db.label}"))
    except Exception:
        pass
    return type_compteur_db

@type_router.delete("/{type_id}")
def delete_etat(type_id:int,db: Session = Depends(get_db_samaconso)):
    type_compteur_db = db.query(TypeCompteur).filter(TypeCompteur.id == type_id).first()
    if not type_compteur_db:
        raise HTTPException(status_code=404, detail="Type Compteur not found")
    db.delete(type_compteur_db)
    db.commit()
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("type_compteur:all"))
        if type_compteur_db.label:
            loop.create_task(cache_delete(f"type_compteur:label:{type_compteur_db.label}"))
    except Exception:
        pass
    return {"message": "Etat deleted successfully"}