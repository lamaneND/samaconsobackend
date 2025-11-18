"""
Script pour nettoyer les sessions dupliquées (même user_id + fcm_token)
Usage: python clean_duplicate_sessions.py [--dry-run]
"""

import sys
from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker
from app.models.models import UserSession
from app.database import DATABASE_URL
from datetime import datetime

def clean_duplicate_sessions(dry_run=True):
    """
    Nettoie les sessions dupliquées en gardant seulement la plus récente

    Args:
        dry_run: Si True, affiche ce qui serait supprimé sans supprimer
    """
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        print("\n" + "="*70)
        print("  NETTOYAGE DES SESSIONS DUPLIQUÉES")
        print("="*70)

        if dry_run:
            print("\n⚠️  MODE DRY-RUN (simulation, aucune suppression)")
        else:
            print("\n🔥 MODE SUPPRESSION (les sessions seront supprimées)")

        # Trouver toutes les combinaisons (user_id, fcm_token) dupliquées
        duplicate_pairs = db.query(
            UserSession.user_id,
            UserSession.fcm_token
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

        if not duplicate_pairs:
            print("\n✅ Aucune session dupliquée trouvée.")
            return 0

        print(f"\n📊 {len(duplicate_pairs)} paires (user_id, fcm_token) dupliquées trouvées")

        total_deleted = 0

        for user_id, fcm_token in duplicate_pairs:
            # Récupérer toutes les sessions pour cette paire
            sessions = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.fcm_token == fcm_token,
                    UserSession.is_active == True
                )
            ).order_by(UserSession.created_at.desc()).all()

            if len(sessions) <= 1:
                continue

            # Garder la plus récente, supprimer les autres
            most_recent = sessions[0]
            to_delete = sessions[1:]

            print(f"\n  User ID {user_id} - Token: {fcm_token[:30]}...")
            print(f"    ✅ Garder session ID {most_recent.id} (créée le {most_recent.created_at})")
            print(f"    ❌ Supprimer {len(to_delete)} session(s):")

            for session in to_delete:
                print(f"       - Session ID {session.id} (créée le {session.created_at})")

                if not dry_run:
                    # Option 1: Désactiver au lieu de supprimer (recommandé)
                    session.is_active = False
                    # Option 2: Supprimer complètement (décommenter si souhaité)
                    # db.delete(session)

                total_deleted += 1

        if not dry_run:
            db.commit()
            print(f"\n✅ {total_deleted} sessions dupliquées désactivées avec succès")
        else:
            print(f"\n📋 {total_deleted} sessions seraient désactivées en mode réel")
            print("\n💡 Pour exécuter le nettoyage, lancez:")
            print("   python clean_duplicate_sessions.py --execute")

        return total_deleted

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return 0
    finally:
        db.close()

def main():
    # Vérifier les arguments
    dry_run = True

    if len(sys.argv) > 1:
        if sys.argv[1] in ['--execute', '--no-dry-run', '--real']:
            dry_run = False
            print("\n⚠️  ATTENTION: Mode d'exécution réelle activé!")
            response = input("Êtes-vous sûr de vouloir désactiver les sessions dupliquées? (oui/non): ")
            if response.lower() != 'oui':
                print("❌ Opération annulée")
                sys.exit(0)

    deleted = clean_duplicate_sessions(dry_run=dry_run)

    print("\n" + "="*70)
    print(f"{'Simulation' if dry_run else 'Nettoyage'} terminé - {deleted} sessions traitées")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
