from fastapi import APIRouter, Depends, HTTPException,status
import json
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db_samaconso
from app.models.models import Role, User
from app.schemas.role_schemas import RoleCreateSchema, RoleListResponseSchema,RoleUpdateSchema
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS


role_router = APIRouter(prefix="/role",tags=["role"])


# Endpoint pour créer un role
@role_router.post("/")
async def create_role(role:RoleCreateSchema,db:Session=Depends(get_db_samaconso)):
    # cache by label to short-circuit duplicates
    cache_key_by_label = CACHE_KEYS["ROLE_BY_LABEL"].format(label=role.label)
    cached_role = await cache_get(cache_key_by_label)
    if cached_role:
        return {"status":status.HTTP_409_CONFLICT,"message":"Ce role existe déjà"}

    role_exist = db.query(Role).filter(Role.label==role.label).first()
    if role_exist:
        return {"status":status.HTTP_409_CONFLICT,"message":"Ce role existe déjà"}


    created_role = Role(label=role.label)
    db.add(created_role)
    db.commit()
    db.refresh(created_role)
    created_role.created_at = created_role.created_at.strftime("%d/%m/%Y %H:%M:%S")
    created_role.updated_at = created_role.updated_at.strftime("%d/%m/%Y %H:%M:%S")

    try:
        await cache_set(cache_key_by_label, json.dumps({
            "id": created_role.id,
            "label": created_role.label,
            "created_at": created_role.created_at,
            "updated_at": created_role.updated_at,
        }))
        await cache_delete(CACHE_KEYS["ROLES_ALL"])
    except Exception:
        pass

    return {"status":200,"role":created_role}

# Récupérer tous les rôles créés

@role_router.get("/")
async def get_all_roles(db: Session = Depends(get_db_samaconso)):
    """Récupérer tous les rôles avec cache longue durée (données quasi-statiques)"""
    cache_key_all = CACHE_KEYS["ROLES_ALL"]
    try:
        cached = await cache_get(cache_key_all)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "roles": data,
                "cache_hit": True
            }
    except Exception:
        pass

    roles = db.query(Role).all()
    roles_data = []
    for r in roles:
        roles_data.append({
            "id": r.id,
            "label": r.label,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
        })
    
    # Cache avec TTL long (2 heures) pour données quasi-statiques
    try:
        await cache_set(cache_key_all, json.dumps(roles_data), ttl_seconds=7200)  # CACHE_TTL["ROLES"]
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(roles_data),
        "roles": roles_data,
        "cache_hit": False
    }


@role_router.put("/{role_id}")
async def update_role(role_id:int,role_update : RoleUpdateSchema,db: Session = Depends(get_db_samaconso)):
    role_db = db.query(Role).filter(Role.id == role_id).first()
    if not role_db:
        raise HTTPException(status_code=404, detail="Role not found")
    for key, value in role_update.model_dump(exclude_unset=True).items():
        setattr(role_db, key, value)
    db.commit()
    db.refresh(role_db)
    # invalidate cache
    try:
        await cache_delete(CACHE_KEYS["ROLES_ALL"])
        if role_db.label:
            await cache_delete(CACHE_KEYS["ROLE_BY_LABEL"].format(label=role_db.label))
    except Exception:
        pass
    return role_db


@role_router.get("/{role_id}")
async def get_role_by_id(role_id: int, db: Session = Depends(get_db_samaconso)):
    """Récupérer un rôle par ID avec cache"""
    cache_key = CACHE_KEYS["ROLE_BY_ID"].format(id=role_id)
    try:
        cached = await cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "role": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rôle non trouvé")
    
    role_data = {
        "id": role.id,
        "label": role.label,
        "created_at": role.created_at.strftime("%d/%m/%Y %H:%M:%S"),
        "updated_at": role.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
    }
    
    try:
        await cache_set(cache_key, json.dumps(role_data), ttl_seconds=7200)  # TTL long pour les rôles
    except Exception:
        pass
    
    return {
        "status": 200,
        "role": role_data,
        "cache_hit": False
    }

@role_router.delete("/{role_id}")
async def delete_role(role_id: int, db: Session = Depends(get_db_samaconso)):
    """Supprimer un rôle avec invalidation cache complète"""
    role_db = db.query(Role).filter(Role.id == role_id).first()
    if not role_db:
        raise HTTPException(status_code=404, detail="Role not found")
    
    label = role_db.label
    db.delete(role_db)
    db.commit()
    
    # Invalidation complète du cache
    try:
        await cache_delete(CACHE_KEYS["ROLES_ALL"])
        await cache_delete(CACHE_KEYS["ROLE_BY_ID"].format(id=role_id))
        if label:
            await cache_delete(CACHE_KEYS["ROLE_BY_LABEL"].format(label=label))
    except Exception:
        pass
    
    return {
        "status": 200,
        "message": "Rôle supprimé avec succès"
    }

@role_router.get("/cache/inspect")
async def inspect_role_cache():
    """Inspecter l'état du cache des rôles"""
    from app.cache import redis_client
    
    try:
        if not redis_client:
            return {"status": 500, "message": "Redis non disponible"}
        
        # Rechercher toutes les clés de rôles
        role_patterns = ["roles:*", "role:*"]
        role_keys = []
        
        for pattern in role_patterns:
            keys = await redis_client.keys(pattern)
            role_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        
        cache_contents = {}
        for key in role_keys:
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
                "role_cache_keys": role_keys,
                "cache_contents": cache_contents
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "message": f"Erreur inspection cache: {str(e)}"
        }