from fastapi import APIRouter, Depends, HTTPException,status
import json
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db_samaconso
from app.models.models import Agence
from app.schemas.agence_schemas import AgenceCreateSchemas, AgenceUpdateSchemas
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS


agence_router = APIRouter(prefix="/agence",tags=["agence"])


# Endpoint pour créer un role
@agence_router.post("/")
async def create_agence(agence:AgenceCreateSchemas,db:Session=Depends(get_db_samaconso)):
    # Lecture cache par nom pour refuser les doublons rapidement
    cache_key_by_name = CACHE_KEYS["AGENCE_BY_NAME"].format(name=agence.nom)
    cached_agence_by_name = await cache_get(cache_key_by_name)
    if cached_agence_by_name:
        return {"status":status.HTTP_409_CONFLICT,"message":"Cette agence existe déjà"}

    agence_exist = db.query(Agence).filter(Agence.nom==agence.nom).first()
    if agence_exist:
        return {"status":status.HTTP_409_CONFLICT,"message":"Cette agence existe déjà"}

    created_agence = Agence(nom=agence.nom,nom_corrige=agence.nom_corrige)
    db.add(created_agence)
    db.commit()
    db.refresh(created_agence)
    created_agence.created_at = created_agence.created_at.strftime("%d/%m/%Y %H:%M:%S")
    created_agence.updated_at = created_agence.updated_at.strftime("%d/%m/%Y %H:%M:%S")

    # Mise à jour du cache: clé par nom, et invalidation de la liste
    try:
        await cache_set(cache_key_by_name, json.dumps({
            "id": created_agence.id,
            "nom": created_agence.nom,
            "nom_corrige": created_agence.nom_corrige,
            "created_at": created_agence.created_at,
            "updated_at": created_agence.updated_at,
        }))
        await cache_delete(CACHE_KEYS["AGENCES_ALL"])
    except Exception:
        pass

    return {"status":200,"agence":created_agence}

#Récupérer tous les roles créés

@agence_router.get("/")
async def get_all_agences(db:Session=Depends(get_db_samaconso)):
    cache_key_all = CACHE_KEYS["AGENCES_ALL"]
    # Lecture depuis le cache si disponible
    try:
        cached = await cache_get(cache_key_all)
        if cached:
            data = json.loads(cached)
            return {"status":status.HTTP_200_OK,"results":len(data),"agences":data}
    except Exception:
        pass

    agences = db.query(Agence).all()
    agences_payload = []
    for a in agences:
        agences_payload.append({
            "id": a.id,
            "nom": a.nom,
            "nom_corrige": a.nom_corrige,
            "created_at": a.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            "updated_at": a.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
        })

    # Ecriture en cache
    try:
        await cache_set(cache_key_all, json.dumps(agences_payload))
    except Exception:
        pass

    return {"status":status.HTTP_200_OK,"results":len(agences_payload),"agences":agences_payload}


@agence_router.put("/{agence_id}")
async def update_agence(agence_id:int,agence_update : AgenceUpdateSchemas,db: Session = Depends(get_db_samaconso)):
    agence_db = db.query(Agence).filter(Agence.id == agence_id).first()
    if not agence_db:
        raise HTTPException(status_code=404, detail="Agence not found")
    for key, value in agence_update.model_dump(exclude_unset=True).items():
        setattr(agence_db, key, value)
    db.commit()
    db.refresh(agence_db)
    # Invalidation du cache list et clé par nom
    try:
        await cache_delete("agences:all")
        if agence_db.nom:
            await cache_delete(f"agence:name:{agence_db.nom}")
    except Exception:
        pass
    return agence_db


@agence_router.delete("/{agence_id}")
async def delete_role(agence_id:int,db: Session = Depends(get_db_samaconso)):
    agence_db = db.query(Agence).filter(Agence.id == agence_id).first()
    if not agence_db:
        raise HTTPException(status_code=404, detail="Agence not found")
    db.delete(agence_db)
    db.commit()
    # Invalidation du cache list et clé par nom
    try:
        await cache_delete("agences:all")
        if agence_db.nom:
            await cache_delete(f"agence:name:{agence_db.nom}")
    except Exception:
        pass
    return {"message": "Agence deleted successfully"}


@agence_router.get("/cache/inspect")
async def inspect_agence_cache():
    """Endpoint pour inspecter le cache Redis des agences"""
    try:
        from app.cache import get_redis
        client = get_redis()
        
        # Vérifier la connexion
        await client.ping()
        
        # Récupérer toutes les clés d'agences
        agence_keys = await client.keys("agence*")
        
        cache_info = {
            "redis_connected": True,
            "agence_cache_keys": [],
            "cache_contents": {}
        }
        
        for key in agence_keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            cache_info["agence_cache_keys"].append(key_str)
            
            # Récupérer le contenu de chaque clé
            value = await client.get(key_str)
            ttl = await client.ttl(key_str)
            
            if value:
                try:
                    parsed_value = json.loads(value)
                    cache_info["cache_contents"][key_str] = {
                        "data_preview": str(parsed_value)[:200] + "..." if len(str(parsed_value)) > 200 else parsed_value,
                        "ttl_seconds": ttl,
                        "size_bytes": len(value)
                    }
                except json.JSONDecodeError:
                    cache_info["cache_contents"][key_str] = {
                        "raw_data": str(value)[:200] + "..." if len(str(value)) > 200 else value,
                        "ttl_seconds": ttl,
                        "size_bytes": len(str(value))
                    }
        
        return {
            "status": 200,
            "message": "Cache inspection successful",
            "cache_info": cache_info
        }
        
    except Exception as e:
        return {
            "status": 500,
            "message": f"Cache inspection failed: {str(e)}",
            "cache_info": {"redis_connected": False, "error": str(e)}
        }