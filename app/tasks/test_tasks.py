#!/usr/bin/env python3
"""
Version simplifiée des tâches Celery pour test sans Firebase
"""

from celery import current_task
from app.celery_app import celery_app
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name="send_simple_notification_test"
)
def send_simple_notification_test(self, notification_data: Dict[str, Any]):
    """
    Tâche de test simple sans Firebase
    """
    try:
        logger.info(f"🔄 Test notification for user {notification_data.get('user_id')}")
        
        # Validation du token
        token = notification_data.get("token")
        if not token or token.strip() == "":
            logger.warning(f"⚠️ Token invalide pour user {notification_data.get('user_id')}")
            return {"status": "skipped", "reason": "invalid_token"}
        
        # Simulation de l'envoi
        title = notification_data.get("title", "Test")
        body = notification_data.get("body", "Test Body")
        
        # Simule un délai d'envoi
        import time
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
    name="send_batch_test"
)
def send_batch_test(self, batch_data: Dict[str, Any]):
    """
    Tâche de test pour batch notifications
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
            # Simule le traitement
            import time
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

# Tâche de test de sanité simple
@celery_app.task(name="health_check")
def health_check():
    """Tâche de test de sanité"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Celery worker is running"
    }