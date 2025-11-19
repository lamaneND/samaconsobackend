"""
Script de test pour valider les modifications du refresh token JWT
À exécuter après le démarrage du conteneur Docker
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Affiche une section de test"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_result(success, message):
    """Affiche le résultat d'un test"""
    status = "✅ SUCCESS" if success else "❌ FAILED"
    print(f"{status}: {message}")

def test_login():
    """Test du login - doit retourner access_token et refresh_token"""
    print_section("TEST 1: Login avec génération de refresh token")
    
    # Remplacez ces identifiants par un utilisateur valide de votre base
    login_data = {
        "username": "admin",  # À remplacer
        "password": "admin123"  # À remplacer
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/token-json",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if "access_token" in data and "refresh_token" in data:
                print_result(True, "Login réussi - access_token et refresh_token générés")
                return data["access_token"], data["refresh_token"]
            else:
                print_result(False, "Login réussi mais refresh_token manquant")
                return None, None
        else:
            print_result(False, f"Login échoué: {response.text}")
            return None, None
            
    except Exception as e:
        print_result(False, f"Erreur lors du login: {str(e)}")
        return None, None

def test_refresh(access_token, refresh_token):
    """Test du refresh token - doit retourner un nouveau access_token"""
    print_section("TEST 2: Refresh token")
    
    if not refresh_token:
        print_result(False, "Refresh token manquant - test ignoré")
        return None, None
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/refresh",
            json={"refresh_token": refresh_token},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if "access_token" in data and "refresh_token" in data:
                print_result(True, "Refresh réussi - nouveaux tokens générés")
                print(f"  Nouveau access_token: {data['access_token'][:50]}...")
                print(f"  Nouveau refresh_token: {data['refresh_token'][:50]}...")
                return data["access_token"], data["refresh_token"]
            else:
                print_result(False, "Refresh réussi mais nouveaux tokens manquants")
                return None, None
        else:
            print_result(False, f"Refresh échoué: {response.text}")
            return None, None
            
    except Exception as e:
        print_result(False, f"Erreur lors du refresh: {str(e)}")
        return None, None

def test_access_with_token(access_token):
    """Test d'accès à une route protégée avec l'access token"""
    print_section("TEST 3: Accès avec access token")
    
    if not access_token:
        print_result(False, "Access token manquant - test ignoré")
        return False
    
    try:
        # Test avec une route qui nécessite l'authentification
        response = requests.get(
            f"{BASE_URL}/users/",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print_result(True, "Accès réussi avec access token")
            return True
        elif response.status_code == 401:
            print_result(False, "Access token invalide ou expiré")
            return False
        else:
            print_result(False, f"Erreur inattendue: {response.text[:200]}")
            return False
            
    except Exception as e:
        print_result(False, f"Erreur lors de l'accès: {str(e)}")
        return False

def test_refresh_with_invalid_token():
    """Test du refresh avec un token invalide - doit échouer"""
    print_section("TEST 4: Refresh avec token invalide")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/refresh",
            json={"refresh_token": "invalid_token_12345"},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 401:
            print_result(True, "Refresh correctement rejeté avec token invalide")
            return True
        else:
            print_result(False, f"Refresh accepté avec token invalide (devrait être 401): {response.status_code}")
            return False
            
    except Exception as e:
        print_result(False, f"Erreur lors du test: {str(e)}")
        return False

def test_logout(access_token, refresh_token):
    """Test du logout - doit révoquer le refresh token"""
    print_section("TEST 5: Logout et révocation de refresh token")
    
    if not access_token or not refresh_token:
        print_result(False, "Tokens manquants - test ignoré")
        return False
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/logout",
            json={"refresh_token": refresh_token},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("tokens_revoked"):
                print_result(True, "Logout réussi - refresh token révoqué")
                
                # Vérifier que le refresh token est bien révoqué
                print("\n  Vérification: tentative de refresh après logout...")
                refresh_response = requests.post(
                    f"{BASE_URL}/auth/refresh",
                    json={"refresh_token": refresh_token},
                    headers={"Content-Type": "application/json"}
                )
                if refresh_response.status_code == 401:
                    print_result(True, "Refresh token correctement révoqué (refresh échoue)")
                    return True
                else:
                    print_result(False, "Refresh token non révoqué (refresh réussit encore)")
                    return False
            else:
                print_result(False, "Logout réussi mais tokens non révoqués")
                return False
        else:
            print_result(False, f"Logout échoué: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Erreur lors du logout: {str(e)}")
        return False

def test_health():
    """Test de santé de l'API"""
    print_section("TEST 0: Santé de l'API")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print_result(True, "API accessible")
            return True
        else:
            print_result(False, "API non accessible")
            return False
    except Exception as e:
        print_result(False, f"Erreur de connexion à l'API: {str(e)}")
        print(f"  Assurez-vous que Docker est démarré et que l'API écoute sur {BASE_URL}")
        return False

def main():
    """Fonction principale de test"""
    print("\n" + "="*60)
    print("  TESTS REFRESH TOKEN JWT - SamaConso API")
    print("="*60)
    print(f"Démarrage des tests à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 0: Santé de l'API
    if not test_health():
        print("\n❌ L'API n'est pas accessible. Vérifiez que Docker est démarré.")
        return
    
    # Test 1: Login
    access_token, refresh_token = test_login()
    
    if not access_token or not refresh_token:
        print("\n❌ Login échoué - arrêt des tests")
        return
    
    # Test 2: Accès avec access token
    test_access_with_token(access_token)
    
    # Test 3: Refresh token
    new_access_token, new_refresh_token = test_refresh(access_token, refresh_token)
    
    if new_access_token:
        access_token = new_access_token
        refresh_token = new_refresh_token
    
    # Test 4: Refresh avec token invalide
    test_refresh_with_invalid_token()
    
    # Test 5: Logout
    test_logout(access_token, refresh_token)
    
    # Résumé
    print_section("RÉSUMÉ DES TESTS")
    print("Les tests sont terminés. Vérifiez les résultats ci-dessus.")
    print(f"Fin des tests à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()

