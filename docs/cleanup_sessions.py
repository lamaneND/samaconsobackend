"""
Script de nettoyage des sessions utilisateur zombies
Nettoie les sessions dupliquées et obsolètes

Usage:
    python cleanup_sessions.py                    # Mode dry-run (affiche sans modifier)
    python cleanup_sessions.py --execute          # Exécute le nettoyage
    python cleanup_sessions.py --remove-duplicates --execute  # Supprime les duplicatas
"""

import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import argparse
from app.database import get_db_samaconso
from app.models.models import UserSession, User
from sqlalchemy import and_, func
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_duplicate_tokens(db, dry_run=True):
    """
    Nettoie les tokens FCM dupliqués
    Garde seulement la session la plus récente pour chaque token
    """
    print("\n🧹 Nettoyage des tokens FCM dupliqués...")

    # Trouver les tokens dupliqués
    duplicate_tokens_query = db.query(
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
    ).all()

    if not duplicate_tokens_query:
        print("  ✅ Aucun token dupliqué trouvé")
        return 0

    total_to_deactivate = 0

    for token, count in duplicate_tokens_query:
        # Pour chaque token dupliqué, garder seulement la session la plus récente
        sessions_with_token = db.query(UserSession).filter(
            and_(
                UserSession.fcm_token == token,
                UserSession.is_active == True
            )
        ).order_by(
            UserSession.last_login.desc()
        ).all()

        # Garder la première (plus récente), désactiver les autres
        sessions_to_deactivate = sessions_with_token[1:]  # Toutes sauf la plus récente

        for session in sessions_to_deactivate:
            total_to_deactivate += 1
            if dry_run:
                print(f"  [DRY-RUN] Désactiverait session ID={session.id}, user={session.user_id}, token={token[:20]}...")
            else:
                session.is_active = False
                print(f"  ✅ Désactivé session ID={session.id}, user={session.user_id}")

    if not dry_run and total_to_deactivate > 0:
        db.commit()

    return total_to_deactivate

def cleanup_old_sessions(db, days_threshold=30, dry_run=True):
    """
    Nettoie les sessions qui n'ont pas été utilisées depuis X jours
    """
    print(f"\n🧹 Nettoyage des sessions inactives depuis {days_threshold} jours...")

    cutoff_date = datetime.now() - timedelta(days=days_threshold)

    old_sessions = db.query(UserSession).filter(
        and_(
            UserSession.is_active == True,
            UserSession.last_login < cutoff_date
        )
    ).all()

    if not old_sessions:
        print(f"  ✅ Aucune session inactive depuis plus de {days_threshold} jours")
        return 0

    total_deactivated = 0
    for session in old_sessions:
        total_deactivated += 1
        if dry_run:
            print(f"  [DRY-RUN] Désactiverait session ID={session.id}, user={session.user_id}, last_login={session.last_login}")
        else:
            session.is_active = False
            print(f"  ✅ Désactivé session ID={session.id}, last_login={session.last_login}")

    if not dry_run and total_deactivated > 0:
        db.commit()

    return total_deactivated

def cleanup_excess_sessions_per_user(db, max_sessions_per_user=2, dry_run=True):
    """
    Limite le nombre de sessions actives par utilisateur
    Garde seulement les N sessions les plus récentes
    """
    print(f"\n🧹 Limitation à {max_sessions_per_user} sessions par utilisateur...")

    # Trouver les utilisateurs avec trop de sessions
    users_with_many_sessions = db.query(
        UserSession.user_id,
        func.count(UserSession.id).label('session_count')
    ).filter(
        and_(
            UserSession.is_active == True,
            UserSession.fcm_token.isnot(None),
            UserSession.fcm_token != ''
        )
    ).group_by(
        UserSession.user_id
    ).having(
        func.count(UserSession.id) > max_sessions_per_user
    ).all()

    if not users_with_many_sessions:
        print(f"  ✅ Tous les utilisateurs ont <= {max_sessions_per_user} sessions")
        return 0

    total_deactivated = 0

    for user_id, session_count in users_with_many_sessions:
        # Pour chaque utilisateur, garder seulement les N sessions les plus récentes
        user_sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None),
                UserSession.fcm_token != ''
            )
        ).order_by(
            UserSession.last_login.desc()
        ).all()

        # Garder les N premières, désactiver les autres
        sessions_to_keep = user_sessions[:max_sessions_per_user]
        sessions_to_deactivate = user_sessions[max_sessions_per_user:]

        for session in sessions_to_deactivate:
            total_deactivated += 1
            if dry_run:
                print(f"  [DRY-RUN] Désactiverait session ID={session.id}, user={user_id}, last_login={session.last_login}")
            else:
                session.is_active = False
                print(f"  ✅ Désactivé session ID={session.id}, user={user_id}")

    if not dry_run and total_deactivated > 0:
        db.commit()

    return total_deactivated

def main():
    parser = argparse.ArgumentParser(description='Nettoyage des sessions utilisateur')
    parser.add_argument('--execute', action='store_true', help='Exécuter le nettoyage (sinon dry-run)')
    parser.add_argument('--remove-duplicates', action='store_true', help='Supprimer les tokens dupliqués')
    parser.add_argument('--old-sessions-days', type=int, default=30, help='Désactiver les sessions > N jours')
    parser.add_argument('--max-sessions-per-user', type=int, default=2, help='Max sessions par utilisateur')
    args = parser.parse_args()

    dry_run = not args.execute

    db = next(get_db_samaconso())

    try:
        print("=" * 80)
        print("NETTOYAGE DES SESSIONS UTILISATEUR")
        if dry_run:
            print("MODE: DRY-RUN (aucune modification, ajoutez --execute pour appliquer)")
        else:
            print("MODE: EXÉCUTION (les modifications seront appliquées)")
        print("=" * 80)

        total_cleaned = 0

        # 1. Nettoyer les tokens dupliqués
        if args.remove_duplicates:
            total_cleaned += cleanup_duplicate_tokens(db, dry_run)

        # 2. Nettoyer les sessions anciennes
        total_cleaned += cleanup_old_sessions(db, args.old_sessions_days, dry_run)

        # 3. Limiter les sessions par utilisateur
        total_cleaned += cleanup_excess_sessions_per_user(db, args.max_sessions_per_user, dry_run)

        print("\n" + "=" * 80)
        print("RÉSUMÉ")
        print("=" * 80)
        if dry_run:
            print(f"💡 {total_cleaned} sessions seraient désactivées")
            print("🚀 Pour appliquer les changements, ajoutez --execute")
        else:
            print(f"✅ {total_cleaned} sessions désactivées avec succès!")
            print("🎉 Nettoyage terminé!")

        print("=" * 80)

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
