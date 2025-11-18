from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
import json
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, CACHE_KEYS
from app.database import get_db_samaconso
from app.models.models import User, UserSession
from app.schemas.user_schemas import UserResponseSchema, UserCreateSchema, UserUpdateSchema, UserLogoutSchema
from app.auth import create_access_token, get_current_user, get_password_hash
from app.cache import cache_get, cache_set, cache_delete
from app.simple_logging import get_simple_logger, log_error, log_security

logger = get_simple_logger(__name__)
user_router = APIRouter(prefix="/user", tags=["User"])

# Endpoint pour créer un utilisateur
@user_router.post("/")
async def create_user(user, db: Session = Depends(get_db_samaconso)):
    """Créer un utilisateur - Version simplifiée"""
    try:
        # Vérification si utilisateur existe
        user_exist = db.query(User).filter(User.phoneNumber == user.phoneNumber).first()
        if user_exist:
            return {"status": status.HTTP_409_CONFLICT, "message": "Cet utilisateur existe déjà."}

        # Hash des mots de passe
        if user.password: 
            user.password = get_password_hash(user.password)
        if user.codePin:
            user.codePin = get_password_hash(user.codePin)

        # Création utilisateur
        created_user = User(**user.model_dump())
        db.add(created_user)
        db.commit()
        db.refresh(created_user)
        
        # Formatage des dates
        created_user.created_at = created_user.created_at.strftime("%d/%m/%Y %H:%M:%S")
        created_user.updated_at = created_user.updated_at.strftime("%d/%m/%Y %H:%M:%S")
        
        # Génération token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": str(created_user.id)}, expires_delta=access_token_expires)
        
        # Cache simple (optionnel)
        try:
            user_payload = {
                "id": created_user.id,
                "firstName": created_user.firstName,
                "lastName": created_user.lastName,
                "phoneNumber": created_user.phoneNumber,
                "email": created_user.email,
                "login": created_user.login,
                "is_activate": created_user.is_activate,
                "ldap": created_user.ldap,
                "role": created_user.role,
                "id_agence": created_user.id_agence,
                "created_at": created_user.created_at,
                "updated_at": created_user.updated_at,
            }
            await cache_set(CACHE_KEYS["USER_BY_ID"].format(id=created_user.id), json.dumps(user_payload), ttl_seconds=900)
            await cache_delete(CACHE_KEYS["USERS_ALL"])
        except Exception:
            pass  # Cache non critique
        
        # Log seulement les événements critiques
        log_security("User created", created_user.id, details=f"Phone: {user.phoneNumber}")
        
        return {
            "status": 200,
            "utilisateur": created_user,
            "token": access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        log_error(logger, f"User creation failed for {user.phoneNumber}", e)
        raise HTTPException(status_code=500, detail="Failed to create user")

# Récupérer tous les utilisateurs
@user_router.get("/")
async def get_all_users(db: Session = Depends(get_db_samaconso)):
    """Récupérer tous les utilisateurs - Version simplifiée"""
    try:
        # Cache simple
        cache_key_all = CACHE_KEYS["USERS_ALL"]
        try:
            cached = await cache_get(cache_key_all)
            if cached:
                data = json.loads(cached)
                return {"status": 200, "results": len(data), "users": data, "cache_hit": True}
        except Exception:
            pass

        # Récupération en base
        utilisateurs = db.query(User).all()
        users_data = []
        for u in utilisateurs:
            users_data.append({
                "id": u.id,
                "firstName": u.firstName,
                "lastName": u.lastName,
                "phoneNumber": u.phoneNumber,
                "email": u.email,
                "login": u.login,
                "is_activate": u.is_activate,
                "ldap": u.ldap,
                "role": u.role,
                "id_agence": u.id_agence,
                "created_at": u.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "updated_at": u.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
            })
        
        # Cache simple
        try:
            await cache_set(cache_key_all, json.dumps(users_data), ttl_seconds=900)
        except Exception:
            pass

        return {"status": 200, "results": len(users_data), "users": users_data, "cache_hit": False}
        
    except Exception as e:
        log_error(logger, "Failed to get all users", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve users")

# Récupérer utilisateur par téléphone
@user_router.get("/phonenumber/{phonenumber}")
async def get_user_by_phonenumber(phonenumber: str, db: Session = Depends(get_db_samaconso)):
    """Récupérer utilisateur par téléphone - Version simplifiée"""
    try:
        # Cache simple
        cache_key = f"user:phone:{phonenumber}"
        try:
            cached = await cache_get(cache_key)
            if cached:
                return {'status': status.HTTP_200_OK, 'user': json.loads(cached)}
        except Exception:
            pass
            
        # Recherche en base
        utilisateur = db.query(User).filter(User.phoneNumber == phonenumber).first()
        if not utilisateur:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Cet utilisateur n'existe pas."}
        
        payload = {
            "id": utilisateur.id,
            "firstName": utilisateur.firstName,
            "lastName": utilisateur.lastName,
            "phoneNumber": utilisateur.phoneNumber,
            "email": utilisateur.email,
            "login": utilisateur.login,
            "is_activate": utilisateur.is_activate,
            "ldap": utilisateur.ldap,
            "role": utilisateur.role,
            "id_agence": utilisateur.id_agence,
            "created_at": utilisateur.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            "updated_at": utilisateur.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
        }
        
        # Cache simple
        try:
            await cache_set(cache_key, json.dumps(payload), ttl_seconds=900)
        except Exception:
            pass
            
        return {'status': status.HTTP_200_OK, 'user': payload}
        
    except Exception as e:
        log_error(logger, f"Failed to get user by phone {phonenumber}", e)
        raise HTTPException(status_code=500, detail="Internal server error")

# Vérifier existence téléphone
@user_router.get("/phonenumber/{phonenumber}/exist")
async def phonenumber_exist(phonenumber: str, db: Session = Depends(get_db_samaconso)):
    """Vérifier existence téléphone - Version simplifiée"""
    try:
        utilisateur = db.query(User).filter(User.phoneNumber == phonenumber).first()
        if not utilisateur:
            return {"status": status.HTTP_404_NOT_FOUND, "message": False}
        return {'status': status.HTTP_200_OK, 'message': True}
        
    except Exception as e:
        log_error(logger, f"Failed to check phone existence {phonenumber}", e)
        raise HTTPException(status_code=500, detail="Internal server error")

# Récupérer utilisateur par ID
@user_router.get("/{id}")
async def get_user_by_id(id: int, db: Session = Depends(get_db_samaconso)):
    """Récupérer utilisateur par ID - Version simplifiée"""
    try:
        # Cache simple
        cache_key = CACHE_KEYS["USER_BY_ID"].format(id=id)
        try:
            cached = await cache_get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # Recherche en base
        utilisateur = db.query(User).filter(User.id == id).first()
        if not utilisateur:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Cet utilisateur n'existe pas."}
        
        user_data = {
            "id": utilisateur.id,
            "firstName": utilisateur.firstName,
            "lastName": utilisateur.lastName,
            "phoneNumber": utilisateur.phoneNumber,
            "email": utilisateur.email,
            "login": utilisateur.login,
            "is_activate": utilisateur.is_activate,
            "ldap": utilisateur.ldap,
            "role": utilisateur.role,
            "id_agence": utilisateur.id_agence,
            "created_at": utilisateur.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            "updated_at": utilisateur.updated_at.strftime("%d/%m/%Y %H:%M:%S"),
        }
        
        # Cache simple
        try:
            await cache_set(cache_key, json.dumps(user_data), ttl_seconds=900)
        except Exception:
            pass
        
        return user_data
        
    except Exception as e:
        log_error(logger, f"Failed to get user by ID {id}", e)
        raise HTTPException(status_code=500, detail="Internal server error")

# Mise à jour utilisateur
@user_router.put("/{user_id}")
async def update_user(user_id: int, user: UserUpdateSchema, db: Session = Depends(get_db_samaconso)):
    """Mise à jour utilisateur - Version simplifiée"""
    try:
        existing_user = db.query(User).filter(User.id == user_id).first()
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Hash des mots de passe si fournis
        if hasattr(user, 'password') and user.password:
            user.password = get_password_hash(user.password)
            log_security("Password updated", user_id)
            
        if hasattr(user, 'codePin') and user.codePin:
            user.codePin = get_password_hash(user.codePin)
            log_security("PIN updated", user_id)
        
        # Mise à jour
        for key, value in user.model_dump(exclude_unset=True).items():
            setattr(existing_user, key, value)
        existing_user.updated_at = datetime.now()
        
        db.commit()
        db.refresh(existing_user)
        
        # Invalidation cache simple
        try:
            await cache_delete(CACHE_KEYS["USERS_ALL"])
            await cache_delete(CACHE_KEYS["USER_BY_ID"].format(id=user_id))
        except Exception:
            pass
        
        return existing_user
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, f"Failed to update user {user_id}", e)
        raise HTTPException(status_code=500, detail="Failed to update user")

# Suppression utilisateur
@user_router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db_samaconso)):
    """Suppression utilisateur - Version simplifiée"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        phone = user.phoneNumber
        db.delete(user)
        db.commit()
        
        # Log critique
        log_security("User deleted", user_id, details=f"Phone: {phone}")
        
        # Invalidation cache simple
        try:
            await cache_delete(CACHE_KEYS["USERS_ALL"])
            await cache_delete(CACHE_KEYS["USER_BY_ID"].format(id=user_id))
        except Exception:
            pass
            
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, f"Failed to delete user {user_id}", e)
        raise HTTPException(status_code=500, detail="Failed to delete user")

# Utilisateur connecté
@user_router.get("/connected/me", response_model=UserResponseSchema)
async def get_current_user_details(current_user: User = Depends(get_current_user)):
    """Détails utilisateur connecté - Version simplifiée"""
    try:
        current_user.created_at = current_user.created_at.strftime("%d/%m/%Y %H:%M:%S")
        current_user.updated_at = current_user.updated_at.strftime("%d/%m/%Y %H:%M:%S")
        return current_user
    except Exception as e:
        log_error(logger, "Failed to get current user details", e)
        raise HTTPException(status_code=500, detail="Failed to get user details")

# Déconnexion
@user_router.put("/logout/me")
async def logout_user(logout, db: Session = Depends(get_db_samaconso)):
    """Déconnexion utilisateur - Version simplifiée"""
    try:
        if not logout.fcmToken:
            return {"status": status.HTTP_400_BAD_REQUEST, "message": "Token FCM requis"}
        
        user_sessions = db.query(UserSession).filter(
            and_(UserSession.fcm_token == logout.fcmToken, UserSession.user_id == logout.user_id)
        ).all()
        
        if user_sessions:
            for user_session in user_sessions:
                user_session.is_active = False
                db.commit()
                db.refresh(user_session)
            
            # Invalidation cache sessions
            try:
                await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
                for user_session in user_sessions:
                    await cache_delete(CACHE_KEYS["USER_SESSION_BY_ID"].format(id=user_session.id))
            except Exception:
                pass
            
            log_security("User logout", logout.user_id)
            return {"status": status.HTTP_200_OK, "message": "utilisateur déconnecté"}
        
        return {"status": status.HTTP_200_OK, "message": "Aucune session active trouvée"}
        
    except Exception as e:
        log_error(logger, f"Logout failed for user {logout.user_id}", e)
        raise HTTPException(status_code=500, detail="Logout failed")

# Inspection cache (admin)
@user_router.get("/cache/inspect")
async def inspect_user_cache():
    """Inspection cache - Version simplifiée"""
    try:
        from app.cache import redis_client
        
        if not redis_client:
            return {"status": 500, "message": "Redis non disponible"}
        
        user_patterns = ["users:*", "user_sessions:*"]
        user_keys = []
        
        for pattern in user_patterns:
            keys = await redis_client.keys(pattern)
            user_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        
        cache_contents = {}
        for key in user_keys:
            try:
                ttl = await redis_client.ttl(key)
                content = await redis_client.get(key)
                if content:
                    cache_contents[key] = {
                        "ttl_seconds": ttl,
                        "size_bytes": len(content),
                        "has_content": True
                    }
            except Exception:
                cache_contents[key] = {"error": "Failed to read"}
        
        return {
            "status": 200,
            "message": "Cache inspection successful",
            "cache_info": {
                "redis_connected": True,
                "user_cache_keys": user_keys,
                "cache_contents": cache_contents,
                "security_note": "Contenu masqué pour la sécurité"
            }
        }
        
    except Exception as e:
        log_error(logger, "Cache inspection failed", e)
        return {"status": 500, "message": f"Erreur inspection cache: {str(e)}"}