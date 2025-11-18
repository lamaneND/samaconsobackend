# -*- coding: utf-8 -*-
"""
Rechercher un token FCM recent et valide dans la base
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db_samaconso
from app.models.models import UserSession, User

print("\n" + "="*70)
print("RECHERCHE DE TOKENS FCM VALIDES")
print("="*70)

db = next(get_db_samaconso())

try:
    # Tokens FCM actifs
    recent_sessions = db.query(UserSession, User).join(
        User, UserSession.user_id == User.id
    ).filter(
        UserSession.fcm_token.isnot(None),
        UserSession.is_active == True
    ).limit(10).all()

    print(f"\n[1] Tokens FCM actifs: {len(recent_sessions)}")

    if recent_sessions:
        print("\nTop 5 tokens:")
        for i, (session, user) in enumerate(recent_sessions[:5], 1):
            print(f"\n{i}. User: {user.login} (ID: {user.id})")
            print(f"   Token: {session.fcm_token}")

    # Tous les tokens actifs
    all_sessions = db.query(UserSession).filter(
        UserSession.fcm_token.isnot(None),
        UserSession.is_active == True
    ).count()

    print(f"\n[2] Total tokens FCM actifs: {all_sessions}")

    # Recommandation
    print("\n" + "="*70)
    print("RECOMMANDATION")
    print("="*70)

    if recent_sessions:
        session, user = recent_sessions[0]
        print(f"\nUtilisez ce token pour tester:")
        print(f"\nUser: {user.login} (ID: {user.id})")
        print(f"Token: {session.fcm_token}")
        print(f"\nCopiez ce token dans test_single_notification.py")
    else:
        print("\nAucun token recent trouve!")
        print("\nPour tester:")
        print("1. Connectez-vous a l'app mobile Sama Conso")
        print("2. Le token sera genere automatiquement")
        print("3. Re-executez ce script pour le recuperer")

    print("="*70)

except Exception as e:
    print(f"\nERREUR: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
