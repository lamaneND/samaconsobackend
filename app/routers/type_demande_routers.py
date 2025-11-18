from fastapi import APIRouter, Depends, HTTPException,status
import json
from sqlalchemy.orm import Session
from app.models.models import TypeDemande, TypeDemande
from app.schemas.type_demande_schemas import  TypeDemandeCreateSchema,TypeDemandeResponseSchema
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS

type_demande_router = APIRouter(prefix="/type_demande", tags=["TypeDemande"])

@type_demande_router.post("/")
async def create(data:TypeDemandeCreateSchema, db: Session = Depends(get_db_samaconso)):
    cache_key_by_label = f"type_demande:label:{data.label}"
    cached = await cache_get(cache_key_by_label)
    if cached:
        return {"status":status.HTTP_200_OK,"type_demande": json.loads(cached)}
    type_demande = TypeDemande(**data.model_dump())
    db.add(type_demande)
    db.commit()
    db.refresh(type_demande)
    payload = {
        "id": type_demande.id,
        "label": type_demande.label,
        "created_at": type_demande.created_at.strftime("%d/%m/%Y %H:%M:%S") if type_demande.created_at else None,
        "updated_at": type_demande.updated_at.strftime("%d/%m/%Y %H:%M:%S") if type_demande.updated_at else None,
    }
    try:
        await cache_set(CACHE_KEYS["TYPE_DEMANDE_BY_LABEL"].format(label=data.label), json.dumps(payload), ttl_seconds=7200)
        await cache_delete(CACHE_KEYS["TYPE_DEMANDE_ALL"])
    except Exception:
        pass
    return {"status":status.HTTP_200_OK,"type_demande":payload}

@type_demande_router.get("/")
async def list_all(db: Session = Depends(get_db_samaconso)):
    cache_key_all = "type_demande:all"
    try:
        cached = await cache_get(cache_key_all)
        if cached:
            data = json.loads(cached)
            return {"status":status.HTTP_200_OK,"type_demandes":data}
    except Exception:
        pass
    rows= db.query(TypeDemande).all()
    payload = []
    for r in rows:
        payload.append({
            "id": r.id,
            "label": r.label,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        })
    try:
        await cache_set(cache_key_all, json.dumps(payload))
    except Exception:
        pass
    return {"status":status.HTTP_200_OK,"type_demandes":payload}

@type_demande_router.get("/{type_id}")
def get_one(type_id:int,db: Session = Depends(get_db_samaconso)):
    type_demande= db.query(TypeDemande).filter(TypeDemande.id == type_id).first()
    return {"status":status.HTTP_200_OK,"type_demande":type_demande}

@type_demande_router.put("/{type_id}")
def update_etat(type_id:int,type_update : TypeDemandeCreateSchema,db: Session = Depends(get_db_samaconso)):
    type_demande = db.query(TypeDemande).filter(TypeDemande.id == type_id).first()
    if not type_demande:
        raise HTTPException(status_code=404, detail="Type demande not found")
    for key, value in type_update.model_dump(exclude_unset=True).items():
        setattr(type_demande, key, value)
    db.commit()
    db.refresh(type_demande)
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("type_demande:all"))
        if type_demande.label:
            loop.create_task(cache_delete(f"type_demande:label:{type_demande.label}"))
    except Exception:
        pass
    return {"status":status.HTTP_200_OK,"type_demande":type_demande}

@type_demande_router.delete("/{type_id}")
def delete_etat(type_id:int,db: Session = Depends(get_db_samaconso)):
    type_demande_db = db.query(TypeDemande).filter(TypeDemande.id == type_id).first()
    if not type_demande_db:
        raise HTTPException(status_code=404, detail="Type demande not found")
    db.delete(type_demande_db)
    db.commit()
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("type_demande:all"))
        if type_demande_db.label:
            loop.create_task(cache_delete(f"type_demande:label:{type_demande_db.label}"))
    except Exception:
        pass
    return {"message": "Etat deleted successfully"}