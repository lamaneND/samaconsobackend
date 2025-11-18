# 🔥 Firebase avec Proxy Senelec - Solution

## 🔴 Problème Identifié

Le proxy Senelec (10.101.201.204:8080) :
- ✅ Permet l'accès basique à internet
- ❌ **Bloque ou modifie les certificats SSL**
- ❌ Empêche l'authentification OAuth2 vers `oauth2.googleapis.com`

**Résultat** : Firebase ne peut pas obtenir de token d'accès

---

## ✅ Solution 1: Whitelist OAuth2 (Recommandé)

Demander à l'IT Senelec de whitelister:
- `oauth2.googleapis.com`
- `fcm.googleapis.com`
- `*.googleapis.com`

**Email type** :
```
Objet: Whitelist Google APIs pour Firebase

Bonjour,

L'application SamaConso utilise Firebase Cloud Messaging pour envoyer
des notifications push aux utilisateurs.

Actuellement, le proxy bloque l'authentification OAuth2 nécessaire.

Pourriez-vous whitelister les domaines suivants :
- oauth2.googleapis.com (authentification)
- fcm.googleapis.com (notifications)
- *.googleapis.com (services Google)

Merci,
[Votre nom]
```

---

## ✅ Solution 2: Configuration Proxy dans le Code (Temporaire)

### Modifier firebase.py pour utiliser le proxy

**Fichier** : `app/firebase.py`

```python
# Au début du fichier
import os

# Configuration du proxy
PROXY_HOST = "10.101.201.204"
PROXY_PORT = "8080"
PROXIES = {
    'http': f'http://{PROXY_HOST}:{PROXY_PORT}',
    'https': f'http://{PROXY_HOST}:{PROXY_PORT}'
}

# Configurer les variables d'environnement
os.environ['HTTP_PROXY'] = PROXIES['http']
os.environ['HTTPS_PROXY'] = PROXIES['https']
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'
```

### Puis dans la fonction `_get_cached_credentials`:

```python
# Ligne ~61
session = requests.Session()
session.verify = False  # Désactiver SSL
session.proxies = PROXIES  # Utiliser le proxy
```

---

## ✅ Solution 3: Utiliser un Tunnel/VPN

### Option A: Hotspot Mobile
1. Utiliser le partage de connexion de votre téléphone
2. Les notifications fonctionneront sans proxy

### Option B: VPN Professionnel
Si Senelec a un VPN:
1. Se connecter au VPN
2. Le VPN contourne souvent le proxy

---

## ✅ Solution 4: Firebase Admin SDK Legacy (Sans OAuth)

Utiliser l'ancienne API qui ne nécessite pas OAuth.

**Modifier firebase.py** :

```python
import requests
import json

# Au lieu d'utiliser OAuth, utiliser la clé serveur directement
FCM_SERVER_KEY = "votre_clé_serveur_fcm"  # Depuis Firebase Console

async def send_pushNotification_legacy(data: PushNotification):
    """
    Envoi via Legacy API (pas d'OAuth requis)
    """
    url = "https://fcm.googleapis.com/fcm/send"

    headers = {
        "Authorization": f"Key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": data.token,
        "notification": {
            "title": data.title,
            "body": data.body
        },
        "priority": "high"
    }

    # Session avec proxy et sans SSL
    session = requests.Session()
    session.verify = False
    session.proxies = {
        'http': 'http://10.101.201.204:8080',
        'https': 'http://10.101.201.204:8080'
    }

    response = session.post(url, headers=headers, json=payload)
    return response
```

**Note** : Legacy API sera obsolète en juin 2024, mais fonctionne encore.

---

## ✅ Solution 5: Serveur Relais (Architecture)

### Architecture Recommandée pour Production

```
Mobile App → API SamaConso → Serveur Relais (hors Senelec) → Firebase
                                        ↓
                              (Pas de proxy Senelec)
```

**Avantages** :
- Contourne complètement le proxy
- Plus fiable
- Scalable

**Implémentation** :
1. Déployer un micro-service sur un cloud (AWS, Azure, GCP)
2. API SamaConso envoie les demandes au micro-service
3. Le micro-service envoie à Firebase

---

## 🧪 Tests de Diagnostic

### Test 1: Vérifier l'accès OAuth2

```bash
docker exec samaconso_api curl -v -x http://10.101.201.204:8080 https://oauth2.googleapis.com
```

**Si ça échoue** : Le proxy bloque OAuth2 → Solution 1 ou 4

### Test 2: Vérifier l'accès FCM

```bash
docker exec samaconso_api curl -v -x http://10.101.201.204:8080 https://fcm.googleapis.com
```

**Si ça marche** : Utiliser Solution 4 (Legacy API)

### Test 3: Sans Proxy

```bash
docker exec samaconso_api curl -v https://oauth2.googleapis.com
```

**Si ça marche sans proxy** : Configurer NO_PROXY

---

## 📊 Matrice de Solutions

| Solution | Complexité | Délai | Fiabilité | Recommandation |
|----------|------------|-------|-----------|----------------|
| **Whitelist IT** | Faible | 1-5 jours | ⭐⭐⭐⭐⭐ | ✅ Meilleure |
| **Legacy API** | Moyenne | 2 heures | ⭐⭐⭐⭐ | ✅ Court terme |
| **Hotspot Mobile** | Faible | 5 min | ⭐⭐⭐ | ⚡ Test rapide |
| **Serveur Relais** | Élevée | 1-2 jours | ⭐⭐⭐⭐⭐ | 💡 Production |
| **Modifier Code** | Moyenne | 1 heure | ⭐⭐ | ⚠️ Temporaire |

---

## 🎯 Plan d'Action Recommandé

### Court Terme (Aujourd'hui)
1. **Tester avec hotspot mobile** pour confirmer que le code fonctionne
2. **Implémenter Legacy API** comme solution temporaire

### Moyen Terme (Cette Semaine)
1. **Demander whitelist à l'IT**
2. Ou **déployer un serveur relais** sur le cloud

### Long Terme
1. **Architecture microservices** avec serveur relais dédié
2. **Monitoring** des notifications

---

## 💻 Code Prêt à l'Emploi - Legacy API

Créer `app/firebase_legacy.py` :

```python
import requests
import os

# Configuration
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "votre_clé_ici")
PROXY_URL = "http://10.101.201.204:8080"

def send_notification_legacy(token: str, title: str, body: str):
    """
    Envoi notification via Legacy API FCM
    Fonctionne avec le proxy Senelec
    """
    url = "https://fcm.googleapis.com/fcm/send"

    headers = {
        "Authorization": f"Key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": token,
        "notification": {
            "title": title,
            "body": body
        },
        "priority": "high",
        "android": {
            "priority": "high"
        }
    }

    session = requests.Session()
    session.verify = False  # Désactiver SSL
    session.proxies = {
        'http': PROXY_URL,
        'https': PROXY_URL
    }

    try:
        response = session.post(url, headers=headers, json=payload, timeout=10)
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response.json()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Test
if __name__ == "__main__":
    result = send_notification_legacy(
        token="test_token",
        title="Test",
        body="Test depuis Legacy API"
    )
    print(result)
```

**Récupérer la clé serveur** :
1. Console Firebase → Paramètres du projet
2. Cloud Messaging
3. Server key (Legacy)

---

## 📞 Support

**Contact IT Senelec** pour whitelist
**Alternative** : Legacy API (code ci-dessus)
**Test rapide** : Hotspot mobile

---

**Date** : 2025-11-12
**Proxy** : 10.101.201.204:8080
**Problème** : OAuth2 bloqué
**Solutions** : 5 options disponibles
