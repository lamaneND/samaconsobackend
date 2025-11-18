from fastapi import APIRouter, Depends, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.database import get_db_samaconso
from app.models.models import Agence, Notification, User, UserCompteur, UserSession
from app.schemas.notification_schemas import (
    NotificationCreateSchema,
    NotificationUserAgenceCreateSchema,
    NotificationAllAgenceCreateSchema,
    NotificationAllUserCreateSchema,
    NotificationfromCompteurSchema
)
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS

# Imports Celery
from app.tasks.notification_tasks import send_single_notification, send_urgent_notification
from app.tasks.batch_tasks import send_batch_notifications, send_broadcast_notifications

# Import WebSocket functions
from app.routers.websocket_routers import notify_user_via_websocket

# Import Idempotency middleware
from app.middleware.idempotency import check_notification_idempotency, IdempotencyManager

import json
from datetime import datetime

# Logging simplifié - seulement les erreurs critiques
import logging
logger = logging.getLogger(__name__)

notification_router = APIRouter(prefix="/notifications", tags=["notifications"])

@notification_router.post("/")
async def create_notif(data: NotificationCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Création de notification - Version simplifiée sans logs verbeux"""
    try:
        # Vérification d'idempotence (empêcher les doublons)
        is_duplicate, idempotency_key = await check_notification_idempotency(
            user_id=data.for_user_id,
            title=data.title,
            body=data.body,
            notification_type=data.type_notification_id,
            event_id=data.event_id
        )

        if is_duplicate:
            # Récupérer le résultat en cache si disponible
            cached_result = await IdempotencyManager.get_cached_result(idempotency_key)
            if cached_result:
                return cached_result

            return {
                "status": status.HTTP_200_OK,
                "message": "Notification déjà traitée (doublon détecté)",
                "duplicate": True
            }

        # Sauvegarde en base de données
        by_user_id = data.by_user_id if data.by_user_id else None

        notif = Notification(
            type_notification_id=data.type_notification_id,
            event_id=data.event_id,
            by_user_id=by_user_id,
            for_user_id=data.for_user_id,
            title=data.title,
            body=data.body,
            is_read=data.is_read
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        
        # Récupération des sessions actives
        user_sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == data.for_user_id,
                UserSession.is_active,
                UserSession.fcm_token.isnot(None)
            )
        ).all()

        task_ids = []

        # DÉDUPLICATION par token FCM
        all_unique_tokens_single = set()

        if user_sessions:
            for session in user_sessions:
                if session.fcm_token:
                    all_unique_tokens_single.add(session.fcm_token)

            # Envoi aux tokens uniques via Celery
            for fcm_token in all_unique_tokens_single:
                try:
                    # Envoi notification mobile
                    task_result = send_single_notification.delay(
                        fcm_token, data.title, data.body, data.event_id
                    )
                    task_ids.append(str(task_result.id))
                    
                    # WebSocket si connecté
                    await notify_user_via_websocket(
                        data.for_user_id, data.title, data.body, 
                        notif.id, data.event_id
                    )
                    
                except Exception as e:
                    logger.error(f"Notification send failed: {str(e)}")
                    continue

        # Cache result pour idempotence
        result = {
            "status": status.HTTP_201_CREATED,
            "message": "notification créée et envoyée",
            "notification_id": notif.id,
            "task_ids": task_ids,
            "tokens_sent": len(all_unique_tokens_single)
        }
        
        await IdempotencyManager.cache_result(idempotency_key, result)
        return result

    except Exception as e:
        logger.error(f"Notification creation failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur création notification"}

@notification_router.post("/agence/users")
async def create_notification_for_user_in_agence(data: NotificationUserAgenceCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification pour utilisateurs d'une agence - Version simplifiée"""
    try:
        # Vérification agence
        agence = db.query(Agence).filter(Agence.id == data.id_agence).first()
        if not agence:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Agence introuvable"}

        # Utilisateurs de l'agence
        users_in_agence = db.query(User).filter(User.id_agence == data.id_agence).all()

        task_ids = []
        notifications_created = []

        for user in users_in_agence:
            try:
                # Création notification
                notif = Notification(
                    type_notification_id=data.type_notification_id,
                    event_id=data.event_id,
                    by_user_id=data.by_user_id,
                    for_user_id=user.id,
                    title=data.title,
                    body=data.body,
                    is_read=False
                )
                db.add(notif)
                db.commit()
                db.refresh(notif)
                notifications_created.append(notif.id)

                # Sessions actives
                user_sessions = db.query(UserSession).filter(
                    and_(
                        UserSession.user_id == user.id,
                        UserSession.is_active,
                        UserSession.fcm_token.isnot(None)
                    )
                ).all()

                # Envoi notifications
                unique_tokens = set()
                for session in user_sessions:
                    if session.fcm_token:
                        unique_tokens.add(session.fcm_token)

                for fcm_token in unique_tokens:
                    try:
                        task_result = send_single_notification.delay(
                            fcm_token, data.title, data.body, data.event_id
                        )
                        task_ids.append(str(task_result.id))
                        
                        await notify_user_via_websocket(
                            user.id, data.title, data.body, 
                            notif.id, data.event_id
                        )
                    except Exception:
                        continue

            except Exception as e:
                logger.error(f"Notification failed for user {user.id}: {str(e)}")
                continue

        return {
            "status": status.HTTP_201_CREATED,
            "message": f"Notifications créées pour {len(notifications_created)} utilisateurs",
            "notifications_created": notifications_created,
            "task_ids": task_ids,
            "agence": agence.nom
        }

    except Exception as e:
        logger.error(f"Agence notification failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification agence"}

@notification_router.post("/all_agences")
async def create_notification_for_all_agences(data: NotificationAllAgenceCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification pour toutes les agences - Version simplifiée"""
    try:
        # Toutes les agences
        all_agences = db.query(Agence).all()
        if not all_agences:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Aucune agence trouvée"}

        task_ids = []
        notifications_created = []
        agences_processed = []

        for agence in all_agences:
            try:
                users_in_agence = db.query(User).filter(User.id_agence == agence.id).all()
                
                for user in users_in_agence:
                    try:
                        # Création notification
                        notif = Notification(
                            type_notification_id=data.type_notification_id,
                            event_id=data.event_id,
                            by_user_id=data.by_user_id,
                            for_user_id=user.id,
                            title=data.title,
                            body=data.body,
                            is_read=False
                        )
                        db.add(notif)
                        db.commit()
                        db.refresh(notif)
                        notifications_created.append(notif.id)

                        # Sessions et envoi
                        user_sessions = db.query(UserSession).filter(
                            and_(
                                UserSession.user_id == user.id,
                                UserSession.is_active,
                                UserSession.fcm_token.isnot(None)
                            )
                        ).all()

                        unique_tokens = set()
                        for session in user_sessions:
                            if session.fcm_token:
                                unique_tokens.add(session.fcm_token)

                        for fcm_token in unique_tokens:
                            try:
                                task_result = send_single_notification.delay(
                                    fcm_token, data.title, data.body, data.event_id
                                )
                                task_ids.append(str(task_result.id))
                                
                                await notify_user_via_websocket(
                                    user.id, data.title, data.body, 
                                    notif.id, data.event_id
                                )
                            except Exception:
                                continue

                    except Exception as e:
                        logger.error(f"Notification failed for user {user.id}: {str(e)}")
                        continue

                agences_processed.append(agence.nom)

            except Exception as e:
                logger.error(f"Agence processing failed {agence.id}: {str(e)}")
                continue

        return {
            "status": status.HTTP_201_CREATED,
            "message": f"Notifications créées pour {len(agences_processed)} agences",
            "notifications_created": notifications_created,
            "task_ids": task_ids,
            "agences_processed": agences_processed
        }

    except Exception as e:
        logger.error(f"All agences notification failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification toutes agences"}

@notification_router.post("/all_users")
async def create_notification_for_all_users(data: NotificationAllUserCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification pour tous les utilisateurs - Version simplifiée"""
    try:
        # Tous les utilisateurs actifs
        all_users = db.query(User).filter(User.is_activate == True).all()
        if not all_users:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Aucun utilisateur actif trouvé"}

        # Utiliser batch processing pour performance
        task_result = send_broadcast_notifications.delay(
            title=data.title,
            body=data.body,
            event_id=data.event_id,
            type_notification_id=data.type_notification_id,
            by_user_id=data.by_user_id
        )

        return {
            "status": status.HTTP_202_ACCEPTED,
            "message": f"Notification broadcast lancée pour {len(all_users)} utilisateurs",
            "batch_task_id": str(task_result.id),
            "total_users": len(all_users)
        }

    except Exception as e:
        logger.error(f"Broadcast notification failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification broadcast"}

@notification_router.get("/")
async def get_all_notifications(db: Session = Depends(get_db_samaconso)):
    """Récupérer toutes les notifications - Version simplifiée"""
    try:
        cache_key = CACHE_KEYS["NOTIFICATIONS_ALL"]
        
        # Tentative cache
        try:
            cached = await cache_get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # Base de données
        notifications = db.query(Notification).order_by(Notification.created_at.desc()).all()
        
        notifications_data = []
        for notif in notifications:
            notifications_data.append({
                "id": notif.id,
                "type_notification_id": notif.type_notification_id,
                "event_id": notif.event_id,
                "by_user_id": notif.by_user_id,
                "for_user_id": notif.for_user_id,
                "title": notif.title,
                "body": notif.body,
                "is_read": notif.is_read,
                "created_at": notif.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "updated_at": notif.updated_at.strftime("%d/%m/%Y %H:%M:%S")
            })

        result = {
            "status": status.HTTP_200_OK,
            "results": len(notifications_data),
            "notifications": notifications_data
        }

        # Cache simple
        try:
            await cache_set(cache_key, json.dumps(result), ttl_seconds=300)
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"Get all notifications failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur récupération notifications"}

@notification_router.get("/user/{user_id}")
async def get_notifications_for_user(user_id: int, db: Session = Depends(get_db_samaconso)):
    """Notifications pour utilisateur - Version simplifiée"""
    try:
        cache_key = f"notifications:user:{user_id}"
        
        # Tentative cache
        try:
            cached = await cache_get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        notifications = db.query(Notification).filter(
            Notification.for_user_id == user_id
        ).order_by(Notification.created_at.desc()).all()

        notifications_data = []
        for notif in notifications:
            notifications_data.append({
                "id": notif.id,
                "type_notification_id": notif.type_notification_id,
                "event_id": notif.event_id,
                "title": notif.title,
                "body": notif.body,
                "is_read": notif.is_read,
                "created_at": notif.created_at.strftime("%d/%m/%Y %H:%M:%S")
            })

        result = {
            "status": status.HTTP_200_OK,
            "user_id": user_id,
            "results": len(notifications_data),
            "notifications": notifications_data
        }

        # Cache simple
        try:
            await cache_set(cache_key, json.dumps(result), ttl_seconds=180)
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"Get user notifications failed for user {user_id}: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur récupération notifications utilisateur"}

@notification_router.put("/{notification_id}/read")
async def mark_notification_as_read(notification_id: int, db: Session = Depends(get_db_samaconso)):
    """Marquer notification comme lue - Version simplifiée"""
    try:
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Notification introuvable"}

        notification.is_read = True
        notification.updated_at = datetime.now()
        db.commit()

        # Invalidation cache
        try:
            await cache_delete(CACHE_KEYS["NOTIFICATIONS_ALL"])
            await cache_delete(f"notifications:user:{notification.for_user_id}")
        except Exception:
            pass

        return {
            "status": status.HTTP_200_OK,
            "message": "Notification marquée comme lue",
            "notification_id": notification_id
        }

    except Exception as e:
        logger.error(f"Mark notification read failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur marquage notification"}

@notification_router.delete("/{notification_id}")
async def delete_notification(notification_id: int, db: Session = Depends(get_db_samaconso)):
    """Supprimer notification - Version simplifiée"""
    try:
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Notification introuvable"}

        user_id = notification.for_user_id
        db.delete(notification)
        db.commit()

        # Invalidation cache
        try:
            await cache_delete(CACHE_KEYS["NOTIFICATIONS_ALL"])
            await cache_delete(f"notifications:user:{user_id}")
        except Exception:
            pass

        # Log critique pour suppression
        logger.warning(f"Notification deleted: ID={notification_id}, User={user_id}")

        return {
            "status": status.HTTP_200_OK,
            "message": "Notification supprimée",
            "notification_id": notification_id
        }

    except Exception as e:
        logger.error(f"Delete notification failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur suppression notification"}

@notification_router.post("/compteur")
async def create_notification_from_compteur(data: NotificationfromCompteurSchema, db: Session = Depends(get_db_samaconso)):
    """Notification depuis compteur - Version simplifiée"""
    try:
        # Récupérer l'utilisateur associé au compteur
        user_compteur = db.query(UserCompteur).filter(
            UserCompteur.numero_compteur == data.numero_compteur
        ).first()
        
        if not user_compteur:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Compteur non associé à un utilisateur"}

        # Créer la notification
        notif = Notification(
            type_notification_id=data.type_notification_id,
            event_id=data.event_id,
            for_user_id=user_compteur.user_id,
            title=data.title,
            body=data.body,
            is_read=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Sessions actives pour envoi
        user_sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_compteur.user_id,
                UserSession.is_active,
                UserSession.fcm_token.isnot(None)
            )
        ).all()

        task_ids = []
        unique_tokens = set()

        for session in user_sessions:
            if session.fcm_token:
                unique_tokens.add(session.fcm_token)

        # Envoi urgent pour notifications compteur
        for fcm_token in unique_tokens:
            try:
                task_result = send_urgent_notification.delay(
                    fcm_token, data.title, data.body, data.event_id
                )
                task_ids.append(str(task_result.id))
                
                await notify_user_via_websocket(
                    user_compteur.user_id, data.title, data.body, 
                    notif.id, data.event_id
                )
            except Exception:
                continue

        # Log critique pour notifications compteur
        logger.warning(f"Compteur notification: User={user_compteur.user_id}, Compteur={data.numero_compteur}")

        return {
            "status": status.HTTP_201_CREATED,
            "message": "Notification compteur créée et envoyée",
            "notification_id": notif.id,
            "user_id": user_compteur.user_id,
            "task_ids": task_ids,
            "tokens_sent": len(unique_tokens)
        }

    except Exception as e:
        logger.error(f"Compteur notification failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification compteur"}