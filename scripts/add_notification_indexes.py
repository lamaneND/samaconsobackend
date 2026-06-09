"""
Script pour ajouter des indexes optimisés sur les tables de notifications
Exécuter ce script pour améliorer les performances des notifications

Usage:
    python add_notification_indexes.py
"""

from sqlalchemy import create_engine, text
from app.database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_indexes():
    """Ajoute les indexes pour optimiser les requêtes de notifications"""

    engine = create_engine(DATABASE_URL)

    indexes = [
        # Index sur user_session pour améliorer les requêtes de tokens FCM
        """
        CREATE INDEX IF NOT EXISTS idx_user_session_active_tokens
        ON user_session(user_id, is_active, fcm_token)
        WHERE is_active = true AND fcm_token IS NOT NULL
        """,

        # Index sur user_session pour les requêtes par FCM token
        """
        CREATE INDEX IF NOT EXISTS idx_user_session_fcm_token
        ON user_session(fcm_token)
        WHERE fcm_token IS NOT NULL
        """,

        # Index sur user pour les utilisateurs actifs
        """
        CREATE INDEX IF NOT EXISTS idx_user_is_activate
        ON "user"(is_activate)
        WHERE is_activate = true
        """,

        # Index sur user pour les requêtes par agence
        """
        CREATE INDEX IF NOT EXISTS idx_user_id_agence
        ON "user"(id_agence)
        WHERE id_agence IS NOT NULL
        """,

        # Index composite pour les requêtes user actifs par agence
        """
        CREATE INDEX IF NOT EXISTS idx_user_agence_active
        ON "user"(id_agence, is_activate)
        WHERE is_activate = true AND id_agence IS NOT NULL
        """,

        # Index sur notification pour les requêtes par utilisateur
        """
        CREATE INDEX IF NOT EXISTS idx_notification_for_user_created
        ON notification(for_user_id, created_at DESC)
        """,

        # Index sur notification pour les notifications globales
        """
        CREATE INDEX IF NOT EXISTS idx_notification_global
        ON notification(created_at DESC)
        WHERE for_user_id IS NULL
        """,

        # Index sur notification pour les requêtes non lues
        """
        CREATE INDEX IF NOT EXISTS idx_notification_unread
        ON notification(for_user_id, is_read, created_at DESC)
        WHERE is_read = false
        """,

        # Index sur notification pour les requêtes par type
        """
        CREATE INDEX IF NOT EXISTS idx_notification_type
        ON notification(type_notification_id, created_at DESC)
        """
    ]

    analyze_queries = [
        "ANALYZE user_session",
        "ANALYZE \"user\"",
        "ANALYZE notification"
    ]

    try:
        with engine.connect() as conn:
            logger.info("🚀 Début de la création des indexes...")

            for i, index_query in enumerate(indexes, 1):
                try:
                    logger.info(f"📊 Création index {i}/{len(indexes)}...")
                    conn.execute(text(index_query))
                    conn.commit()
                    logger.info(f"✅ Index {i}/{len(indexes)} créé avec succès")
                except Exception as e:
                    logger.error(f"❌ Erreur lors de la création de l'index {i}: {str(e)}")
                    continue

            logger.info("🔍 Analyse des tables pour mise à jour des statistiques...")
            for analyze_query in analyze_queries:
                try:
                    conn.execute(text(analyze_query))
                    conn.commit()
                    logger.info(f"✅ {analyze_query} exécuté")
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'analyse: {str(e)}")

            logger.info("✅ Tous les indexes ont été créés avec succès!")
            logger.info("📈 Les performances des notifications devraient être nettement améliorées")

    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des indexes: {str(e)}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("OPTIMISATION DES NOTIFICATIONS - Ajout des indexes")
    logger.info("=" * 80)
    add_indexes()
    logger.info("=" * 80)
    logger.info("Script terminé!")
    logger.info("=" * 80)
