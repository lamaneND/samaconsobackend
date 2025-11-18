"""
Script de diagnostic pour identifier les causes de notifications dupliques
Usage: python diagnostic_notifications.py
"""

import sys
from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker
from app.models.models import UserSession, Notification, User
from app.database import DATABASE_URL
from datetime import datetime, timedelta
import json

def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def diagnose_duplicate_sessions():
    """Vrifier s'il y a des sessions avec le mme token FCM"""
    print_section("1. DIAGNOSTIC: Sessions dupliques avec le mme FCM token")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Trouver les tokens dupliqus
        duplicate_tokens = db.query(
            UserSession.user_id,
            UserSession.fcm_token,
            func.count(UserSession.id).label('count')
        ).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None)
            )
        ).group_by(
            UserSession.user_id,
            UserSession.fcm_token
        ).having(
            func.count(UserSession.id) > 1
        ).all()

        if duplicate_tokens:
            print(f"\n  PROBLME DTECT: {len(duplicate_tokens)} utilisateurs ont des sessions dupliques")
            print("\nDtails:")
            for user_id, token, count in duplicate_tokens:
                print(f"\n  User ID: {user_id}")
                print(f"  Token FCM: {token[:30]}...")
                print(f"  Nombre de sessions: {count} ")

                # Afficher les dtails de chaque session
                sessions = db.query(UserSession).filter(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.fcm_token == token,
                        UserSession.is_active == True
                    )
                ).all()

                for i, session in enumerate(sessions, 1):
                    print(f"    Session {i}:")
                    print(f"      ID: {session.id}")
                    print(f"      Created: {session.created_at}")
                    print(f"      Last activity: {getattr(session, 'last_activity', 'N/A')}")

            print("\n SOLUTION: Ces sessions dupliques causent l'envoi multiple de notifications.")
            print("   Les modifications dans notification_routers.py devraient rsoudre ce problme.")
        else:
            print("\n Aucune session duplique dtecte.")
            print("   Le problme ne vient pas des sessions en base de donnes.")

        return len(duplicate_tokens) > 0

    except Exception as e:
        print(f"\n Erreur: {e}")
        return False
    finally:
        db.close()

def diagnose_duplicate_notifications():
    """Vrifier s'il y a des notifications dupliques en DB"""
    print_section("2. DIAGNOSTIC: Notifications dupliques en base de donnes")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Vrifier les notifications cres rcemment (dernires 24h)
        yesterday = datetime.utcnow() - timedelta(hours=24)

        # Trouver les notifications en double (mme titre, body, user, cres presque au mme moment)
        recent_notifs = db.query(Notification).filter(
            Notification.created_at >= yesterday
        ).order_by(Notification.created_at.desc()).all()

        if not recent_notifs:
            print("\n Aucune notification rcente trouve.")
            return False

        print(f"\n {len(recent_notifs)} notifications trouves dans les dernires 24h")

        # Grouper par (user, title, body) dans une fentre de 5 secondes
        duplicates_found = False
        checked_notifs = set()

        for notif in recent_notifs:
            if notif.id in checked_notifs:
                continue

            # Chercher des doublons potentiels (mme user, titre, body, dans les 5 secondes)
            similar_notifs = [
                n for n in recent_notifs
                if n.for_user_id == notif.for_user_id
                and n.title == notif.title
                and n.body == notif.body
                and abs((n.created_at - notif.created_at).total_seconds()) <= 5
                and n.id != notif.id
            ]

            if similar_notifs:
                duplicates_found = True
                print(f"\n  DOUBLONS DTECTS:")
                print(f"  User ID: {notif.for_user_id}")
                print(f"  Titre: {notif.title}")
                print(f"  Nombre de doublons: {len(similar_notifs) + 1}")
                print(f"  Timestamps:")
                print(f"    - {notif.created_at} (ID: {notif.id})")
                for dup in similar_notifs:
                    print(f"    - {dup.created_at} (ID: {dup.id})")
                    checked_notifs.add(dup.id)
                checked_notifs.add(notif.id)

        if duplicates_found:
            print("\n SOLUTION: L'endpoint est probablement appel plusieurs fois.")
            print("   Vrifiez le code frontend/client pour viter les double-clics.")
        else:
            print("\n Aucune notification duplique en base de donnes.")

        return duplicates_found

    except Exception as e:
        print(f"\n Erreur: {e}")
        return False
    finally:
        db.close()

def diagnose_active_sessions_per_user():
    """Afficher le nombre de sessions actives par utilisateur"""
    print_section("3. DIAGNOSTIC: Sessions actives par utilisateur")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Compter les sessions actives par utilisateur
        sessions_count = db.query(
            UserSession.user_id,
            func.count(UserSession.id).label('total_sessions'),
            func.count(func.distinct(UserSession.fcm_token)).label('unique_tokens')
        ).filter(
            and_(
                UserSession.is_active == True,
                UserSession.fcm_token.isnot(None)
            )
        ).group_by(
            UserSession.user_id
        ).all()

        if not sessions_count:
            print("\n Aucune session active avec FCM token.")
            return

        print(f"\n {len(sessions_count)} utilisateurs ont des sessions actives")

        problematic_users = []
        for user_id, total, unique in sessions_count:
            if total > unique:
                problematic_users.append((user_id, total, unique))

        if problematic_users:
            print(f"\n  {len(problematic_users)} utilisateurs ont des sessions avec tokens dupliqus:")
            for user_id, total, unique in problematic_users[:10]:  # Limiter  10
                user = db.query(User).filter(User.id == user_id).first()
                username = user.username if user else "N/A"
                print(f"  User {user_id} ({username}): {total} sessions, {unique} tokens uniques")
        else:
            print("\n Tous les utilisateurs ont des tokens uniques.")
            print("   Le problme ne vient probablement pas des sessions dupliques.")

    except Exception as e:
        print(f"\n Erreur: {e}")
    finally:
        db.close()

def suggest_solutions(has_duplicate_sessions, has_duplicate_notifications):
    """Suggrer des solutions bases sur le diagnostic"""
    print_section("RECOMMANDATIONS")

    if has_duplicate_sessions:
        print("\n Actions recommandes:")
        print("  1.  Les modifications de dduplication sont dj appliques")
        print("  2. Nettoyez les sessions dupliques avec ce script:")
        print("\n     python clean_duplicate_sessions.py")
        print("\n  3. Ajoutez une contrainte UNIQUE sur (user_id, fcm_token) si possible")

    if has_duplicate_notifications:
        print("\n Actions recommandes:")
        print("  1. Vrifiez le code client (frontend/mobile) pour viter les double-clics")
        print("  2. Ajoutez un mcanisme de debounce ct client")
        print("  3. Considrez l'ajout d'un idempotency key dans l'API")

    if not has_duplicate_sessions and not has_duplicate_notifications:
        print("\n Le problme pourrait venir de:")
        print("  1. Celery qui rejoue les tches (vrifiez les logs Celery)")
        print("  2. Firebase/FCM qui envoie plusieurs fois (vrifiez les logs FCM)")
        print("  3. Le client qui coute plusieurs fois le WebSocket")
        print("\n Vrifiez les logs de l'application lors de l'envoi:")
        print("   tail -f app.log | grep ''")

def main():
    # Fix encoding for Windows console
    import sys
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("\n[DIAGNOSTIC] DIAGNOSTIC DES NOTIFICATIONS DUPLIQUEES")
    print("=" * 70)

    try:
        has_dup_sessions = diagnose_duplicate_sessions()
        has_dup_notifs = diagnose_duplicate_notifications()
        diagnose_active_sessions_per_user()
        suggest_solutions(has_dup_sessions, has_dup_notifs)

        print("\n" + "="*70)
        print("[OK] Diagnostic termine")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
