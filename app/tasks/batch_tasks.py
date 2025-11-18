from app.celery_app import celery_app
from app.firebase import send_batch_pushNotifications
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name="send_batch_notifications"
)
def send_batch_notifications(self, batch_data: Dict[str, Any]):
    """
    Traitement par lot pour notifications d'agence (100-1000 users)
    OPTIMISÉ : Utilise l'envoi groupé FCM au lieu d'envoyer 1 par 1

    Args:
        batch_data: {
            "notifications": [{"token": "...", "title": "...", "body": "...", "user_id": 123}],
            "batch_id": "batch_123",
            "priority": 5
        }
    """
    try:
        notifications = batch_data.get("notifications", [])
        batch_id = batch_data.get("batch_id", f"batch_{datetime.utcnow().timestamp()}")

        logger.info(f"📦 Traitement batch {batch_id}: {len(notifications)} notifications")

        if not notifications:
            return {"status": "skipped", "reason": "empty_batch"}

        # OPTIMISATION : Envoi groupé au lieu d'envoyer 1 par 1
        # Beaucoup plus rapide : ~500 notifications en 5-10s au lieu de 50-100s
        result = send_batch_pushNotifications(notifications)

        logger.info(f"✅ Batch {batch_id} terminé: {result['success_count']} succès, {result['failure_count']} échecs")

        return {
            "status": "completed",
            "batch_id": batch_id,
            "total_notifications": len(notifications),
            "success_count": result["success_count"],
            "failure_count": result["failure_count"]
        }

    except Exception as e:
        logger.error(f"❌ Erreur traitement batch: {e}")
        raise

@celery_app.task(
    bind=True,
    name="send_broadcast_notifications"
)
def send_broadcast_notifications(self, broadcast_data: Dict[str, Any]):
    """
    Diffusion massive (10K+ utilisateurs) avec chunking intelligent
    
    Args:
        broadcast_data: {
            "title": "Titre broadcast",
            "body": "Message broadcast",
            "user_tokens": [{"user_id": 1, "tokens": ["token1", "token2"]}],
            "chunk_size": 100
        }
    """
    try:
        user_tokens = broadcast_data.get("user_tokens", [])
        chunk_size = broadcast_data.get("chunk_size", 100)
        title = broadcast_data["title"]
        body = broadcast_data["body"]
        
        logger.info(f"📡 Broadcast vers {len(user_tokens)} utilisateurs")
        
        # Création des chunks
        chunks = [
            user_tokens[i:i + chunk_size] 
            for i in range(0, len(user_tokens), chunk_size)
        ]
        
        batch_jobs = []
        for idx, chunk in enumerate(chunks):
            # Conversion en format compatible batch
            chunk_notifications = []
            for user_data in chunk:
                for token in user_data.get("tokens", []):
                    if token:
                        chunk_notifications.append({
                            "token": token,
                            "title": title,
                            "body": body,
                            "user_id": user_data["user_id"]
                        })
            
            if chunk_notifications:
                # Délai progressif pour étaler la charge
                delay_seconds = idx * 10  # 10s entre chaque chunk
                
                batch_job = send_batch_notifications.apply_async(
                    args=[{
                        "notifications": chunk_notifications,
                        "batch_id": f"broadcast_chunk_{idx}",
                        "priority": 3
                    }],
                    countdown=delay_seconds,
                    queue="low_priority"
                )
                batch_jobs.append(batch_job.id)
        
        return {
            "status": "scheduled",
            "total_chunks": len(chunks),
            "total_users": len(user_tokens),
            "batch_job_ids": batch_jobs
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur broadcast: {e}")
        raise

@celery_app.task(name="batch_summary_callback")
def batch_summary_callback(results: List[Dict], batch_id: str):
    """Callback exécuté après completion d'un batch"""
    try:
        total = len(results)
        success = sum(1 for r in results if r.get("status") == "success")
        failed = total - success
        
        logger.info(f"📊 Résumé batch {batch_id}: {success}/{total} succès")
        
        # Ici on peut envoyer des métriques, logs, alertes etc.
        _store_batch_metrics(batch_id, total, success, failed)
        
        return {
            "batch_id": batch_id,
            "summary": {
                "total": total,
                "success": success,  
                "failed": failed,
                "success_rate": (success / total * 100) if total > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur callback batch: {e}")
        return {"error": str(e)}

def _store_batch_metrics(batch_id: str, total: int, success: int, failed: int):
    """Stockage des métriques de batch (Redis)"""
    try:
        from app.cache import cache_set
        import asyncio
        import json
        
        metrics = {
            "batch_id": batch_id,
            "total": total,
            "success": success,
            "failed": failed,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Stockage avec TTL de 7 jours
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            cache_set(
                f"batch_metrics:{batch_id}",
                json.dumps(metrics),
                ttl_seconds=604800  # 7 jours
            )
        )
        loop.close()
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur stockage métriques: {e}")