"""
Middleware d'idempotence pour éviter les doublons de notifications
"""
import hashlib
import json
from typing import Optional, Any
from app.cache import cache_get, cache_set
import logging

logger = logging.getLogger(__name__)

class IdempotencyManager:
    """Gestionnaire d'idempotence pour les notifications"""

    IDEMPOTENCY_TTL = 10  # 10 secondes - fenêtre de déduplication

    @staticmethod
    def generate_key(
        user_id: int,
        title: str,
        body: str,
        notification_type: int,
        event_id: Optional[int] = None
    ) -> str:
        """
        Génère une clé d'idempotence unique basée sur les paramètres de notification

        Args:
            user_id: ID de l'utilisateur destinataire
            title: Titre de la notification
            body: Corps du message
            notification_type: Type de notification
            event_id: ID de l'événement (optionnel)

        Returns:
            Clé d'idempotence unique (hash SHA256)
        """
        # Créer une chaîne unique avec tous les paramètres
        data = {
            "user_id": user_id,
            "title": title,
            "body": body,
            "type": notification_type,
            "event_id": event_id or 0
        }

        # Générer un hash SHA256
        data_str = json.dumps(data, sort_keys=True)
        key_hash = hashlib.sha256(data_str.encode()).hexdigest()

        return f"idempotency:notification:{key_hash}"

    @staticmethod
    async def is_duplicate(idempotency_key: str) -> bool:
        """
        Vérifie si une requête avec cette clé a déjà été traitée

        Args:
            idempotency_key: Clé d'idempotence à vérifier

        Returns:
            True si c'est un doublon, False sinon
        """
        try:
            cached = await cache_get(idempotency_key)
            return cached is not None
        except Exception as e:
            logger.error(f"Erreur vérification idempotence: {e}")
            # En cas d'erreur Redis, laisser passer (fail-open)
            return False

    @staticmethod
    async def mark_as_processed(idempotency_key: str, result: Any = None) -> bool:
        """
        Marque une requête comme traitée

        Args:
            idempotency_key: Clé d'idempotence
            result: Résultat à stocker (optionnel)

        Returns:
            True si succès, False sinon
        """
        try:
            value = json.dumps({"processed": True, "result": result}) if result else "processed"
            await cache_set(
                idempotency_key,
                value,
                ttl_seconds=IdempotencyManager.IDEMPOTENCY_TTL
            )
            return True
        except Exception as e:
            logger.error(f"Erreur marquage idempotence: {e}")
            return False

    @staticmethod
    async def get_cached_result(idempotency_key: str) -> Optional[Any]:
        """
        Récupère le résultat en cache pour une requête dupliquée

        Args:
            idempotency_key: Clé d'idempotence

        Returns:
            Résultat en cache ou None
        """
        try:
            cached = await cache_get(idempotency_key)
            if cached:
                try:
                    data = json.loads(cached)
                    return data.get("result")
                except json.JSONDecodeError:
                    return None
        except Exception as e:
            logger.error(f"Erreur récupération résultat cache: {e}")
        return None


async def check_notification_idempotency(
    user_id: int,
    title: str,
    body: str,
    notification_type: int,
    event_id: Optional[int] = None
) -> tuple[bool, Optional[str]]:
    """
    Vérifie l'idempotence d'une notification

    Args:
        user_id: ID utilisateur
        title: Titre
        body: Corps
        notification_type: Type
        event_id: ID événement

    Returns:
        (is_duplicate, idempotency_key)
    """
    idempotency_key = IdempotencyManager.generate_key(
        user_id, title, body, notification_type, event_id
    )

    is_dup = await IdempotencyManager.is_duplicate(idempotency_key)

    if is_dup:
        logger.warning(
            f"[IDEMPOTENCY] Notification dupliquée détectée pour user {user_id}: "
            f"{title[:30]}..."
        )

    return is_dup, idempotency_key
