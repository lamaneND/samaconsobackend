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
from app.tasks.batch_tasks import send_broadcast_notifications

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
    """Notification pour utilisateurs d'une agence - Version optimisée avec requêtes SQL groupées"""
    try:
        # Vérification agence
        agence = db.query(Agence).filter(Agence.id == data.id_agence).first()
        if not agence:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Agence introuvable"}

        # OPTIMISATION : Récupérer utilisateurs ET sessions en une seule requête avec jointure
        user_sessions_data = db.query(
            User.id.label('user_id'),
            UserSession.fcm_token
        ).outerjoin(
            UserSession,
            and_(
                UserSession.user_id == User.id,
                UserSession.is_active,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).filter(
            User.id_agence == data.id_agence
        ).all()

        if not user_sessions_data:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Aucun utilisateur dans cette agence"}

        # Organiser les données par utilisateur
        users_dict = {}
        for user_id, fcm_token in user_sessions_data:
            if user_id not in users_dict:
                users_dict[user_id] = set()
            if fcm_token:  # Peut être None si l'utilisateur n'a pas de session active
                users_dict[user_id].add(fcm_token)

        # OPTIMISATION : Créer toutes les notifications en un seul batch
        notifications_to_create = []
        for user_id in users_dict.keys():
            notifications_to_create.append(Notification(
                type_notification_id=data.type_notification_id,
                event_id=data.event_id,
                by_user_id=data.by_user_id,
                for_user_id=user_id,
                title=data.title,
                body=data.body,
                is_read=False
            ))

        db.bulk_save_objects(notifications_to_create)
        db.commit()

        # Préparer les notifications FCM pour envoi groupé
        notifications_batch = []
        for user_id, tokens in users_dict.items():
            for token in tokens:
                notifications_batch.append({
                    "token": token,
                    "title": data.title,
                    "body": data.body,
                    "user_id": user_id
                })

                # WebSocket pour chaque utilisateur
                try:
                    await notify_user_via_websocket(
                        user_id, data.title, data.body,
                        None, data.event_id  # notification_id = None car bulk insert
                    )
                except Exception:
                    continue

        # Lancer l'envoi groupé via Celery
        if notifications_batch:
            task_result = send_broadcast_notifications.delay({
                "title": data.title,
                "body": data.body,
                "event_id": data.event_id,
                "user_tokens": [{"user_id": uid, "tokens": list(tokens)} for uid, tokens in users_dict.items() if tokens],
                "chunk_size": 100
            })
            batch_task_id = str(task_result.id)
        else:
            batch_task_id = None

        return {
            "status": status.HTTP_201_CREATED,
            "message": f"Notifications créées pour {len(users_dict)} utilisateurs de l'agence {agence.nom}",
            "total_users": len(users_dict),
            "total_tokens": len(notifications_batch),
            "batch_task_id": batch_task_id,
            "agence": agence.nom,
            "processing": "asynchronous"
        }

    except Exception as e:
        logger.error(f"Agence notification failed: {str(e)}")
        db.rollback()
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification agence"}

@notification_router.post("/all_agences")
async def create_notification_for_all_agences(data: NotificationAllAgenceCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification pour toutes les agences - Version optimisée avec requêtes SQL groupées"""
    try:
        # OPTIMISATION : Une seule requête pour tous les utilisateurs de toutes les agences avec leurs sessions
        user_sessions_data = db.query(
            User.id.label('user_id'),
            User.id_agence,
            UserSession.fcm_token
        ).outerjoin(
            UserSession,
            and_(
                UserSession.user_id == User.id,
                UserSession.is_active,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).filter(
            User.id_agence.isnot(None)  # Utilisateurs ayant une agence
        ).all()

        if not user_sessions_data:
            return {"status": status.HTTP_404_NOT_FOUND, "message": "Aucun utilisateur dans les agences"}

        # Organiser les données par utilisateur
        users_dict = {}
        agences_set = set()
        for user_id, agence_id, fcm_token in user_sessions_data:
            if user_id not in users_dict:
                users_dict[user_id] = set()
            if fcm_token:
                users_dict[user_id].add(fcm_token)
            agences_set.add(agence_id)

        # OPTIMISATION : Créer toutes les notifications en un seul batch
        notifications_to_create = []
        for user_id in users_dict.keys():
            notifications_to_create.append(Notification(
                type_notification_id=data.type_notification_id,
                event_id=data.event_id,
                by_user_id=data.by_user_id,
                for_user_id=user_id,
                title=data.title,
                body=data.body,
                is_read=False
            ))

        if notifications_to_create:
            db.bulk_save_objects(notifications_to_create)
            db.commit()

        # Préparer les notifications FCM pour envoi groupé
        user_tokens = [
            {"user_id": uid, "tokens": list(tokens)}
            for uid, tokens in users_dict.items() if tokens
        ]

        # WebSocket pour chaque utilisateur (en parallèle)
        for user_id in users_dict.keys():
            try:
                await notify_user_via_websocket(
                    user_id, data.title, data.body,
                    None, data.event_id
                )
            except Exception:
                continue

        # Lancer l'envoi groupé via Celery
        if user_tokens:
            task_result = send_broadcast_notifications.delay({
                "title": data.title,
                "body": data.body,
                "event_id": data.event_id,
                "user_tokens": user_tokens,
                "chunk_size": 100
            })
            batch_task_id = str(task_result.id)
        else:
            batch_task_id = None

        # Récupérer les noms des agences pour le retour
        agences_names = db.query(Agence.nom).filter(Agence.id.in_(agences_set)).all()
        agences_list = [name[0] for name in agences_names]

        return {
            "status": status.HTTP_201_CREATED,
            "message": f"Notifications créées pour {len(users_dict)} utilisateurs dans {len(agences_set)} agences",
            "total_users": len(users_dict),
            "total_agences": len(agences_set),
            "total_tokens": sum(len(tokens) for tokens in users_dict.values()),
            "batch_task_id": batch_task_id,
            "agences_processed": agences_list,
            "processing": "asynchronous"
        }

    except Exception as e:
        logger.error(f"All agences notification failed: {str(e)}")
        db.rollback()
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification toutes agences"}

@notification_router.post("/all_users")
async def create_notification_for_all_users(data: NotificationAllUserCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification pour tous les utilisateurs - Version optimisée avec requête SQL groupée"""
    try:
        # Créer UNE SEULE notification globale (sans for_user_id spécifique)
        global_notification = Notification(
            type_notification_id=data.type_notification_id,
            event_id=data.event_id,
            by_user_id=data.by_user_id,
            for_user_id=None,  # NULL = notification globale pour tous
            title=data.title,
            body=data.body,
            is_read=False
        )

        try:
            db.add(global_notification)
            db.commit()
            db.refresh(global_notification)
            logger.info(f"Created global notification ID={global_notification.id} for broadcast")
        except Exception as e:
            logger.error(f"Failed to create global notification: {str(e)}")
            db.rollback()
            return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Failed to create global notification"}

        # OPTIMISATION : Une seule requête SQL avec jointure au lieu de N requêtes
        # Récupérer tous les utilisateurs actifs avec leurs sessions en UNE requête
        active_sessions = db.query(
            UserSession.user_id,
            UserSession.fcm_token
        ).join(
            User, UserSession.user_id == User.id
        ).filter(
            and_(
                User.is_activate,
                UserSession.is_active,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).all()

        if not active_sessions:
            return {
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Aucun utilisateur actif avec token FCM trouvé",
                "global_notification_id": global_notification.id
            }

        # Organiser les tokens par utilisateur avec déduplication
        user_tokens_dict = {}
        for user_id, fcm_token in active_sessions:
            if user_id not in user_tokens_dict:
                user_tokens_dict[user_id] = set()
            user_tokens_dict[user_id].add(fcm_token)

        # Convertir en format attendu par Celery
        user_tokens = [
            {"user_id": user_id, "tokens": list(tokens)}
            for user_id, tokens in user_tokens_dict.items()
        ]

        # Calculer les statistiques de déduplication
        total_unique_tokens = sum(len(tokens) for tokens in user_tokens_dict.values())
        total_sessions_before_dedup = len(active_sessions)
        duplicate_sessions = total_sessions_before_dedup - total_unique_tokens

        logger.info(f"Broadcast notification: {len(user_tokens)} users, {total_unique_tokens} unique tokens, {duplicate_sessions} duplicates removed")

        # Préparer les données pour Celery avec les tokens FCM
        broadcast_data = {
            "title": data.title,
            "body": data.body,
            "event_id": data.event_id,
            "user_tokens": user_tokens,
            "chunk_size": 100  # Augmenté de 50 à 100 pour plus d'efficacité
        }

        # Lancer la tâche Celery pour l'envoi FCM
        task_result = send_broadcast_notifications.delay(broadcast_data)

        return {
            "status": status.HTTP_202_ACCEPTED,
            "message": f"Notification broadcast créée pour {len(user_tokens)} utilisateurs",
            "batch_task_id": str(task_result.id),
            "total_users": len(user_tokens),
            "total_sessions_found": total_sessions_before_dedup,
            "total_unique_tokens": total_unique_tokens,
            "duplicate_sessions_removed": duplicate_sessions,
            "avg_tokens_per_user": round(total_unique_tokens / len(user_tokens), 2) if user_tokens else 0,
            "global_notification_id": global_notification.id,
            "processing": "asynchronous",
            "note": "Optimisé avec requête SQL groupée et Celery, tokens dédupliqués"
        }

    except Exception as e:
        logger.error(f"Broadcast notification failed: {str(e)}")
        return {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Erreur notification broadcast"}

@notification_router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Vérifier le statut d'une tâche Celery"""
    try:
        from app.celery_app import celery_app
        
        result = celery_app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "info": result.info,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None
        }
        
    except Exception as e:
        logger.error(f"Task status check failed: {str(e)}")
        return {
            "task_id": task_id,
            "status": "error",
            "message": str(e)
        }

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
            # Gestion du cas où updated_at pourrait ne pas exister (pour les anciens enregistrements)
            updated_at_str = ""
            if hasattr(notif, 'updated_at') and notif.updated_at:
                updated_at_str = notif.updated_at.strftime("%d/%m/%Y %H:%M:%S")
            else:
                updated_at_str = notif.created_at.strftime("%d/%m/%Y %H:%M:%S")
            
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
                "updated_at": updated_at_str
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

        # Récupérer les notifications spécifiques à l'utilisateur ET les notifications globales
        notifications = db.query(Notification).filter(
            or_(
                Notification.for_user_id == user_id,    # Notifications spécifiques
                Notification.for_user_id.is_(None)      # Notifications globales (for_user_id = NULL)
            )
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
                "is_global": notif.for_user_id is None,  # True si notification globale
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
        # Mise à jour de updated_at seulement si le champ existe
        if hasattr(notification, 'updated_at'):
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

# Fonction helper pour compatibilité
def for_user_notif(type_notification_id: int, title: str, body: str, for_user_id: int, event_id: int, db: Session):
    """Helper function simplifiée pour créer notification"""
    try:
        # Création notification
        notif = Notification(
            type_notification_id=type_notification_id,
            event_id=event_id,
            by_user_id=None,
            for_user_id=for_user_id,
            title=title,
            body=body,
            is_read=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Sessions actives
        user_sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == for_user_id,
                UserSession.is_active,
                UserSession.fcm_token.isnot(None)
            )
        ).all()

        # Envoi notifications
        task_ids = []
        unique_tokens = set()

        for session in user_sessions:
            if session.fcm_token:
                unique_tokens.add(session.fcm_token)

        for token in unique_tokens:
            try:
                task_result = send_single_notification.delay(token, title, body, event_id)
                task_ids.append(str(task_result.id))
            except Exception:
                continue

        return notif, task_ids

    except Exception as e:
        logger.error(f"for_user_notif failed: {str(e)}")
        return None, []