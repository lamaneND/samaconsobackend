#!/usr/bin/env python3
"""
Tâches Celery simplifiées pour test sans base de données
"""

from celery import current_task
from app.celery_app import celery_app
import logging
from datetime import datetime
from typing import Dict, Any
import time

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name="test_notification_simple"
)
def test_notification_simple(self, notification_data: Dict[str, Any]):
    """
    Tâche de test notification sans Firebase ni DB
    """
    try:
        logger.info(f"🔄 Test notification for user {notification_data.get('user_id')}")
        
        # Validation du token
        token = notification_data.get("token")
        if not token or token.strip() == "":
            logger.warning(f"⚠️ Token invalide pour user {notification_data.get('user_id')}")
            return {"status": "skipped", "reason": "invalid_token"}
        
        title = notification_data.get("title", "Test")
        body = notification_data.get("body", "Test Body")
        
        # Simule un délai d'envoi FCM
        time.sleep(1)  # Simule l'appel à Firebase
        
        logger.info(f"✅ Notification test envoyée: {title}")
        
        return {
            "status": "success",
            "user_id": notification_data.get("user_id"),
            "task_id": current_task.request.id,
            "sent_at": datetime.utcnow().isoformat(),
            "title": title,
            "body": body,
            "token": token[:10] + "..." # Token partiellement masqué
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur test notification: {e}")
        return {"status": "error", "error": str(e)}

@celery_app.task(
    bind=True,
    name="test_firebase_notification"
)
def test_firebase_notification(self, notification_data: Dict[str, Any]):
    """
    Test avec Firebase réel mais sans DB
    """
    try:
        logger.info(f"🔥 Test Firebase for user {notification_data.get('user_id')}")
        
        token = notification_data.get("token")
        title = notification_data.get("title", "Test Firebase")
        body = notification_data.get("body", "Test Firebase Body")
        
        if not token or token.strip() == "":
            return {"status": "skipped", "reason": "invalid_token"}
        
        # Import Firebase seulement ici pour éviter les erreurs d'import global
        try:
            from app.firebase import send_pushNotification
            from app.schemas.notification_schemas import PushNotification
            
            # Créer l'objet PushNotification
            push_notif = PushNotification(
                token=token,
                title=title,
                body=body
            )
            
            # Envoi via Firebase (asyncio car send_pushNotification est async)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(send_pushNotification(push_notif))
                logger.info(f"✅ Firebase notification envoyée: {result}")
                return {
                    "status": "success",
                    "user_id": notification_data.get("user_id"),
                    "firebase_result": str(result),
                    "sent_at": datetime.utcnow().isoformat()
                }
            finally:
                loop.close()
            
        except ImportError as e:
            logger.error(f"❌ Import Firebase failed: {e}")
            return {"status": "error", "error": f"Firebase import failed: {e}"}
        except Exception as e:
            logger.error(f"❌ Firebase error: {e}")
            return {"status": "error", "error": f"Firebase error: {e}"}
        
    except Exception as e:
        logger.error(f"❌ Erreur test Firebase: {e}")
        return {"status": "error", "error": str(e)}

@celery_app.task(
    bind=True,
    name="test_batch_simple"
)
def test_batch_simple(self, batch_data: Dict[str, Any]):
    """
    Test batch sans DB
    """
    try:
        notifications = batch_data.get("notifications", [])
        batch_id = batch_data.get("batch_id", f"test_batch_{datetime.utcnow().timestamp()}")
        
        logger.info(f"📦 Test batch {batch_id}: {len(notifications)} notifications")
        
        if not notifications:
            return {"status": "skipped", "reason": "empty_batch"}
        
        # Simulation du traitement par lot
        results = []
        for i, notif_data in enumerate(notifications):
            time.sleep(0.1)  # 100ms par notification
            
            result = {
                "notification_index": i,
                "status": "success",
                "title": notif_data.get("title", "Test"),
                "user_id": notif_data.get("user_id", "unknown")
            }
            results.append(result)
        
        return {
            "status": "completed",
            "batch_id": batch_id,
            "total_notifications": len(notifications),
            "results": results,
            "task_id": current_task.request.id
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur test batch: {e}")
        return {"status": "error", "error": str(e)}