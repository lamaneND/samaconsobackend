from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.orm import Session
from app.models.models import EtatCompteur
from app.schemas.etat_compteur_schemas import  EtatCompteurResponseSchema,EtatCompteurCreateSchema,EtatCompteurUpdateSchema
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS

etat_compteur_router = APIRouter(prefix="/etat", tags=["Etat"])

@etat_compteur_router.post("/")
async def create(data: EtatCompteurCreateSchema, db: Session = Depends(get_db_samaconso)):
    cache_key_by_label = CACHE_KEYS["ETAT_COMPTEUR_BY_LABEL"].format(label=data.label)
    cached = await cache_get(cache_key_by_label)
    if cached:
        return json.loads(cached)
    db_obj = EtatCompteur(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    payload = {
        "id": db_obj.id,
        "label": db_obj.label,
        "created_at": db_obj.created_at.strftime("%d/%m/%Y %H:%M:%S") if db_obj.created_at else None,
        "updated_at": db_obj.updated_at.strftime("%d/%m/%Y %H:%M:%S") if db_obj.updated_at else None,
    }
    try:
        await cache_set(cache_key_by_label, json.dumps(payload))
        await cache_delete(CACHE_KEYS["ETAT_COMPTEUR_ALL"])
    except Exception:
        pass
    return payload

@etat_compteur_router.get("/")
async def list_all(db: Session = Depends(get_db_samaconso)):
    """Récupérer tous les états compteur avec cache quasi-statique (1h TTL)"""
    cache_key_all = CACHE_KEYS["ETAT_COMPTEUR_ALL"]
    try:
        cached = await cache_get(cache_key_all)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "etats": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    rows = db.query(EtatCompteur).all()
    etats_data = []
    for r in rows:
        etats_data.append({
            "id": r.id,
            "label": r.label,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        })
    
    # Cache avec TTL quasi-statique (1 heure) pour données de référence
    try:
        await cache_set(cache_key_all, json.dumps(etats_data), ttl_seconds=3600)
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(etats_data),
        "etats": etats_data,
        "cache_hit": False
    }

@etat_compteur_router.get("/{etat_id}")
def get_one(etat_id:int,db: Session = Depends(get_db_samaconso)):
    return db.query(EtatCompteur).filter(EtatCompteur.id == etat_id).first()

@etat_compteur_router.put("/{etat_id}")
async def update_etat(etat_id:int,etat_update : EtatCompteurUpdateSchema,db: Session = Depends(get_db_samaconso)):
    etat_db = db.query(EtatCompteur).filter(EtatCompteur.id == etat_id).first()
    if not etat_db:
        raise HTTPException(status_code=404, detail="Etat not found")
    for key, value in etat_update.model_dump(exclude_unset=True).items():
        setattr(etat_db, key, value)
    db.commit()
    db.refresh(etat_db)
    try:
        await cache_delete(CACHE_KEYS["ETAT_COMPTEUR_ALL"])
        if etat_db.label:
            await cache_delete(CACHE_KEYS["ETAT_COMPTEUR_BY_LABEL"].format(label=etat_db.label))
    except Exception:
        pass
    return etat_db

@etat_compteur_router.delete("/{etat_id}")
async def delete_etat(etat_id:int,db: Session = Depends(get_db_samaconso)):
    etat_db = db.query(EtatCompteur).filter(EtatCompteur.id == etat_id).first()
    if not etat_db:
        raise HTTPException(status_code=404, detail="Etat not found")
    label = etat_db.label
    db.delete(etat_db)
    db.commit()
    try:
        await cache_delete(CACHE_KEYS["ETAT_COMPTEUR_ALL"])
        if label:
            await cache_delete(CACHE_KEYS["ETAT_COMPTEUR_BY_LABEL"].format(label=label))
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "État supprimé avec succès"
    }

@etat_compteur_router.get("/cache/inspect")
async def inspect_etat_cache():
    """Inspecter l'état du cache des états compteur"""
    from app.cache import redis_client
    
    try:
        if not redis_client:
            return {"status": 500, "message": "Redis non disponible"}
        
        # Rechercher toutes les clés d'états
        etat_patterns = ["etat_compteur:*"]
        etat_keys = []
        
        for pattern in etat_patterns:
            keys = await redis_client.keys(pattern)
            etat_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        
        cache_contents = {}
        for key in etat_keys:
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
                "etat_cache_keys": etat_keys,
                "cache_contents": cache_contents
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "message": f"Erreur inspection cache: {str(e)}"
        }