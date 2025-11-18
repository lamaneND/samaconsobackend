# 🔧 Solutions aux Problèmes Docker - SamaConso API

## 📊 Diagnostic Résumé

### ✅ État Actuel des Conteneurs
```
✅ samaconso_redis         - HEALTHY
✅ samaconso_rabbitmq      - HEALTHY
✅ samaconso_minio         - HEALTHY
✅ samaconso_api           - HEALTHY
⚠️  samaconso_celery_worker - UNHEALTHY (problèmes identifiés)
⚠️  samaconso_flower        - UNHEALTHY (dépend du worker)
```

---

## 🔴 PROBLÈME 1: Connexion SQL Server

### Symptômes
```
Error connecting to database: ('01000', "[01000] [unixODBC][Driver Manager]
Can't open lib 'ODBC Driver 18 for SQL Server' : file not found (0)")
```

### Cause Racine
Le driver Microsoft ODBC 18 pour SQL Server n'est **PAS installé** dans l'image Docker.

Preuve:
```bash
$ docker exec samaconso_api python -c "import pyodbc; print(pyodbc.drivers())"
Drivers disponibles: []  # ❌ Aucun driver!
```

### ✅ Solution Implémentée

#### Modification du Dockerfile ([Dockerfile.fixed](Dockerfile.fixed:32-46))

```dockerfile
# Installation des drivers Microsoft ODBC
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    libpq5 \
    unixodbc \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get install -y mssql-tools18 \
    && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> /etc/bash.bashrc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

### ✅ Configuration Réseau pour SQL Server

#### Problème de Résolution DNS
Les serveurs SQL internes (`srv-asreports`, `srv-commercial`) ne sont **pas résolvables** depuis Docker.

#### Solution 1: Utiliser `extra_hosts` ([docker-compose.fixed.yml](docker-compose.fixed.yml:104-106))

```yaml
services:
  api:
    extra_hosts:
      - "srv-asreports:10.101.1.XXX"   # ⚠️ REMPLACER par IP réelle
      - "srv-commercial:10.101.1.XXX"  # ⚠️ REMPLACER par IP réelle
```

**Comment trouver les IPs:**
```bash
# Sur une machine du réseau interne
ping srv-asreports
ping srv-commercial
# Noter les adresses IP retournées
```

#### Solution 2: Utiliser les IPs directement

Modifier [.env.docker.fixed](.env.docker.fixed:25-35):

```bash
# Au lieu des noms de serveurs
SQL_SERVER_SIC_HOST=srv-asreports

# Utiliser les IPs directement
SQL_SERVER_SIC_HOST=10.101.1.50
```

### ✅ Configuration Flexible des Connexions

Nouveau fichier [app/database_docker.py](app/database_docker.py) qui:
- ✅ Utilise les variables d'environnement
- ✅ Logs détaillés pour le debug
- ✅ Timeouts configurés
- ✅ Fonction de test de connectivité

**Migration:**
```python
# Dans vos fichiers, remplacer:
from app.database import get_db_connection_sic

# Par:
from app.database_docker import get_db_connection_sic
```

Ou renommer:
```bash
mv app/database.py app/database_old.py
mv app/database_docker.py app/database.py
```

---

## 🔴 PROBLÈME 2: Push Notifications Firebase

### Symptômes Possibles
- Certificat Firebase introuvable
- Erreurs SSL lors de l'envoi
- Variables d'environnement manquantes
- Échec silencieux des notifications

### Causes Identifiées

#### 1. Fichier Firebase Non Monté
Le fichier `samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json` n'est pas accessible dans le conteneur.

#### 2. Variables d'Environnement Manquantes
`FIREBASE_CREDENTIALS_PATH` et `GOOGLE_APPLICATION_CREDENTIALS` non définies.

#### 3. Certificats SSL
Code actuel désactive la vérification SSL (`session.verify = False`), ce qui peut causer des problèmes.

### ✅ Solutions Implémentées

#### 1. Montage du Fichier Firebase ([docker-compose.fixed.yml](docker-compose.fixed.yml:98-100))

```yaml
services:
  api:
    volumes:
      - ./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:ro

  celery_worker:
    volumes:
      - ./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:ro
```

**Note:** `:ro` = read-only pour sécurité

#### 2. Variables d'Environnement ([.env.docker.fixed](.env.docker.fixed:24-32))

```bash
# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
GOOGLE_APPLICATION_CREDENTIALS=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# SSL Configuration pour Firebase
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

#### 3. Certificats SSL dans Docker ([Dockerfile.fixed](Dockerfile.fixed:50))

```dockerfile
# Créer le répertoire pour les certificats SSL
RUN mkdir -p /etc/ssl/certs
```

Les certificats sont installés automatiquement via `ca-certificates`.

### ✅ Recommandation: Corriger le Code Firebase

**Problème actuel** ([app/firebase.py:56](app/firebase.py:56)):
```python
session.verify = False  # ⚠️ DANGEREUX en production
```

**Correction recommandée:**
```python
# Utiliser les certificats système
session.verify = os.getenv('REQUESTS_CA_BUNDLE', True)
```

Ou mieux:
```python
# Ne pas désactiver SSL
session = requests.Session()
# session.verify reste True par défaut
```

---

## 📁 Fichiers Créés/Modifiés

### Nouveaux Fichiers
1. ✅ **[Dockerfile.fixed](Dockerfile.fixed)** - Dockerfile corrigé avec drivers SQL
2. ✅ **[docker-compose.fixed.yml](docker-compose.fixed.yml)** - Configuration Docker complète
3. ✅ **[.env.docker.fixed](.env.docker.fixed)** - Variables d'environnement
4. ✅ **[app/database_docker.py](app/database_docker.py)** - Connexions DB flexibles
5. ✅ **[test_docker_connectivity.py](test_docker_connectivity.py)** - Script de diagnostic
6. ✅ **[GUIDE_DEPLOYMENT_DOCKER.md](GUIDE_DEPLOYMENT_DOCKER.md)** - Guide complet
7. ✅ **[SOLUTIONS_DOCKER.md](SOLUTIONS_DOCKER.md)** - Ce document

### Fichiers à Modifier (optionnel)
- `app/firebase.py` - Corriger `session.verify = False`
- `app/database.py` - Utiliser `database_docker.py`

---

## 🚀 Plan de Déploiement Rapide

### Option A: Déploiement avec Fichiers Corrigés (Recommandé)

```bash
# 1. Trouver les IPs des serveurs SQL
ping srv-asreports      # Noter l'IP
ping srv-commercial     # Noter l'IP

# 2. Éditer docker-compose.fixed.yml et remplacer les IPs
nano docker-compose.fixed.yml
# Chercher "extra_hosts" et remplacer 10.101.1.XXX

# 3. Arrêter les conteneurs actuels
docker-compose down

# 4. Construire et démarrer avec les corrections
docker-compose -f docker-compose.fixed.yml build --no-cache
docker-compose -f docker-compose.fixed.yml up -d

# 5. Vérifier les logs
docker logs samaconso_api -f
```

### Option B: Migration Complète

```bash
# 1-2. Même que Option A

# 3. Sauvegarder l'ancienne config
cp Dockerfile Dockerfile.old
cp docker-compose.yml docker-compose.old.yml
cp .env.docker .env.docker.old

# 4. Remplacer par les nouveaux fichiers
mv Dockerfile.fixed Dockerfile
mv docker-compose.fixed.yml docker-compose.yml
mv .env.docker.fixed .env.docker

# 5. Déployer normalement
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 🧪 Tests de Validation

### Test 1: Vérifier les Drivers SQL Server

```bash
docker exec samaconso_api python -c "import pyodbc; print('✅ Drivers:', pyodbc.drivers())"
```

**Résultat attendu:**
```
✅ Drivers: ['ODBC Driver 18 for SQL Server']
```

### Test 2: Tester la Connexion SQL

```bash
docker exec samaconso_api python test_docker_connectivity.py
```

**Résultat attendu:**
```
✅ PASS - Drivers ODBC
✅ PASS - Connexion SIC
✅ PASS - Connexion Postpaid
✅ PASS - Credentials Firebase
✅ PASS - Initialisation Firebase
✅ PASS - Connectivité Réseau
✅ PASS - Certificats SSL

Score: 7/7 tests réussis (100%)
```

### Test 3: Test Notification Celery

```bash
# Via l'API FastAPI
curl -X POST http://localhost:8000/api/notifications/test \
  -H "Content-Type: application/json" \
  -d '{"token": "test_token", "title": "Test", "body": "Test notification"}'
```

### Test 4: Vérifier Flower (Monitoring Celery)

Ouvrir dans un navigateur: http://localhost:5555

**Login:** admin / admin

Vous devriez voir:
- ✅ Workers actifs
- ✅ Queues: `urgent`, `high_priority`, `normal`, `low_priority`
- ✅ Tasks enregistrées

---

## 🔍 Dépannage Avancé

### Problème: "Connection refused" persistant

```bash
# Vérifier la résolution DNS dans le conteneur
docker exec samaconso_api cat /etc/hosts
docker exec samaconso_api getent hosts srv-asreports

# Tester la connectivité réseau
docker exec samaconso_api ping -c 2 srv-asreports
```

### Problème: Firebase "Permission Denied"

```bash
# Vérifier les permissions du fichier
docker exec samaconso_api ls -la /app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# Devrait afficher:
# -r--r--r-- 1 appuser appuser ... samaconso-firebase-adminsdk...json
```

### Problème: Celery Worker "Unhealthy"

```bash
# Vérifier les logs détaillés
docker logs samaconso_celery_worker --tail 100

# Vérifier que RabbitMQ est accessible
docker exec samaconso_celery_worker python -c "
from app.config import CELERY_BROKER_URL
print('Broker URL:', CELERY_BROKER_URL)
"
```

---

## 📊 Architecture Docker Finale

```
┌─────────────────────────────────────────────────────────┐
│                    Host Machine                         │
│                                                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │         samaconso_network (bridge)                 │ │
│  │                                                      │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │ │
│  │  │  Redis   │  │ RabbitMQ │  │  MinIO   │         │ │
│  │  │  :6379   │  │  :5672   │  │  :9000   │         │ │
│  │  └──────────┘  └──────────┘  └──────────┘         │ │
│  │                                                      │ │
│  │  ┌────────────────────────────────────────────┐   │ │
│  │  │         API Container                      │   │ │
│  │  │  - FastAPI (:8000)                         │   │ │
│  │  │  - ODBC Driver 18 ✅                       │   │ │
│  │  │  - Firebase Credentials ✅                 │   │ │
│  │  │  - SSL Certificates ✅                     │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                      │ │
│  │  ┌────────────────────────────────────────────┐   │ │
│  │  │      Celery Worker Container               │   │ │
│  │  │  - Notifications Tasks                     │   │ │
│  │  │  - Firebase Integration ✅                 │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                      │ │
│  │  ┌────────────────────────────────────────────┐   │ │
│  │  │         Flower Container                   │   │ │
│  │  │  - Monitoring (:5555)                      │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  └──────────────────────────────────────────────────┘ │
│                                                           │
│  Connexions Externes:                                    │
│  ├─ PostgreSQL      → 10.101.1.171:5432                │
│  ├─ SQL Server SIC  → srv-asreports (via extra_hosts)  │
│  ├─ SQL Postpaid    → srv-commercial (via extra_hosts) │
│  └─ Firebase FCM    → fcm.googleapis.com ✅            │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Checklist de Production

### Avant le Déploiement
- [ ] IPs des serveurs SQL documentées
- [ ] Fichier Firebase présent et accessible
- [ ] Variables d'environnement validées
- [ ] `.env.docker` ne contient pas de secrets (utiliser Docker secrets)

### Après le Déploiement
- [ ] Tous les conteneurs `HEALTHY`
- [ ] Tests de connectivité SQL passés
- [ ] Test d'envoi de notification réussi
- [ ] Logs sans erreurs critiques
- [ ] Monitoring accessible (Flower, RabbitMQ)

### Sécurité
- [ ] Changer les mots de passe par défaut
- [ ] Désactiver le mode DEBUG
- [ ] Restreindre les ports exposés (firewall)
- [ ] Configurer TLS pour RabbitMQ/Redis
- [ ] Backup automatique configuré

### Performance
- [ ] Monitorer l'usage CPU/RAM
- [ ] Configurer les limites de ressources
- [ ] Log rotation activé
- [ ] Métriques Celery surveillées

---

## 📞 Support et Questions

Pour toute question sur cette solution:

1. **Logs complets:**
   ```bash
   docker-compose logs > diagnostic-full.log 2>&1
   ```

2. **Test de connectivité:**
   ```bash
   docker exec samaconso_api python test_docker_connectivity.py > connectivity.log 2>&1
   ```

3. **État des conteneurs:**
   ```bash
   docker ps -a > containers-status.txt
   ```

Envoyer ces 3 fichiers pour analyse approfondie.

---

## 🎓 Résumé des Modifications

| Composant | Problème | Solution | Fichier |
|-----------|----------|----------|---------|
| **SQL Server** | Driver manquant | Installation `msodbcsql18` | `Dockerfile.fixed` |
| **Réseau SQL** | Hosts non résolvables | `extra_hosts` mapping | `docker-compose.fixed.yml` |
| **Firebase** | Certificat absent | Volume mount + env vars | `docker-compose.fixed.yml`, `.env.docker.fixed` |
| **SSL** | Certificats manquants | Installation `ca-certificates` | `Dockerfile.fixed` |
| **Configuration** | Hardcodée | Variables d'environnement | `app/database_docker.py` |

---

**✅ Avec ces corrections, votre application devrait fonctionner correctement dans Docker!**
