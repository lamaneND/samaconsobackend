from celery import current_task
from celery.exceptions import MaxRetriesExceededError
from app.celery_app import celery_app
from app.firebase import send_pushNotification
from app.schemas.notification_schemas import PushNotification
from app.database import get_db_samaconso
from app.models.models import UserSession, Notification
from sqlalchemy import and_
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    name="send_single_notification"
)
def send_single_notification(self, notification_data: Dict[str, Any]):
    """
    Envoi d'une notification individuelle avec retry automatique
    
    Args:
        notification_data: {
            "token": "fcm_token",
            "title": "Titre",
            "body": "Message", 
            "user_id": 123,
            "notification_id": 456
        }
    """
    try:
        logger.info(f"🔄 Processing notification for user {notification_data.get('user_id')}")
        
        # Validation du token
        token = notification_data.get("token")
        if not token or token.strip() == "":
            logger.warning(f"⚠️ Token invalide pour user {notification_data.get('user_id')}")
            return {"status": "skipped", "reason": "invalid_token"}
        
        # Création de l'objet PushNotification
        push_notification = PushNotification(
            token=token,
            title=notification_data["title"],
            body=notification_data["body"]
        )
        
        # Envoi avec gestion des erreurs spécifiques
        try:
            # Exécution de la coroutine async dans le worker sync
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_pushNotification(push_notification))
            loop.close()
            
            logger.info(f"✅ Notification envoyée avec succès pour user {notification_data.get('user_id')}")
            
            # Mise à jour du statut en DB (optionnel)
            _update_notification_status(
                notification_data.get("notification_id"), 
                "sent", 
                current_task.request.id
            )
            
            return {
                "status": "success",
                "user_id": notification_data.get("user_id"),
                "task_id": current_task.request.id,
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except Exception as fcm_error:
            # Gestion des erreurs FCM spécifiques
            error_str = str(fcm_error).lower()
            
            if "invalid" in error_str or "not registered" in error_str:
                # Token invalide - pas de retry
                logger.warning(f"🗑️ Token invalide/expiré pour user {notification_data.get('user_id')}")
                _mark_token_invalid(notification_data.get("user_id"), token)
                return {"status": "failed", "reason": "invalid_token", "no_retry": True}
            
            elif "quota" in error_str or "rate limit" in error_str:
                # Rate limit - retry avec backoff plus long
                logger.warning("🚫 Rate limit atteint, retry dans 5 minutes")
                raise self.retry(countdown=300, max_retries=5)
            
            else:
                # Autres erreurs - retry normal
                logger.error(f"❌ Erreur FCM: {fcm_error}")
                raise fcm_error
                
    except MaxRetriesExceededError:
        logger.error(f"💀 Max retries atteint pour notification user {notification_data.get('user_id')}")
        _update_notification_status(
            notification_data.get("notification_id"), 
            "failed_max_retries", 
            current_task.request.id
        )
        return {"status": "failed", "reason": "max_retries_exceeded"}
        
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {e}")
        raise

@celery_app.task(
    bind=True,
    name="send_urgent_notification",
    priority=9
)
def send_urgent_notification(self, notification_data: Dict[str, Any]):
    """
    Notification urgente (coupure électrique, urgence)
    Priorité maximale, retry agressif
    """
    # Modification des paramètres pour urgence
    notification_data["priority"] = "high"
    notification_data["urgent"] = True
    
    # Délégation à la tâche standard avec priorité haute
    return send_single_notification.apply_async(
        args=[notification_data],
        queue="urgent",
        priority=9
    ).get()

def _update_notification_status(notification_id: int, status: str, task_id: str):
    """Mise à jour du statut de notification en DB"""
    try:
        with next(get_db_samaconso()) as db:
            notification = db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            
            if notification:
                # Ajouter des champs de tracking si nécessaire
                # notification.delivery_status = status
                # notification.task_id = task_id
                # notification.processed_at = datetime.utcnow()
                db.commit()
                
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour statut notification: {e}")

def _mark_token_invalid(user_id: int, invalid_token: str):
    """Marquer un token FCM comme invalide"""
    try:
        with next(get_db_samaconso()) as db:
            session = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.fcm_token == invalid_token
                )
            ).first()
            
            if session:
                session.is_active = False
                # session.invalidated_at = datetime.utcnow()
                db.commit()
                logger.info(f"🗑️ Token marqué comme invalide pour user {user_id}")
                
    except Exception as e:
        logger.error(f"❌ Erreur marquage token invalide: {e}")