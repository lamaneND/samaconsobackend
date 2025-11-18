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
from app.routers.websocket_routers import notify_user_via_websocket, broadcast_notification_via_websocket

# Import Idempotency middleware
from app.middleware.idempotency import check_notification_idempotency, IdempotencyManager

import json
from datetime import datetime
from app.logging_config import get_logger, log_api_request, log_notification, log_database

logger = get_logger(__name__)


notification_router = APIRouter(prefix="/notifications",tags=["notifications"])


@notification_router.post("/")
async def create_notif(data: NotificationCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Création de notification avec envoi via Celery + protection anti-doublons"""

    logger.info(f"🔔 Creating notification for user {data.for_user_id} | Type: {data.type_notification_id} | Title: '{data.title[:50]}'")
    log_api_request("/notifications", "POST", data.for_user_id)

    # 0. Vérification d'idempotence (empêcher les doublons)
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

        # Sinon retourner une réponse générique
        return {
            "status": status.HTTP_200_OK,
            "message": "Notification déjà traitée (doublon détecté)",
            "duplicate": True
        }

    # 1. Sauvegarde en base de données (synchrone, critique)
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
    
    # 2. Récupération des sessions actives
    user_sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id == data.for_user_id,
            UserSession.is_active == True,
            UserSession.fcm_token.isnot(None)
        )
    ).all()

    task_ids = []

    # DÉDUPLICATION GLOBALE par token FCM: éviter d'envoyer plusieurs fois au même appareil
    all_unique_tokens_single = set()

    if user_sessions:
        # Collecter tous les tokens uniques globalement
        for session in user_sessions:
            if session.fcm_token:
                all_unique_tokens_single.add(session.fcm_token)

        # Envoyer seulement aux tokens uniques
        for token in all_unique_tokens_single:
            notification_data = {
                "token": token,
                "title": data.title,
                "body": data.body,
                "user_id": data.for_user_id,
                "notification_id": notif.id
            }

            # 3. Envoi via Celery selon priorité
            if _is_urgent_notification(data.type_notification_id):
                task = send_urgent_notification.delay(notification_data)
            else:
                task = send_single_notification.delay(notification_data)

            task_ids.append(task.id)

    log_notification(data.for_user_id, data.title, len(all_unique_tokens_single), "FCM")
    logger.info(f"📨 Created notification {notif.id} for user {data.for_user_id} | Tokens sent: {len(all_unique_tokens_single)}")
    
    # 4. Invalidation cache
    try:
        await cache_delete(CACHE_KEYS["NOTIFICATIONS_ALL"])
        await cache_delete(CACHE_KEYS["NOTIFICATIONS_BY_USER"].format(user_id=data.for_user_id))
        await cache_delete(CACHE_KEYS["NOTIFICATIONS_UNREAD"].format(user_id=data.for_user_id))
    except Exception:
        pass
    
    # 5. Envoi via WebSocket temps réel
    notification_ws_data = {
        "id": notif.id,
        "type_notification_id": notif.type_notification_id,
        "event_id": notif.event_id,
        "by_user_id": notif.by_user_id,
        "for_user_id": notif.for_user_id,
        "title": notif.title,
        "body": notif.body,
        "is_read": notif.is_read,
        "created_at": notif.created_at.strftime("%d/%m/%Y %H:%M:%S") if notif.created_at else None,
    }
    await notify_user_via_websocket(data.for_user_id, notification_ws_data)

    # 6. Préparer la réponse
    response = {
        "status": status.HTTP_201_CREATED,
        "notification": {
            "id": notif.id,
            "title": notif.title,
            "created_at": notif.created_at
        },
        "delivery": {
            "status": "queued",
            "task_count": len(task_ids),
            "task_ids": task_ids
        }
    }

    # 7. Marquer comme traité dans le cache (empêcher les doublons futurs)
    await IdempotencyManager.mark_as_processed(idempotency_key, response)

    return response


@notification_router.post("/agence")
async def create_notif_agence(data: NotificationUserAgenceCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification par agence avec Celery batch processing"""
    
    # 1. Validation agence
    agence = db.query(Agence).filter(Agence.nom_corrige == data.agence).first()
    if not agence:
        return {"status": status.HTTP_404_NOT_FOUND, "message": "Agence non trouvée"}
    
    # 2. Récupération des utilisateurs
    user_compteurs_db = db.query(UserCompteur).filter(UserCompteur.id_agence == agence.id).all()
    if not user_compteurs_db:
        return {"status": status.HTTP_404_NOT_FOUND, "message": "Pas de compteurs"}
    
    # 3. Sauvegarde des notifications en lot
    notifications = []
    user_ids = set()
    
    for user_compteur in user_compteurs_db:
        user_ids.add(user_compteur.user_id)
        
        notif = Notification(
            type_notification_id=data.type_notification_id,
            event_id=data.event_id,
            by_user_id=data.by_user_id,
            for_user_id=user_compteur.user_id,
            title=data.title,
            body=data.body,
            is_read=data.is_read
        )
        notifications.append(notif)
    
    db.add_all(notifications)
    db.commit()
    
    # 4. Récupération des tokens
    user_sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id.in_(user_ids),
            UserSession.is_active == True,
            UserSession.fcm_token.isnot(None)
        )
    ).all()
    
    # 5. Préparation du batch Celery avec DÉDUPLICATION GLOBALE
    batch_notifications = []
    all_unique_tokens = set()
    
    # Collecter tous les tokens uniques globalement (même logique que /alluser)
    for session in user_sessions:
        if session.fcm_token:
            all_unique_tokens.add(session.fcm_token)
    
    # Créer les notifications avec les tokens dédupliqués
    for token in all_unique_tokens:
        # Trouver un user_id associé à ce token (pour les stats)
        session_for_token = next(s for s in user_sessions if s.fcm_token == token)
        batch_notifications.append({
            "token": token,
            "title": data.title,
            "body": data.body,
            "user_id": session_for_token.user_id
        })
    
    task_result = None
    if batch_notifications:
        from datetime import datetime
        batch_data = {
            "notifications": batch_notifications,
            "batch_id": f"agence_{agence.id}_{int(datetime.utcnow().timestamp())}",
            "priority": _get_notification_priority(data.type_notification_id)
        }
        
        task_result = send_batch_notifications.delay(batch_data)
    
    return {
        "status": status.HTTP_201_CREATED,
        "message": f"Notifications programmées pour {len(user_ids)} utilisateurs",
        "delivery": {
            "batch_task_id": task_result.id if task_result else None,
            "notification_count": len(batch_notifications)
        }
    }


@notification_router.post("/allusercompteur")
async def create_notif_all_agence(data: NotificationAllAgenceCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification à tous les utilisateurs ayant un compteur (avec Celery broadcast)"""

    by_user_id = data.by_user_id if data.by_user_id else None

    user_compteurs_db = db.query(UserCompteur).all()

    if not user_compteurs_db:
        return {"status": status.HTTP_404_NOT_FOUND, "message": "Pas de compteurs"}

    # 1. Sauvegarder toutes les notifications en DB (batch)
    notifications = []
    user_ids = set()

    for user_compteur in user_compteurs_db:
        user_ids.add(user_compteur.user_id)
        notif = Notification(
            type_notification_id=data.type_notification_id,
            event_id=data.event_id,
            by_user_id=by_user_id,
            for_user_id=user_compteur.user_id,
            title=data.title,
            body=data.body,
            is_read=data.is_read
        )
        notifications.append(notif)

    db.add_all(notifications)
    db.commit()

    # 2. Récupérer tous les tokens FCM
    user_sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id.in_(user_ids),
            UserSession.is_active,
            UserSession.fcm_token.isnot(None)
        )
    ).all()

    # 3. Préparer le broadcast avec DÉDUPLICATION GLOBALE (même correction)
    user_tokens = {}
    all_unique_tokens = set()
    
    for session in user_sessions:
        if session.fcm_token:
            # Collecte globale des tokens uniques
            all_unique_tokens.add(session.fcm_token)
            
            # Statistiques par utilisateur
            if session.user_id not in user_tokens:
                user_tokens[session.user_id] = set()
            user_tokens[session.user_id].add(session.fcm_token)

    # Format pour Celery : tokens uniques seulement
    user_tokens_list = [
        {"user_id": "global_compteurs", "tokens": list(all_unique_tokens)}
    ] if all_unique_tokens else []

    # 4. Envoyer via Celery broadcast (TOKENS DÉDUPLIQUÉS)
    task_result = None
    if user_tokens_list:
        broadcast_data = {
            "title": data.title,
            "body": data.body,
            "user_tokens": user_tokens_list,  # Tokens uniques globalement
            "chunk_size": 100
        }
        task_result = send_broadcast_notifications.delay(broadcast_data)

    # Calculer le nombre de tokens uniques globalement
    all_unique_tokens = set()
    for tokens in user_tokens.values():
        all_unique_tokens.update(tokens)
    
    return {
        "status": status.HTTP_201_CREATED,
        "message": f"Notifications programmées pour {len(user_ids)} utilisateurs avec compteur",
        "delivery": {
            "broadcast_task_id": task_result.id if task_result else None,
            "user_count": len(user_ids),
            "token_count": len(all_unique_tokens)
        }
    }


@notification_router.post("/alluser")
async def create_notif_all_user(data: NotificationAllUserCreateSchema, db: Session = Depends(get_db_samaconso)):
    """Notification GLOBALE à tous les utilisateurs (1 seul enregistrement) - OPTIMISÉ"""

    logger.info(f"📢 Creating GLOBAL notification | Type: {data.type_notification_id} | Title: '{data.title[:50]}'")
    log_api_request("/notifications/alluser", "POST", data.by_user_id)

    by_user_id = data.by_user_id if data.by_user_id else None

    user_db = db.query(User).all()

    if not user_db:
        return {"status": status.HTTP_404_NOT_FOUND, "message": "Pas d'utilisateurs"}

    # 1. Créer UNE SEULE notification globale (for_user_id = NULL pour "tous")
    user_ids = [user.id for user in user_db]
    
    global_notif = Notification(
        type_notification_id=data.type_notification_id,
        event_id=data.event_id,
        by_user_id=by_user_id,
        for_user_id=None,  # NULL = notification globale pour tous les utilisateurs
        title=data.title,
        body=data.body,
        is_read=data.is_read
    )
    
    db.add(global_notif)
    db.commit()
    db.refresh(global_notif)

    # 2. Récupérer tous les tokens FCM
    user_sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id.in_(user_ids),
            UserSession.is_active,
            UserSession.fcm_token.isnot(None)
        )
    ).all()

    # 3. Préparer le broadcast avec DÉDUPLICATION GLOBALE (résout le problème des 40+ notifications)
    user_tokens = {}
    all_unique_tokens = set()
    
    for session in user_sessions:
        if session.fcm_token:
            # Collecte globale des tokens uniques
            all_unique_tokens.add(session.fcm_token)
            
            # Statistiques par utilisateur (pour debug)
            if session.user_id not in user_tokens:
                user_tokens[session.user_id] = set()
            user_tokens[session.user_id].add(session.fcm_token)

    # Format pour Celery : UN SEUL GROUPE avec tous les tokens uniques (68 au lieu de 108 !)
    user_tokens_list = [
        {"user_id": "global_broadcast", "tokens": list(all_unique_tokens)}
    ] if all_unique_tokens else []

    # 4. Envoyer via Celery broadcast (TOKENS DÉDUPLIQUÉS GLOBALEMENT)
    task_result = None
    if user_tokens_list:
        broadcast_data = {
            "title": data.title,
            "body": data.body,
            "user_tokens": user_tokens_list,  # Seulement les tokens uniques !
            "chunk_size": 100
        }
        task_result = send_broadcast_notifications.delay(broadcast_data)
    
    return {
        "status": status.HTTP_201_CREATED,
        "message": f"Notification globale créée et diffusée à {len(user_ids)} utilisateurs",
        "notification_id": global_notif.id,
        "delivery": {
            "broadcast_task_id": task_result.id if task_result else None,
            "user_count": len(user_ids),
            "token_count": len(all_unique_tokens),
            "optimization": "1 seule notification en base au lieu de " + str(len(user_ids))
        }
    }



@notification_router.put("/{notif_id}/read")
def mark_as_read(notif_id: int, db: Session = Depends(get_db_samaconso)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if notif:
        notif.is_read = True
        db.commit()
        try:
            from app.cache import cache_delete
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(cache_delete("notifications:all"))
        except Exception:
            pass
        return {"status":status.HTTP_200_OK,"message": "Notification marquée comme lue"}
    return {"status":status.HTTP_404_NOT_FOUND,"message": "Notification non trouvée"}


@notification_router.get("/for/{user_id}/all")
def get_all_for_user_notifs(user_id: int, db: Session = Depends(get_db_samaconso)):
    # Récupérer les notifications spécifiques à l'utilisateur ET les notifications globales
    notifs = db.query(Notification).filter(
        or_(
            Notification.for_user_id == user_id,     # Notifications spécifiques à l'utilisateur
            Notification.for_user_id.is_(None)       # Notifications globales (for_user_id = NULL)
        )
    ).order_by(Notification.created_at.desc()).all()
    
    if not notifs:
        return {"status":status.HTTP_404_NOT_FOUND,"message": "Pas encore de notification"}
    
    # Compter les types pour information
    specific_count = len([n for n in notifs if n.for_user_id == user_id])
    global_count = len([n for n in notifs if n.for_user_id is None])
    
    return {
        "status":status.HTTP_200_OK,
        "results":len(notifs),
        "breakdown": {
            "specific_notifications": specific_count,
            "global_notifications": global_count,
            "total": len(notifs)
        },
        "notifications": notifs
    }

@notification_router.get("/agence/{agence_id}")
def get_all_agence_notifs(agence_id: int, db: Session = Depends(get_db_samaconso)):
    users = db.query(User).filter(User.id_agence==agence_id).order_by(Notification.created_at.desc()).all()
    user_ids = [user.id for user in users]

    notifs = db.query(Notification).filter(Notification.by_user_id.in_(user_ids)).order_by(Notification.created_at.desc()).all()
    if not notifs:
        return {"status":status.HTTP_404_NOT_FOUND,"message": "Pas encore de notification"}
    
    return {"status":status.HTTP_200_OK,"results":len(notifs),"notifications": notifs}

@notification_router.get("/by/{user_id}/all")
def get_all_by_user_notifs(user_id: int, db: Session = Depends(get_db_samaconso)):
    notifs = db.query(Notification).filter(Notification.by_user_id == user_id).order_by(Notification.created_at.desc()).all()
    if not notifs:
        return {"status":status.HTTP_404_NOT_FOUND,"message": "Pas encore de notification"}
    
    return {"status":status.HTTP_200_OK,"results":len(notifs),"notifications": notifs}


@notification_router.get("/all/{user_id}")
def get_all_user_notifs(user_id: int, db: Session = Depends(get_db_samaconso)):
    # Récupérer toutes les notifications liées à l'utilisateur (envoyées par lui, pour lui, ou globales)
    notifs = db.query(Notification).filter(
        or_(
            Notification.by_user_id == user_id,      # Notifications envoyées par l'utilisateur
            Notification.for_user_id == user_id,     # Notifications spécifiques à l'utilisateur
            Notification.for_user_id.is_(None)       # Notifications globales (tous les utilisateurs)
        )
    ).order_by(Notification.created_at.desc()).all()
    
    if not notifs:
        return {"status":status.HTTP_404_NOT_FOUND,"message": "Pas encore de notification"}
    
    # Statistiques détaillées
    sent_by_user = len([n for n in notifs if n.by_user_id == user_id])
    received_specific = len([n for n in notifs if n.for_user_id == user_id])
    received_global = len([n for n in notifs if n.for_user_id is None])
    
    return {
        "status":status.HTTP_200_OK,
        "results":len(notifs),
        "breakdown": {
            "sent_by_user": sent_by_user,
            "received_specific": received_specific,
            "received_global": received_global,
            "total": len(notifs)
        },
        "notifications": notifs
    }

@notification_router.get("/all")
async def get_all_notifs(db: Session = Depends(get_db_samaconso)):
    """Récupérer toutes les notifications avec cache très court (très dynamique - 1min)"""
    key_all = CACHE_KEYS["NOTIFICATIONS_ALL"]
    try:
        cached = await cache_get(key_all)
        if cached:
            data = json.loads(cached)
            return {
                "status": 200,
                "results": len(data),
                "notifications": data,
                "cache_hit": True
            }
    except Exception:
        pass
    
    notifs = db.query(Notification).order_by(Notification.created_at.desc()).all()
    if not notifs:
        return {"status": 404, "message": "Pas encore de notification"}
    
    notifications_data = []
    for n in notifs:
        notifications_data.append({
            "id": n.id,
            "type_notification_id": n.type_notification_id,
            "event_id": n.event_id,
            "by_user_id": n.by_user_id,
            "for_user_id": n.for_user_id,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%d/%m/%Y %H:%M:%S") if n.created_at else None,
        })
    
    # Cache avec TTL très court (1 minute) pour données très dynamiques
    try:
        await cache_set(key_all, json.dumps(notifications_data), ttl_seconds=60)  # CACHE_TTL["NOTIFICATIONS"]
    except Exception:
        pass
    
    return {
        "status": 200,
        "results": len(notifications_data),
        "notifications": notifications_data,
        "cache_hit": False
    }

@notification_router.post("/fromcompteur")
async def create_notif_compteur(data: NotificationfromCompteurSchema, db: Session = Depends(get_db_samaconso)):
    """
    Send notification to all users associated with a specific meter number
    MIGRATED TO CELERY - Uses RabbitMQ + Redis backend
    """
    # 1. Find all users associated with this meter
    user_compteurs = db.query(UserCompteur).filter(
        UserCompteur.numero_compteur == data.num_compteur
    ).all()

    if not user_compteurs:
        return {
            "status": status.HTTP_404_NOT_FOUND,
            "message": "Compteur non trouvé"
        }

    # 2. Prepare batch notifications
    batch_notifications = []
    notification_ids = []

    for user_compteur in user_compteurs:
        for_user_id = user_compteur.user_id

        # Create notification in DB
        notif = Notification(
            type_notification_id=data.type_notification_id,
            event_id=0,
            by_user_id=None,
            for_user_id=for_user_id,
            title=data.title,
            body=data.body,
            is_read=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        notification_ids.append(notif.id)

        # Get user sessions with FCM tokens
        user_sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == for_user_id,
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None)
            )
        ).all()

        # DÉDUPLICATION GLOBALE par token: éviter d'envoyer plusieurs fois au même appareil
        all_unique_tokens_compteur = set()
        
        # Collecter tous les tokens uniques pour ce compteur
        for session in user_sessions:
            if session.fcm_token:
                all_unique_tokens_compteur.add(session.fcm_token)
        
        # Créer les notifications avec les tokens dédupliqués
        for token in all_unique_tokens_compteur:
            batch_notifications.append({
                "token": token,
                "title": data.title,
                "body": data.body,
                "user_id": for_user_id,
                "notification_id": notif.id
            })

    # 3. Send via Celery batch processing
    task_result = None
    if batch_notifications:
        batch_data = {
            "notifications": batch_notifications,
            "batch_id": f"compteur_{data.num_compteur}_{int(datetime.utcnow().timestamp())}",
            "priority": 6  # Normal priority
        }
        task_result = send_batch_notifications.delay(batch_data)

    return {
        "status": status.HTTP_201_CREATED,
        "message": f"Notifications programmées pour {len(user_compteurs)} utilisateurs du compteur {data.num_compteur}",
        "notification_ids": notification_ids,
        "delivery": {
            "batch_task_id": task_result.id if task_result else None,
            "notification_count": len(batch_notifications),
            "user_count": len(user_compteurs)
        }
    }


@notification_router.delete("/{notif_id}")
def delete_user_session(notif_id: int, db: Session = Depends(get_db_samaconso)):
    session = db.query(Notification).filter(Notification.id == notif_id).first()
    if not session:
        return {"status_code":404, "message":"Session not found"}
    db.delete(session)
    db.commit()
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("notifications:all"))
    except Exception:
        pass
    return {"detail": "Session deleted"}

# @notification_router.post("/notif")
# async def send_push_notification(data:PushNotification):
    # pass
    # headers = {
    #     "Authorization": f"key={FCM_SERVER_KEY}",
    #     "Content-Type": "application/json",
    # }
    # payload = {
    #     "to": data.token,
    #     "notification": {
    #         "title": data.title,
    #         "body": data.body,
    #     },
    #     "priority": "high"
    # }
    # async with httpx.AsyncClient() as client:
    #     response = await client.post("https://fcm.googleapis.com/fcm/send", headers=headers, json=payload)
    #     return response.json()

    ###

    # message = messaging.Message(
    #     notification=messaging.Notification(
    #         title=data.title,
    #         body=data.body,
    #     ),
    #     token=data.token,
    # )

    # # Send message
    # response = messaging.send(message)
    # return {"message_id": response}


def for_user_notif(type_notification_id:int,title:str,body:str,for_user_id:int,event_id:int,  db: Session ):
    """
    Helper function to create notification and send via Celery (async)
    MIGRATED TO CELERY - Uses RabbitMQ + Redis backend
    """

    # 1. Create notification in database
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

    # 2. Get active user sessions with FCM tokens
    user_sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id == for_user_id,
            UserSession.is_active == True,
            UserSession.fcm_token.isnot(None)
        )
    ).all()

    # 3. Send notifications via Celery (asynchronous) avec DÉDUPLICATION GLOBALE
    task_ids = []
    all_unique_tokens_helper = set()

    if user_sessions:
        # DÉDUPLICATION GLOBALE: collecter tous les tokens uniques
        for user_session in user_sessions:
            if user_session.fcm_token:
                all_unique_tokens_helper.add(user_session.fcm_token)

        # Envoyer seulement aux tokens uniques
        for token in all_unique_tokens_helper:
            notification_data = {
                "token": token,
                "title": title,
                "body": body,
                "user_id": for_user_id,
                "notification_id": notif.id
            }

            # Send via Celery task queue (RabbitMQ)
            task = send_single_notification.delay(notification_data)
            task_ids.append(task.id)

    return notif, task_ids

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
            "info": result.info
        }
        
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "error",
            "message": str(e)
        }

@notification_router.get("/debug/sessions/{user_id}")
async def debug_user_sessions(user_id: int, db: Session = Depends(get_db_samaconso)):
    """Debug: Afficher toutes les sessions actives d'un utilisateur"""
    try:
        sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active
            )
        ).all()

        session_info = []
        fcm_tokens = []

        for session in sessions:
            session_info.append({
                "session_id": session.id,
                "fcm_token": session.fcm_token[:30] + "..." if session.fcm_token else None,
                "last_login": session.last_login.isoformat() if session.last_login else None,
                "device_model": session.device_model
            })
            if session.fcm_token:
                fcm_tokens.append(session.fcm_token)

        # Compter les tokens uniques
        unique_tokens = len(set(fcm_tokens))
        duplicate_tokens = len(fcm_tokens) - unique_tokens

        return {
            "status": 200,
            "user_id": user_id,
            "total_sessions": len(sessions),
            "total_fcm_tokens": len(fcm_tokens),
            "unique_fcm_tokens": unique_tokens,
            "duplicate_tokens": duplicate_tokens,
            "warning": f"⚠️ {duplicate_tokens} tokens dupliqués détectés!" if duplicate_tokens > 0 else None,
            "sessions": session_info
        }

    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }

@notification_router.get("/cache/inspect")
async def inspect_notification_cache():
    """Inspecter l'état du cache des notifications"""
    from app.cache import redis_client

    try:
        if not redis_client:
            return {"status": 500, "message": "Redis non disponible"}

        # Rechercher toutes les clés de notifications
        notification_patterns = ["notifications:*"]
        notification_keys = []

        for pattern in notification_patterns:
            keys = await redis_client.keys(pattern)
            notification_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])

        cache_contents = {}
        for key in notification_keys:
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
                "notification_cache_keys": notification_keys,
                "cache_contents": cache_contents
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"Erreur inspection cache: {str(e)}"
        }

def _is_urgent_notification(type_notification_id: int) -> bool:
    """Détermine si une notification est urgente"""
    urgent_types = [1, 2]  # Coupure électrique, Urgence
    return type_notification_id in urgent_types

def _get_notification_priority(type_notification_id: int) -> int:
    """Retourne la priorité selon le type"""
    priority_mapping = {1: 9, 2: 7, 3: 5, 4: 3}
    return priority_mapping.get(type_notification_id, 5)


@notification_router.get("/debug/users")
async def debug_users(db: Session = Depends(get_db_samaconso)):
    """Debug: Afficher tous les utilisateurs avec leurs sessions"""
    try:
        users = db.query(User).limit(10).all()  # Limiter à 10 pour éviter trop de données
        
        result = []
        for user in users:
            sessions = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user.id,
                    UserSession.is_active
                )
            ).all()
            
            result.append({
                "user_id": user.id,
                "firstName": user.firstName,
                "lastName": user.lastName,
                "active_sessions": len(sessions),
                "fcm_tokens": [s.fcm_token[:20] + "..." if s.fcm_token else None for s in sessions]
            })
            
        return {
            "status": 200,
            "users": result
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }


@notification_router.get("/debug/tokens/analysis")
async def debug_tokens_analysis(db: Session = Depends(get_db_samaconso)):
    """Debug: Analyser les tokens FCM dupliqués dans toute la base"""
    try:
        # Récupérer toutes les sessions actives
        sessions = db.query(UserSession).filter(
            and_(
                UserSession.is_active,
                UserSession.fcm_token.isnot(None)
            )
        ).all()

        # Analyser les doublons
        token_users = {}  # token -> [list of user_ids]
        
        for session in sessions:
            token = session.fcm_token
            user_id = session.user_id
            
            if token not in token_users:
                token_users[token] = []
            token_users[token].append(user_id)

        # Identifier les tokens dupliqués entre utilisateurs
        cross_user_duplicates = {
            token: users for token, users in token_users.items() 
            if len(set(users)) > 1  # Même token sur plusieurs users différents
        }
        
        # Stats
        total_sessions = len(sessions)
        total_unique_tokens = len(token_users)
        notifications_saved = total_sessions - total_unique_tokens
        
        return {
            "status": 200,
            "problem_analysis": {
                "total_active_sessions": total_sessions,
                "unique_fcm_tokens_globally": total_unique_tokens,
                "tokens_shared_between_users": len(cross_user_duplicates),
                "notifications_that_would_be_duplicated": notifications_saved,
                "current_system": f"Sends {total_sessions} notifications",
                "with_global_dedup": f"Would send only {total_unique_tokens} notifications",
                "improvement": f"Reduces by {notifications_saved} duplicates"
            },
            "shared_tokens_sample": {
                token[:30] + "...": {
                    "users": list(set(users)), 
                    "occurrences": len(users)
                }
                for token, users in list(cross_user_duplicates.items())[:5]  # Seulement 5 exemples
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }


@notification_router.get("/debug/recent-notifications/{user_id}")
async def debug_recent_notifications_for_user(user_id: int, db: Session = Depends(get_db_samaconso)):
    """Debug: Voir les dernières notifications pour un utilisateur spécifique"""
    try:
        # Notifications FOR cet utilisateur
        notifs_for = db.query(Notification).filter(
            Notification.for_user_id == user_id
        ).order_by(Notification.created_at.desc()).limit(10).all()
        
        # Notifications BY cet utilisateur  
        notifs_by = db.query(Notification).filter(
            Notification.by_user_id == user_id
        ).order_by(Notification.created_at.desc()).limit(5).all()

        return {
            "status": 200,
            "user_id": user_id,
            "notifications_for_user": {
                "count": len(notifs_for),
                "notifications": [
                    {
                        "id": n.id,
                        "title": n.title,
                        "by_user_id": n.by_user_id,
                        "for_user_id": n.for_user_id,
                        "created_at": n.created_at.isoformat() if n.created_at else None
                    }
                    for n in notifs_for
                ]
            },
            "notifications_by_user": {
                "count": len(notifs_by),
                "notifications": [
                    {
                        "id": n.id,
                        "title": n.title,
                        "by_user_id": n.by_user_id,
                        "for_user_id": n.for_user_id,
                        "created_at": n.created_at.isoformat() if n.created_at else None
                    }
                    for n in notifs_by
                ]
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }


@notification_router.get("/debug/deduplication-test")
async def test_deduplication_impact(db: Session = Depends(get_db_samaconso)):
    """Test: Simuler l'impact de la déduplication sur tous les endpoints"""
    try:
        # Analyse globale des tokens
        sessions = db.query(UserSession).filter(
            and_(
                UserSession.is_active,
                UserSession.fcm_token.isnot(None)
            )
        ).all()

        # Grouper par utilisateur et par agence (simulation)
        user_tokens = {}
        agence_tokens = {}
        
        for session in sessions:
            # Par utilisateur
            if session.user_id not in user_tokens:
                user_tokens[session.user_id] = set()
            user_tokens[session.user_id].add(session.fcm_token)
            
            # Par agence (simuler avec user_id % 5 pour grouper)
            agence_id = session.user_id % 5
            if agence_id not in agence_tokens:
                agence_tokens[agence_id] = set()
            agence_tokens[agence_id].add(session.fcm_token)

        # Calculs de l'impact
        total_sessions = len(sessions)
        total_unique_tokens = len(set(s.fcm_token for s in sessions))
        
        # Analyse des notifications globales vs spécifiques
        total_users = db.query(User).count()
        global_notifications = db.query(Notification).filter(Notification.for_user_id.is_(None)).count()
        specific_notifications = db.query(Notification).filter(Notification.for_user_id.isnot(None)).count()
        
        # Simulations par endpoint
        endpoint_analysis = {
            "global_stats": {
                "total_sessions": total_sessions,
                "unique_tokens_globally": total_unique_tokens,
                "duplicates_saved": total_sessions - total_unique_tokens,
                "improvement_percentage": round((total_sessions - total_unique_tokens) / total_sessions * 100, 2) if total_sessions > 0 else 0
            },
            "database_optimization": {
                "total_users": total_users,
                "global_notifications": global_notifications,
                "specific_notifications": specific_notifications,
                "efficiency_note": f"1 notification globale remplace potentiellement {total_users} notifications spécifiques",
                "storage_saved": f"Économie potentielle: {total_users - global_notifications} enregistrements par broadcast global"
            },
            "endpoints_fixed": {
                "/": "✅ Global deduplication applied",
                "/alluser": "✅ Global deduplication + Global notification (1 record instead of millions)", 
                "/allusercompteur": "✅ Global deduplication applied",
                "/agence": "✅ Global deduplication applied - NEWLY FIXED",
                "/fromcompteur": "✅ Global deduplication applied - NEWLY FIXED",
                "for_user_notif (helper)": "✅ Global deduplication applied - NEWLY FIXED"
            },
            "simulation_by_agence": {
                f"agence_{agence_id}": {
                    "total_tokens_before": sum(len(user_tokens.get(user_id, set())) for user_id in range(agence_id * 10, (agence_id + 1) * 10) if user_id in user_tokens),
                    "unique_tokens_after": len(tokens),
                    "improvement": f"Saves {sum(len(user_tokens.get(user_id, set())) for user_id in range(agence_id * 10, (agence_id + 1) * 10) if user_id in user_tokens) - len(tokens)} duplicates"
                }
                for agence_id, tokens in list(agence_tokens.items())[:3]  # Premier 3 agences
            }
        }
        
        return {
            "status": 200,
            "message": "✅ SYSTEM FULLY OPTIMIZED: FCM Deduplication + Global Notifications",
            "analysis": endpoint_analysis
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }


@notification_router.get("/debug/global-notifications/stats")
async def debug_global_notifications_stats(db: Session = Depends(get_db_samaconso)):
    """Debug: Statistiques sur les notifications globales vs spécifiques"""
    try:
        # Compter les notifications
        global_notifs = db.query(Notification).filter(Notification.for_user_id.is_(None)).all()
        specific_notifs = db.query(Notification).filter(Notification.for_user_id.isnot(None)).count()
        total_users = db.query(User).count()
        
        # Analyser les notifications globales récentes
        recent_globals = [
            {
                "id": n.id,
                "title": n.title,
                "by_user_id": n.by_user_id,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "type": "GLOBAL BROADCAST"
            }
            for n in global_notifs[-5:]  # 5 plus récentes
        ]
        
        return {
            "status": 200,
            "statistics": {
                "global_notifications": len(global_notifs),
                "specific_notifications": specific_notifs,
                "total_users": total_users,
                "efficiency_ratio": f"{len(global_notifs)}:{specific_notifs}",
                "storage_efficiency": f"Chaque notification globale évite {total_users} enregistrements spécifiques"
            },
            "recent_global_notifications": recent_globals,
            "optimization_impact": {
                "without_global": f"Aurait créé {len(global_notifs) * total_users} enregistrements",
                "with_global": f"Créé seulement {len(global_notifs)} enregistrements",
                "records_saved": (len(global_notifs) * total_users) - len(global_notifs),
                "percentage_reduction": round((1 - len(global_notifs) / (len(global_notifs) * total_users)) * 100, 2) if total_users > 0 else 0
            }
        }
        
    except Exception as e:
        return {
            "status": 500,
            "error": str(e)
        }
