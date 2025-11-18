#!/usr/bin/env python3
"""
Créer un token JWT de test pour les WebSockets
"""

from datetime import datetime, timedelta
import jwt
from app.config import SECRET_KEY, ALGORITHM


def create_test_token(user_id: int = 1, expires_minutes: int = 60):
    """Créer un token JWT de test"""
    
    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),  # Expiration
        "iat": datetime.utcnow(),  # Issued at
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


if __name__ == "__main__":
    print("🔑 Génération d'un token JWT de test")
    
    # Créer des tokens pour différents utilisateurs
    for user_id in [1, 2, 3]:
        token = create_test_token(user_id)
        print(f"User {user_id}: {token}")
    
    print("\n💡 Utilisez ces tokens pour tester les WebSockets")
    print("Exemple d'URL WebSocket:")
    token_example = create_test_token(1)
    print(f"ws://127.0.0.1:8000/notifications/ws/1?token={token_example}")