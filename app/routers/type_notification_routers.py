from fastapi import APIRouter, Depends, HTTPException,status
import json
from sqlalchemy.orm import Session
from app.models.models import TypeNotification
from app.schemas.type_notification_schemas import  TypeNotificationCreateSchema,TypeNotificationResponseSchema
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS

type_notification_router = APIRouter(prefix="/type_notification", tags=["TypeNotification"])

@type_notification_router.post("/")
async def create(data:TypeNotificationCreateSchema, db: Session = Depends(get_db_samaconso)):
    cache_key_by_label = f"type_notification:label:{data.label}"
    cached = await cache_get(cache_key_by_label)
    if cached:
        return {"status":status.HTTP_200_OK,"type_notification": json.loads(cached)}
    type_notification = TypeNotification(**data.model_dump())
    db.add(type_notification)
    db.commit()
    db.refresh(type_notification)
    payload = {
        "id": type_notification.id,
        "label": type_notification.label,
        "created_at": type_notification.created_at.strftime("%d/%m/%Y %H:%M:%S") if type_notification.created_at else None,
        "updated_at": type_notification.updated_at.strftime("%d/%m/%Y %H:%M:%S") if type_notification.updated_at else None,
    }
    try:
        await cache_set(CACHE_KEYS["TYPE_NOTIFICATION_BY_LABEL"].format(label=data.label), json.dumps(payload), ttl_seconds=7200)
        await cache_delete(CACHE_KEYS["TYPE_NOTIFICATION_ALL"])
    except Exception:
        pass
    return {"status":status.HTTP_200_OK,"type_notification":payload}

@type_notification_router.get("/")
async def list_all(db: Session = Depends(get_db_samaconso)):
    cache_key_all = "type_notification:all"
    try:
        cached = await cache_get(cache_key_all)
        if cached:
            data = json.loads(cached)
            return {"status":status.HTTP_200_OK,"type_notifications":data}
    except Exception:
        pass
    rows= db.query(TypeNotification).all()
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
    return {"status":status.HTTP_200_OK,"type_notifications":payload}

@type_notification_router.get("/{type_id}")
def get_one(type_id:int,db: Session = Depends(get_db_samaconso)):
    type_notification= db.query(TypeNotification).filter(TypeNotification.id == type_id).first()
    return {"status":status.HTTP_200_OK,"type_notification":type_notification}

@type_notification_router.put("/{type_id}")
def update_etat(type_id:int,type_update : TypeNotificationCreateSchema,db: Session = Depends(get_db_samaconso)):
    type_notification = db.query(TypeNotification).filter(TypeNotification.id == type_id).first()
    if not type_notification:
        raise HTTPException(status_code=404, detail="Type Notification not found")
    for key, value in type_update.model_dump(exclude_unset=True).items():
        setattr(type_notification, key, value)
    db.commit()
    db.refresh(type_notification)
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("type_notification:all"))
        if type_notification.label:
            loop.create_task(cache_delete(f"type_notification:label:{type_notification.label}"))
    except Exception:
        pass
    return {"status":status.HTTP_200_OK,"type_notification":type_notification}

@type_notification_router.delete("/{type_id}")
def delete_etat(type_id:int,db: Session = Depends(get_db_samaconso)):
    type_Notification_db = db.query(TypeNotification).filter(TypeNotification.id == type_id).first()
    if not type_Notification_db:
        raise HTTPException(status_code=404, detail="Type Notification not found")
    db.delete(type_Notification_db)
    db.commit()
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("type_notification:all"))
        if type_Notification_db.label:
            loop.create_task(cache_delete(f"type_notification:label:{type_Notification_db.label}"))
    except Exception:
        pass
    return {"message": "Etat deleted successfully"}