

from fastapi import status, APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.models import UserSession
from app.schemas.user_session_schemas import (
    UserSessionCreateSchema, 
    UserSessionUpdateSchema
)
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS, CACHE_TTL
import json

user_session_router = APIRouter(prefix="/user-sessions", tags=["User Sessions"])

@user_session_router.get("/cache/inspect")
async def inspect_cache():
    """🔍 Inspection du cache pour User Sessions"""
    cache_info = {
        "entity": "user_sessions",
        "cache_keys": {
            "all_sessions": CACHE_KEYS["USER_SESSIONS_ALL"],
            "session_by_id": CACHE_KEYS["USER_SESSION_BY_ID"].format(id="{session_id}"),
        },
        "ttl_config": {
            "sessions": f"{CACHE_TTL['USER_SESSIONS']}s ({CACHE_TTL['USER_SESSIONS']//60}min)",
        },
        "security_note": "⚠️ Cache avec tokens complets pour compatibilité - TTL court (5min)"
    }
    
    # Test de quelques clés courantes
    active_keys = []
    test_keys = [
        CACHE_KEYS["USER_SESSIONS_ALL"],
        CACHE_KEYS["USER_SESSION_BY_ID"].format(id="1"),
        CACHE_KEYS["USER_SESSION_BY_ID"].format(id="2")
    ]
    
    for key in test_keys:
        try:
            cached = await cache_get(key)
            if cached:
                active_keys.append({
                    "key": key,
                    "size": len(cached),
                    "type": "JSON string"
                })
        except Exception:
            pass
    
    cache_info["active_keys"] = active_keys
    cache_info["total_active"] = len(active_keys)
    
    return cache_info

@user_session_router.post("/")
async def create_user_session(session: UserSessionCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Créer une session utilisateur avec déduplication de tokens FCM"""
    
    # 1. Désactiver toutes les sessions existantes avec le même token/utilisateur (BATCH)
    existing_sessions = db.query(UserSession).filter(
        and_(
            UserSession.fcm_token == session.fcm_token,
            UserSession.user_id == session.user_id,
            UserSession.is_active
        )
    ).all()
    
    # Désactivation en batch (plus efficace)
    for user_session in existing_sessions:
        user_session.is_active = False
    
    # 2. Créer la nouvelle session
    db_session = UserSession(**session.model_dump())
    db.add(db_session)
    
    # 3. Commit unique pour toutes les modifications
    db.commit()
    db.refresh(db_session)
    
    # 4. Invalidation du cache
    try:
        await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
    except Exception:
        pass
    
    return db_session

@user_session_router.get("/")
async def get_all_user_sessions(db: Session = Depends(get_db_samaconso)):
    key_all = CACHE_KEYS["USER_SESSIONS_ALL"]
    try:
        cached = await cache_get(key_all)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    rows = db.query(UserSession).all()
    payload = []
    for s in rows:
        payload.append({
            "id": s.id,
            "user_id": s.user_id,
            "device_model": s.device_model,
            "fcm_token": s.fcm_token,  # Token complet pour compatibilité
            "is_active": s.is_active,
            "last_login": s.last_login.strftime("%d/%m/%Y %H:%M:%S") if s.last_login else None,
        })
    try:
        await cache_set(key_all, json.dumps(payload), ttl_seconds=CACHE_TTL["USER_SESSIONS"])
    except Exception:
        pass
    return payload

@user_session_router.get("/{session_id}")
async def get_user_session(session_id: int, db: Session = Depends(get_db_samaconso)):
    key = CACHE_KEYS["USER_SESSION_BY_ID"].format(id=session_id)
    try:
        cached = await cache_get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = {
        "id": session.id,
        "user_id": session.user_id,
        "device_model": session.device_model,
        "fcm_token": session.fcm_token,  # Token complet pour compatibilité
        "is_active": session.is_active,
        "last_login": session.last_login.strftime("%d/%m/%Y %H:%M:%S") if session.last_login else None,
    }
    
    try:
        await cache_set(key, json.dumps(session_data), ttl_seconds=CACHE_TTL["USER_SESSIONS"])
    except Exception:
        pass
    
    return session_data

@user_session_router.put("/{session_id}")
async def update_user_session(session_id: int, updates: UserSessionUpdateSchema, db: Session = Depends(get_db_samaconso)):
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    
    # Invalidation du cache
    try:
        await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
        await cache_delete(CACHE_KEYS["USER_SESSION_BY_ID"].format(id=session_id))
    except Exception:
        pass
    
    return session

@user_session_router.delete("/{session_id}")
async def delete_user_session(session_id: int, db: Session = Depends(get_db_samaconso)):
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    
    # Invalidation du cache
    try:
        await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
        await cache_delete(CACHE_KEYS["USER_SESSION_BY_ID"].format(id=session_id))
    except Exception:
        pass
    
    return {"detail": "Session deleted"}


@user_session_router.post("/register-token", status_code=status.HTTP_201_CREATED)
async def register_fcm_token(
    payload: UserSessionCreateSchema,
    db: Session = Depends(get_db_samaconso)
):
    """
    Enregistrer un token FCM avec déduplication intelligente et limite de sessions

    OPTIMISATIONS:
    - Réutilise session existante si même token
    - Désactive tokens dupliqués sur AUTRES utilisateurs
    - Limite à MAX_SESSIONS_PER_USER (défaut: 2)
    - Nettoie sessions > 30 jours automatiquement
    - Gestion robuste des erreurs de connexion DB
    """
    from sqlalchemy.exc import OperationalError, DisconnectionError
    from datetime import timedelta
    import time

    MAX_SESSIONS_PER_USER = 2  # Configurable: max sessions actives par utilisateur
    SESSION_CLEANUP_DAYS = 30  # Nettoyer sessions > 30 jours
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconde

    for attempt in range(MAX_RETRIES):
        try:
            # ========== ÉTAPE 1: Nettoyer les sessions de TOUS les utilisateurs ayant ce token ==========
            # Important: Un token FCM appartient à UN SEUL appareil, mais peut être réutilisé
            # si l'utilisateur se déconnecte et qu'un autre se connecte sur le même appareil
            sessions_with_same_token = db.query(UserSession).filter(
                and_(
                    UserSession.fcm_token == payload.fcm_token,
                    UserSession.is_active.is_(True)
                )
            ).all()

            # Désactiver toutes les sessions utilisant ce token (pour TOUS les utilisateurs)
            for session in sessions_with_same_token:
                session.is_active = False

            # ========== ÉTAPE 2: Vérifier si session existe déjà pour CET utilisateur ==========
            existing_session = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == payload.user_id,
                    UserSession.fcm_token == payload.fcm_token
                )
            ).first()

            if existing_session:
                # Réactiver et mettre à jour la session existante
                existing_session.device_model = payload.device_model
                existing_session.last_login = datetime.now()
                existing_session.is_active = True
                db.commit()
                db.refresh(existing_session)

                # Invalidation du cache
                try:
                    await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
                    await cache_delete(CACHE_KEYS["USER_SESSION_BY_ID"].format(id=existing_session.id))
                except Exception:
                    pass

                return {
                    "detail": "Session réactivée",
                    "id": existing_session.id,
                    "reused": True
                }

            # ========== ÉTAPE 3: Limiter le nombre de sessions actives par utilisateur ==========
            active_user_sessions = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == payload.user_id,
                    UserSession.is_active.is_(True)
                )
            ).order_by(UserSession.last_login.desc()).all()

            # Si on a déjà MAX_SESSIONS_PER_USER sessions, désactiver les plus anciennes
            if len(active_user_sessions) >= MAX_SESSIONS_PER_USER:
                # Garder les (MAX_SESSIONS_PER_USER - 1) plus récentes, désactiver le reste
                sessions_to_deactivate = active_user_sessions[MAX_SESSIONS_PER_USER - 1:]
                for old_session in sessions_to_deactivate:
                    old_session.is_active = False

            # ========== ÉTAPE 4: Nettoyer automatiquement les vieilles sessions (bonus) ==========
            cutoff_date = datetime.now() - timedelta(days=SESSION_CLEANUP_DAYS)

            old_sessions = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == payload.user_id,
                    UserSession.last_login < cutoff_date,
                    UserSession.is_active.is_(True)
                )
            ).all()

            old_sessions_count = len(old_sessions)
            for old_session in old_sessions:
                old_session.is_active = False

            # ========== ÉTAPE 5: Créer la nouvelle session ==========
            new_session = UserSession(
                user_id=payload.user_id,
                device_model=payload.device_model,
                fcm_token=payload.fcm_token,
                last_login=datetime.now(),
                is_active=True
            )
            db.add(new_session)
            db.commit()
            db.refresh(new_session)

            # ========== ÉTAPE 6: Invalidation du cache ==========
            try:
                await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
            except Exception:
                pass

            return {
                "status": status.HTTP_201_CREATED,
                "detail": "Token enregistré avec succès",
                "id": new_session.id,
                "reused": False,
                "sessions_cleaned": {
                    "old_sessions_deactivated": old_sessions_count,
                    "limit_enforced": len(active_user_sessions) >= MAX_SESSIONS_PER_USER,
                    "duplicate_tokens_cleaned": len(sessions_with_same_token)
                }
            }

        except (OperationalError, DisconnectionError) as e:
            # Gestion des erreurs de connexion DB
            db.rollback()
            
            if attempt < MAX_RETRIES - 1:
                # Attendre avant le prochain essai
                time.sleep(RETRY_DELAY * (attempt + 1))  # Backoff exponentiel
                continue
            else:
                # Dernier essai échoué
                raise HTTPException(
                    status_code=503,
                    detail=f"Erreur de connexion à la base de données après {MAX_RETRIES} tentatives: {str(e)}"
                )
                
        except Exception as e:
            # Autres erreurs
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de l'enregistrement du token FCM: {str(e)}"
            )


@user_session_router.post("/logout")
async def logout_user_session(
    user_id: int,
    fcm_token: str = None,
    db: Session = Depends(get_db_samaconso)
):
    """
    Déconnexion utilisateur - Désactive la session avec le token FCM fourni

    Args:
        user_id: ID de l'utilisateur
        fcm_token: Token FCM à désactiver (optionnel, si non fourni désactive toutes les sessions)

    Returns:
        Confirmation de déconnexion avec nombre de sessions désactivées
    """
    try:
        if fcm_token:
            # Déconnexion d'un appareil spécifique
            session_to_logout = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.fcm_token == fcm_token,
                    UserSession.is_active
                )
            ).first()

            if session_to_logout:
                session_to_logout.is_active = False
                db.commit()

                # Invalidation du cache
                try:
                    await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
                    await cache_delete(CACHE_KEYS["USER_SESSION_BY_ID"].format(id=session_to_logout.id))
                except Exception:
                    pass

                return {
                    "status": "success",
                    "message": "Déconnexion réussie",
                    "sessions_deactivated": 1,
                    "device": session_to_logout.device_model
                }
            else:
                return {
                    "status": "not_found",
                    "message": "Session non trouvée ou déjà inactive",
                    "sessions_deactivated": 0
                }
        else:
            # Déconnexion de TOUS les appareils de l'utilisateur
            all_user_sessions = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active
                )
            ).all()

            deactivated_count = len(all_user_sessions)
            for session in all_user_sessions:
                session.is_active = False

            db.commit()

            # Invalidation du cache
            try:
                await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
            except Exception:
                pass

            return {
                "status": "success",
                "message": f"Déconnexion de tous les appareils ({deactivated_count} sessions)",
                "sessions_deactivated": deactivated_count
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la déconnexion: {str(e)}",
            "sessions_deactivated": 0
        }


@user_session_router.get("/debug/tokens/duplicates")
async def debug_duplicate_tokens(db: Session = Depends(get_db_samaconso)):
    """Debug: Identifier les tokens FCM dupliqués entre utilisateurs"""
    try:
        # Récupérer toutes les sessions actives
        sessions = db.query(UserSession).filter(UserSession.is_active.is_(True)).all()
        
        # Grouper par token FCM
        token_users = {}
        for session in sessions:
            if session.fcm_token:
                if session.fcm_token not in token_users:
                    token_users[session.fcm_token] = []
                token_users[session.fcm_token].append({
                    "user_id": session.user_id,
                    "session_id": session.id,
                    "device_model": session.device_model,
                    "last_login": session.last_login.isoformat() if session.last_login else None
                })
        
        # Identifier les doublons
        duplicates = {
            token: users for token, users in token_users.items() 
            if len(users) > 1
        }
        
        total_sessions = len(sessions)
        total_unique_tokens = len(token_users)
        duplicate_count = sum(len(users) - 1 for users in duplicates.values())
        
        return {
            "status": 200,
            "summary": {
                "total_active_sessions": total_sessions,
                "unique_fcm_tokens": total_unique_tokens,
                "tokens_with_duplicates": len(duplicates),
                "total_duplicate_sessions": duplicate_count,
                "efficiency": f"{round((1 - duplicate_count / total_sessions) * 100, 1)}% efficient"
            },
            "duplicate_tokens": {
                f"{token[:30]}...": users 
                for token, users in list(duplicates.items())[:5]  # Premier 5 exemples
            } if duplicates else {},
            "recommendations": [
                "✅ La déduplication FCM globale résout ces doublons",
                "🧹 Nettoyer les sessions inactives périodiquement", 
                "📊 Surveiller ce ratio pour optimiser les performances"
            ]
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }


@user_session_router.get("/debug/user/{user_id}/sessions")
async def debug_user_sessions(user_id: int, db: Session = Depends(get_db_samaconso)):
    """Debug: Voir toutes les sessions d'un utilisateur spécifique"""
    try:
        sessions = db.query(UserSession).filter(UserSession.user_id == user_id).all()
        
        if not sessions:
            return {
                "status": 404,
                "message": f"Aucune session trouvée pour l'utilisateur {user_id}"
            }
        
        session_details = []
        active_count = 0
        fcm_tokens = set()
        
        for session in sessions:
            if session.is_active:
                active_count += 1
            if session.fcm_token:
                fcm_tokens.add(session.fcm_token)
                
            session_details.append({
                "id": session.id,
                "is_active": session.is_active,
                "device_model": session.device_model,
                "fcm_token_preview": session.fcm_token[:30] + "..." if session.fcm_token else None,
                "last_login": session.last_login.isoformat() if session.last_login else None,
                "created_at": session.created_at.isoformat() if hasattr(session, 'created_at') and session.created_at else None
            })
        
        return {
            "status": 200,
            "user_id": user_id,
            "summary": {
                "total_sessions": len(sessions),
                "active_sessions": active_count,
                "inactive_sessions": len(sessions) - active_count,
                "unique_fcm_tokens": len(fcm_tokens)
            },
            "sessions": session_details,
            "warnings": [
                f"⚠️ {active_count} sessions actives - optimalement 1 seule" if active_count > 1 else None,
                f"⚠️ {len(fcm_tokens)} tokens FCM différents" if len(fcm_tokens) > 1 else None
            ]
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }


@user_session_router.post("/cleanup/inactive")
async def cleanup_inactive_sessions(db: Session = Depends(get_db_samaconso)):
    """Nettoyer les sessions inactives (maintenance)"""
    try:
        # Compter les sessions inactives
        inactive_sessions = db.query(UserSession).filter(UserSession.is_active.is_(False)).all()
        inactive_count = len(inactive_sessions)
        
        if inactive_count == 0:
            return {
                "status": 200,
                "message": "Aucune session inactive à nettoyer",
                "deleted_count": 0
            }
        
        # Supprimer les sessions inactives
        db.query(UserSession).filter(UserSession.is_active.is_(False)).delete()
        db.commit()
        
        # Invalidation du cache
        try:
            await cache_delete(CACHE_KEYS["USER_SESSIONS_ALL"])
        except Exception:
            pass
        
        return {
            "status": 200,
            "message": f"Nettoyage terminé : {inactive_count} sessions supprimées",
            "deleted_count": inactive_count,
            "performance_impact": f"Réduction de {inactive_count} enregistrements en base"
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }
