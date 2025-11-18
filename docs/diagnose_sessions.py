"""
Script de diagnostic des sessions utilisateur
Permet d'identifier les problèmes de sessions dupliquées

Usage:
    python diagnose_sessions.py
"""

import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from app.database import get_db_samaconso
from app.models.models import User, UserSession
from sqlalchemy import and_, func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_sessions():
    """Diagnostic complet des sessions utilisateur"""

    db = next(get_db_samaconso())

    try:
        print("=" * 80)
        print("DIAGNOSTIC DES SESSIONS UTILISATEUR")
        print("=" * 80)

        # 1. Nombre total d'utilisateurs actifs
        total_active_users = db.query(User).filter(User.is_activate == True).count()
        print(f"\n📊 Total utilisateurs actifs: {total_active_users}")

        # 2. Nombre total de sessions actives
        total_active_sessions = db.query(UserSession).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).count()
        print(f"📱 Total sessions actives avec FCM token: {total_active_sessions}")

        # 3. Moyenne de sessions par utilisateur
        if total_active_users > 0:
            avg_sessions = total_active_sessions / total_active_users
            print(f"📈 Moyenne sessions par utilisateur: {avg_sessions:.2f}")

        # 4. Utilisateurs avec le plus de sessions
        print("\n🔍 Top 10 utilisateurs avec le plus de sessions actives:")
        users_with_sessions = db.query(
            UserSession.user_id,
            User.firstName,
            User.lastName,
            func.count(UserSession.id).label('session_count')
        ).join(
            User, UserSession.user_id == User.id
        ).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).group_by(
            UserSession.user_id, User.firstName, User.lastName
        ).order_by(
            func.count(UserSession.id).desc()
        ).limit(10).all()

        for user_id, first_name, last_name, count in users_with_sessions:
            name = f"{first_name or ''} {last_name or ''}".strip() or "N/A"
            print(f"  - User {user_id} ({name}): {count} sessions")

        # 5. Tokens FCM dupliqués
        print("\n🔍 Vérification des tokens FCM dupliqués:")
        duplicate_tokens = db.query(
            UserSession.fcm_token,
            func.count(UserSession.id).label('count')
        ).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).group_by(
            UserSession.fcm_token
        ).having(
            func.count(UserSession.id) > 1
        ).order_by(
            func.count(UserSession.id).desc()
        ).limit(10).all()

        if duplicate_tokens:
            print(f"  ⚠️ {len(duplicate_tokens)} tokens dupliqués trouvés (top 10):")
            for token, count in duplicate_tokens:
                print(f"  - Token {token[:20]}...: {count} fois")
        else:
            print("  ✅ Aucun token dupliqué")

        # 6. Distribution des sessions par utilisateur
        print("\n📊 Distribution du nombre de sessions par utilisateur:")
        session_distribution = db.query(
            func.count(UserSession.id).label('sessions_per_user'),
            func.count(func.distinct(UserSession.user_id)).label('user_count')
        ).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).group_by(
            UserSession.user_id
        ).all()

        distribution = {}
        for sessions_count, _ in session_distribution:
            distribution[sessions_count] = distribution.get(sessions_count, 0) + 1

        for sessions_count in sorted(distribution.keys()):
            user_count = distribution[sessions_count]
            print(f"  - {sessions_count} session(s): {user_count} utilisateur(s)")

        # 7. Tokens uniques vs total
        unique_tokens = db.query(
            func.count(func.distinct(UserSession.fcm_token))
        ).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).scalar()

        print(f"\n🔑 Tokens FCM uniques: {unique_tokens}")
        print(f"📱 Total sessions avec token: {total_active_sessions}")

        if unique_tokens < total_active_sessions:
            duplicate_ratio = ((total_active_sessions - unique_tokens) / total_active_sessions) * 100
            print(f"⚠️ Taux de duplication: {duplicate_ratio:.1f}%")
            print(f"💡 {total_active_sessions - unique_tokens} sessions en trop!")

        # 8. Recommandations
        print("\n" + "=" * 80)
        print("RECOMMANDATIONS")
        print("=" * 80)

        if avg_sessions > 2:
            print("⚠️ PROBLÈME: Trop de sessions actives par utilisateur")
            print("   Recommandation: Nettoyer les sessions zombies")
            print("   Commande: python cleanup_sessions.py")

        if duplicate_tokens:
            print("⚠️ PROBLÈME: Tokens FCM dupliqués détectés")
            print("   Recommandation: Désactiver les anciennes sessions avec le même token")
            print("   Commande: python cleanup_sessions.py --remove-duplicates")

        if avg_sessions <= 2 and not duplicate_tokens:
            print("✅ Tout semble normal!")

        print("=" * 80)

    except Exception as e:
        logger.error(f"Erreur lors du diagnostic: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_sessions()
