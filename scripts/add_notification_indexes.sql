-- ============================================================================
-- OPTIMISATION DES NOTIFICATIONS - Ajout d'indexes pour améliorer les performances
-- ============================================================================
-- Exécuter ce script sur votre base de données pour améliorer drastiquement
-- les performances des requêtes de notifications
--
-- Ces indexes vont accélérer :
-- - La récupération des sessions actives par utilisateur
-- - Les requêtes de notifications par utilisateur
-- - Les jointures User <-> UserSession
-- ============================================================================

-- Index sur user_session pour améliorer les requêtes de tokens FCM
-- Accélère : WHERE user_id = X AND is_active = true AND fcm_token IS NOT NULL
CREATE INDEX IF NOT EXISTS idx_user_session_active_tokens
ON user_session(user_id, is_active, fcm_token)
WHERE is_active = true AND fcm_token IS NOT NULL;

-- Index sur user_session pour les requêtes par FCM token
-- Accélère : WHERE fcm_token = 'xxx'
CREATE INDEX IF NOT EXISTS idx_user_session_fcm_token
ON user_session(fcm_token)
WHERE fcm_token IS NOT NULL;

-- Index sur user pour les utilisateurs actifs
-- Accélère : WHERE is_activate = true
CREATE INDEX IF NOT EXISTS idx_user_is_activate
ON "user"(is_activate)
WHERE is_activate = true;

-- Index sur user pour les requêtes par agence
-- Accélère : WHERE id_agence = X
CREATE INDEX IF NOT EXISTS idx_user_id_agence
ON "user"(id_agence)
WHERE id_agence IS NOT NULL;

-- Index composite pour les requêtes user actifs par agence
-- Accélère : WHERE id_agence = X AND is_activate = true
CREATE INDEX IF NOT EXISTS idx_user_agence_active
ON "user"(id_agence, is_activate)
WHERE is_activate = true AND id_agence IS NOT NULL;

-- Index sur notification pour les requêtes par utilisateur
-- Accélère : WHERE for_user_id = X ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_notification_for_user_created
ON notification(for_user_id, created_at DESC);

-- Index sur notification pour les notifications globales
-- Accélère : WHERE for_user_id IS NULL
CREATE INDEX IF NOT EXISTS idx_notification_global
ON notification(created_at DESC)
WHERE for_user_id IS NULL;

-- Index sur notification pour les requêtes non lues
-- Accélère : WHERE for_user_id = X AND is_read = false
CREATE INDEX IF NOT EXISTS idx_notification_unread
ON notification(for_user_id, is_read, created_at DESC)
WHERE is_read = false;

-- Index sur notification pour les requêtes par type
-- Accélère : WHERE type_notification_id = X
CREATE INDEX IF NOT EXISTS idx_notification_type
ON notification(type_notification_id, created_at DESC);

-- ============================================================================
-- VÉRIFICATION DES INDEXES CRÉÉS
-- ============================================================================
-- Décommenter et exécuter pour vérifier que les indexes ont été créés

-- SELECT
--     schemaname,
--     tablename,
--     indexname,
--     indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('user_session', 'user', 'notification')
-- ORDER BY tablename, indexname;

-- ============================================================================
-- ANALYSE DES TABLES (Optionnel mais recommandé après ajout des indexes)
-- ============================================================================
-- Met à jour les statistiques PostgreSQL pour optimiser le query planner

ANALYZE user_session;
ANALYZE "user";
ANALYZE notification;

-- ============================================================================
-- FIN DU SCRIPT
-- ============================================================================
