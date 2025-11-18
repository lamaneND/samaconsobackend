# Guide d'Utilisation - SamaConso API Docker

## Table des Matières
1. [Démarrage et Arrêt](#démarrage-et-arrêt)
2. [Surveillance et Monitoring](#surveillance-et-monitoring)
3. [Tests et Vérifications](#tests-et-vérifications)
4. [Résolution de Problèmes](#résolution-de-problèmes)
5. [Maintenance](#maintenance)
6. [Commandes Avancées](#commandes-avancées)

---

## Démarrage et Arrêt

### Démarrer tous les services
```bash
docker-compose -f docker-compose.fixed.yml up -d
```
**Résultat** : Démarre tous les conteneurs en arrière-plan

### Arrêter tous les services
```bash
docker-compose -f docker-compose.fixed.yml down
```
**Note** : Les données (Redis, RabbitMQ, MinIO) sont préservées dans les volumes

### Redémarrer tous les services
```bash
docker-compose -f docker-compose.fixed.yml restart
```

### Redémarrer un service spécifique
```bash
# Redémarrer l'API
docker-compose -f docker-compose.fixed.yml restart api

# Redémarrer le worker Celery
docker-compose -f docker-compose.fixed.yml restart celery_worker

# Redémarrer Flower
docker-compose -f docker-compose.fixed.yml restart flower
```

### Démarrer un service spécifique
```bash
docker-compose -f docker-compose.fixed.yml up -d api
docker-compose -f docker-compose.fixed.yml up -d celery_worker
```

---

## Surveillance et Monitoring

### Voir l'état des conteneurs
```bash
docker ps
```
**Colonnes importantes** :
- `STATUS` : Healthy, Unhealthy, ou Up
- `PORTS` : Ports exposés

### Voir les logs en temps réel

#### Logs de l'API
```bash
docker logs samaconso_api -f
```
**Astuce** : Appuyez sur `Ctrl+C` pour arrêter de suivre les logs

#### Logs du Worker Celery
```bash
docker logs samaconso_celery_worker -f
```

#### Logs de tous les services
```bash
docker-compose -f docker-compose.fixed.yml logs -f
```

#### Logs d'un service spécifique (sans suivre)
```bash
docker logs samaconso_api --tail 100
```
**Affiche** : Les 100 dernières lignes de logs

### Interfaces Web de Monitoring

#### 1. API Swagger (Documentation Interactive)
**URL** : http://localhost:8000/docs
**Utilisation** : Tester les endpoints directement depuis le navigateur

#### 2. Flower (Monitoring Celery)
**URL** : http://localhost:5555
**Identifiants** : admin / admin
**Fonctionnalités** :
- Workers actifs
- Tâches en cours et historique
- Statistiques de performance
- Queues configurées

#### 3. RabbitMQ Management
**URL** : http://localhost:15672
**Identifiants** : guest / guest
**Fonctionnalités** :
- Queues et messages
- Connexions actives
- Throughput en temps réel

#### 4. MinIO Console
**URL** : http://localhost:9001
**Identifiants** : minioadmin / minioadmin
**Fonctionnalités** :
- Gestion des buckets
- Upload/Download de fichiers
- Statistiques de stockage

---

## Tests et Vérifications

### Test 1: API Health Check
```bash
curl http://localhost:8000
```
**Résultat attendu** :
```json
{
  "message": "SAMA CONSO",
  "version": "2.0.0",
  "status": "running"
}
```

### Test 2: Connexion SQL Server SIC
```bash
docker exec samaconso_api python -c "from app.database import get_db_connection_sic; print('✅ OK' if get_db_connection_sic() else '❌ FAIL')"
```

### Test 3: Connexion SQL Server Postpaid
```bash
docker exec samaconso_api python -c "from app.database import get_db_connection_postpaid; print('✅ OK' if get_db_connection_postpaid() else '❌ FAIL')"
```

### Test 4: Drivers ODBC installés
```bash
docker exec samaconso_api python -c "import pyodbc; print(pyodbc.drivers())"
```
**Résultat attendu** : `['ODBC Driver 18 for SQL Server']`

### Test 5: Firebase initialisé
```bash
docker exec samaconso_api python -c "import firebase_admin; print('✅ Firebase OK')"
```

### Test 6: Redis fonctionnel
```bash
docker exec samaconso_redis redis-cli ping
```
**Résultat attendu** : `PONG`

### Test 7: RabbitMQ fonctionnel
```bash
docker exec samaconso_rabbitmq rabbitmq-diagnostics ping
```
**Résultat attendu** : `Ping succeeded`

### Test 8: Envoyer une notification test
```bash
docker exec samaconso_api python -c "
from app.firebase import send_pushNotification
from app.schemas.notification_schemas import PushNotification
import asyncio

# Remplacer par un vrai token FCM
test_notif = PushNotification(
    token='VOTRE_TOKEN_FCM_ICI',
    title='Test SamaConso',
    body='Test notification depuis Docker'
)

loop = asyncio.new_event_loop()
result = loop.run_until_complete(send_pushNotification(test_notif))
loop.close()

print(f'Status: {result.status_code}')
print('✅ OK' if result.status_code == 200 else '❌ ERREUR')
"
```

---

## Résolution de Problèmes

### Problème 1: Conteneur "Unhealthy"

#### Diagnostic
```bash
docker ps
docker logs <nom_conteneur> --tail 50
```

#### Solution
```bash
# Redémarrer le conteneur
docker restart <nom_conteneur>

# Si ça ne marche pas, recréer le conteneur
docker-compose -f docker-compose.fixed.yml up -d --force-recreate <service>
```

### Problème 2: SQL Server - "Connection refused"

#### Vérifications
```bash
# Vérifier que les IPs sont correctement mappées
docker exec samaconso_api cat /etc/hosts | grep srv-

# Tester la connectivité réseau
docker exec samaconso_api ping -c 2 10.101.2.87
docker exec samaconso_api ping -c 2 10.101.3.243
```

#### Solution
Si les IPs ont changé, modifier `docker-compose.fixed.yml` section `extra_hosts` :
```yaml
extra_hosts:
  - "srv-asreports:NOUVELLE_IP"
  - "srv-commercial:NOUVELLE_IP"
```
Puis redémarrer :
```bash
docker-compose -f docker-compose.fixed.yml down
docker-compose -f docker-compose.fixed.yml up -d
```

### Problème 3: Firebase - "SSL Certificate Error"

#### Vérification
```bash
docker exec samaconso_api python -c "
import ssl
print('SSL Context:', ssl._create_default_https_context)
"
```

#### Solution
Si la configuration SSL a été perdue, la réappliquer :
```bash
# Recréer sitecustomize.py
docker exec -u root samaconso_api bash -c "
cat > /home/appuser/.local/lib/python3.10/site-packages/sitecustomize.py << 'EOF'
import ssl
import os
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')
try:
    import urllib3
    urllib3.disable_warnings()
except:
    pass
EOF
chown appuser:appuser /home/appuser/.local/lib/python3.10/site-packages/sitecustomize.py
"

# Redémarrer
docker restart samaconso_api samaconso_celery_worker
```

### Problème 4: Port déjà utilisé

#### Erreur
```
Bind for 0.0.0.0:8000 failed: port is already allocated
```

#### Solution
```bash
# Trouver le processus qui utilise le port
netstat -ano | findstr :8000

# Arrêter le processus ou changer le port dans docker-compose.fixed.yml
ports:
  - "8001:8000"  # Utiliser le port 8001 à la place
```

### Problème 5: "Out of disk space"

#### Diagnostic
```bash
# Voir l'espace utilisé par Docker
docker system df
```

#### Nettoyage
```bash
# Supprimer les images inutilisées
docker image prune -a

# Supprimer les conteneurs arrêtés
docker container prune

# Supprimer les volumes inutilisés
docker volume prune

# Nettoyage complet (ATTENTION: supprime tout ce qui n'est pas utilisé)
docker system prune -a --volumes
```

---

## Maintenance

### Sauvegarder les données

#### Sauvegarder la base PostgreSQL
```bash
docker exec samaconso_api pg_dump -U <user> -d <database> > backup_postgres.sql
```

#### Sauvegarder les volumes Docker
```bash
docker run --rm -v samaconso_redis_data:/data -v D:\backups:/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .
docker run --rm -v samaconso_rabbitmq_data:/data -v D:\backups:/backup alpine tar czf /backup/rabbitmq_backup.tar.gz -C /data .
docker run --rm -v samaconso_minio_data:/data -v D:\backups:/backup alpine tar czf /backup/minio_backup.tar.gz -C /data .
```

### Mettre à jour l'application

#### Si vous avez modifié le code Python
```bash
# 1. Reconstruire l'image
docker build -f Dockerfile.fixed -t samaconso_api:with-fixes .

# 2. Redémarrer les services
docker-compose -f docker-compose.fixed.yml down
docker-compose -f docker-compose.fixed.yml up -d
```

#### Si vous avez modifié uniquement docker-compose.fixed.yml
```bash
docker-compose -f docker-compose.fixed.yml down
docker-compose -f docker-compose.fixed.yml up -d
```

### Vérifier les mises à jour des images

```bash
# Voir les images utilisées
docker images | grep samaconso

# Voir la date de création
docker inspect samaconso_api:with-fixes | grep Created
```

### Sauvegarder les images corrigées

```bash
# Exporter l'image API
docker save samaconso_api:with-fixes -o samaconso_api_backup.tar

# Exporter l'image Worker
docker save samaconso_celery_worker:with-fixes -o samaconso_worker_backup.tar
```

### Restaurer une image sauvegardée

```bash
docker load -i samaconso_api_backup.tar
docker load -i samaconso_worker_backup.tar
```

---

## Commandes Avancées

### Exécuter une commande dans un conteneur

```bash
# Shell interactif
docker exec -it samaconso_api bash

# Commande Python directe
docker exec samaconso_api python -c "print('Hello')"

# Commande avec root
docker exec -u root samaconso_api apt-get update
```

### Copier des fichiers vers/depuis un conteneur

```bash
# Copier du local vers le conteneur
docker cp local_file.txt samaconso_api:/app/

# Copier du conteneur vers le local
docker cp samaconso_api:/app/logs/app.log ./logs_backup/
```

### Inspecter un conteneur

```bash
# Voir toute la configuration
docker inspect samaconso_api

# Voir uniquement l'IP
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' samaconso_api

# Voir les variables d'environnement
docker exec samaconso_api env
```

### Surveiller les ressources en temps réel

```bash
# CPU et Mémoire de tous les conteneurs
docker stats

# Ressources d'un conteneur spécifique
docker stats samaconso_api
```

### Nettoyer les logs Docker

```bash
# Voir la taille des logs
docker inspect --format='{{.LogPath}}' samaconso_api | xargs ls -lh

# Truncate les logs (Linux/WSL)
truncate -s 0 $(docker inspect --format='{{.LogPath}}' samaconso_api)
```

### Créer un snapshot d'un conteneur

```bash
# Sauvegarder l'état actuel
docker commit samaconso_api samaconso_api:snapshot-$(date +%Y%m%d)

# Lister les snapshots
docker images | grep samaconso
```

### Restaurer depuis un snapshot

```bash
# Modifier docker-compose.fixed.yml pour utiliser le snapshot
image: samaconso_api:snapshot-20251112

# Redémarrer
docker-compose -f docker-compose.fixed.yml up -d
```

---

## Configuration Réseau

### Serveurs SQL Server
- **SIC** : srv-asreports → 10.101.2.87
- **Postpaid** : srv-commercial → 10.101.3.243

### Proxy Senelec
- **IP** : 10.101.201.204
- **Port** : 8080
- **SSL** : Désactivé dans les conteneurs (sitecustomize.py)

### Ports Exposés

| Service | Port Local | Port Conteneur | Description |
|---------|------------|----------------|-------------|
| API FastAPI | 8000 | 8000 | API principale |
| Flower | 5555 | 5555 | Monitoring Celery |
| RabbitMQ AMQP | 5672 | 5672 | Message broker |
| RabbitMQ Management | 15672 | 15672 | Interface web |
| MinIO API | 9000 | 9000 | Stockage S3 |
| MinIO Console | 9001 | 9001 | Interface web |
| Redis | 6379 | 6379 | Cache |

---

## Checklist de Santé Système

### Vérification Quotidienne (5 minutes)

```bash
# 1. État des conteneurs
docker ps

# 2. Test API
curl http://localhost:8000

# 3. Logs des erreurs (dernières 50 lignes)
docker logs samaconso_api --tail 50 | grep -i error
docker logs samaconso_celery_worker --tail 50 | grep -i error
```

### Vérification Hebdomadaire (15 minutes)

```bash
# 1. Espace disque
docker system df

# 2. Test SQL Server
docker exec samaconso_api python -c "from app.database import get_db_connection_sic; print('OK' if get_db_connection_sic() else 'FAIL')"

# 3. Test Firebase
docker exec samaconso_api python -c "import firebase_admin; print('OK')"

# 4. Vérifier Flower
# Ouvrir http://localhost:5555 et vérifier les workers actifs

# 5. Vérifier RabbitMQ
# Ouvrir http://localhost:15672 et vérifier les queues
```

### Vérification Mensuelle (30 minutes)

```bash
# 1. Sauvegarde complète des volumes
# (Voir section Maintenance > Sauvegarder les données)

# 2. Mise à jour des images de base
docker-compose -f docker-compose.fixed.yml pull redis rabbitmq minio

# 3. Nettoyage Docker
docker system prune -f

# 4. Vérifier les logs de sécurité
docker logs samaconso_api --since 30d | grep -i "unauthorized\|failed\|error"
```

---

## Support et Documentation

### Fichiers de Documentation
- **[SUCCES_COMPLET.md](SUCCES_COMPLET.md)** - Historique du déploiement et solutions
- **[DEPLOIEMENT_AVEC_PROXY.md](DEPLOIEMENT_AVEC_PROXY.md)** - Configuration proxy Senelec
- **[FIREBASE_PROXY_SENELEC.md](FIREBASE_PROXY_SENELEC.md)** - Solutions Firebase SSL
- **[GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md)** - Ce document

### Commandes de Diagnostic Rapide

```bash
# Script de diagnostic complet
docker exec samaconso_api python -c "
print('=== DIAGNOSTIC SAMA CONSO ===')
print('1. Drivers ODBC:', end=' ')
import pyodbc
print('OK' if 'ODBC Driver 18 for SQL Server' in pyodbc.drivers() else 'FAIL')

print('2. SQL SIC:', end=' ')
from app.database import get_db_connection_sic
print('OK' if get_db_connection_sic() else 'FAIL')

print('3. SQL Postpaid:', end=' ')
from app.database import get_db_connection_postpaid
print('OK' if get_db_connection_postpaid() else 'FAIL')

print('4. Firebase:', end=' ')
import firebase_admin
print('OK')

print('=== FIN DIAGNOSTIC ===')
"
```

---

## Contacts Utiles

**Équipe IT Senelec** : Pour whitelist Firebase (oauth2.googleapis.com, fcm.googleapis.com)
**Administrateur Réseau** : Pour les IPs des serveurs SQL (10.101.2.87, 10.101.3.243)
**Proxy Senelec** : 10.101.201.204:8080

---

**Date de création** : 2025-11-12
**Version** : 1.0
**Statut** : Production Ready ✅
