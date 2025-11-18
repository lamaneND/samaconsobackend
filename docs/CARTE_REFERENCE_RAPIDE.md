# 📋 Carte de Référence Rapide - SamaConso API

**Version**: 2.0.0 | **Date**: 2025-11-12 | **Statut**: ✅ Production Ready

---

## 🚀 Démarrage Ultra-Rapide

```bash
# Démarrer
docker-compose -f docker-compose.fixed.yml up -d

# Vérifier
check_health.bat

# Tester notification
send_test_notification.bat <user_id>
```

---

## 🌐 URLs des Services

| Service | URL | Login |
|---------|-----|-------|
| **API** | http://localhost:8000/docs | - |
| **Flower** | http://localhost:5555 | admin / admin |
| **RabbitMQ** | http://localhost:15672 | guest / guest |
| **MinIO** | http://localhost:9001 | minioadmin / minioadmin |

---

## 🔧 Commandes Essentielles

### Gestion Générale
```bash
# Démarrer tous les services
docker-compose -f docker-compose.fixed.yml up -d

# Arrêter tous les services
docker-compose -f docker-compose.fixed.yml down

# Voir statut
docker ps

# Voir tous les conteneurs (même arrêtés)
docker ps -a
```

### Logs
```bash
# API
docker logs samaconso_api -f

# Celery Worker
docker logs samaconso_celery_worker -f

# Tous les services
docker-compose -f docker-compose.fixed.yml logs -f

# Dernières 50 lignes
docker logs samaconso_api --tail 50
```

### Redémarrage
```bash
# Redémarrer API
docker-compose -f docker-compose.fixed.yml restart api

# Redémarrer Worker
docker-compose -f docker-compose.fixed.yml restart celery_worker

# Redémarrer tout
docker-compose -f docker-compose.fixed.yml restart
```

### Inspection
```bash
# Entrer dans conteneur API
docker exec -it samaconso_api bash

# Vérifier drivers ODBC
docker exec samaconso_api python -c "import pyodbc; print(pyodbc.drivers())"

# Voir configuration réseau
docker exec samaconso_api cat /etc/hosts | grep srv-
```

---

## 🆘 Résolution Rapide

### Problème: API ne répond pas
```bash
# 1. Vérifier conteneur
docker ps | grep samaconso_api

# 2. Voir logs
docker logs samaconso_api --tail 50

# 3. Redémarrer
docker-compose -f docker-compose.fixed.yml restart api

# 4. Tester
curl http://localhost:8000
```

### Problème: Notifications non reçues
```bash
# 1. Vérifier worker
docker logs samaconso_celery_worker --tail 50

# 2. Vérifier queues (Flower)
curl -s "http://localhost:5555/api/workers" --user admin:admin

# 3. Redémarrer worker
docker-compose -f docker-compose.fixed.yml restart celery_worker

# 4. Tester
send_test_notification.bat <user_id>
```

### Problème: SQL Server non accessible
```bash
# 1. Vérifier drivers
docker exec samaconso_api python -c "import pyodbc; print(pyodbc.drivers())"

# 2. Vérifier hosts
docker exec samaconso_api cat /etc/hosts | grep srv-

# 3. Si manquant, voir PROBLEMES_RESOLUS_FINAL.md
```

### Problème: Conteneur "unhealthy"
```bash
# 1. Identifier conteneur
docker ps

# 2. Voir détails health
docker inspect <conteneur_id> | grep -A 10 Health

# 3. Redémarrer
docker restart <conteneur_name>
```

### Problème: Espace disque
```bash
# Nettoyer images inutilisées
docker system prune -a

# Nettoyer volumes
docker volume prune

# Voir espace utilisé
docker system df
```

---

## 📊 Vérifications Rapides

### Check #1: Services Running
```bash
docker ps
# Résultat attendu: 6 conteneurs "Up"
```

### Check #2: API Accessible
```bash
curl http://localhost:8000
# Résultat attendu: {"message":"SAMA CONSO","version":"2.0.0","status":"running"}
```

### Check #3: ODBC Drivers
```bash
docker exec samaconso_api python -c "import pyodbc; print(pyodbc.drivers())"
# Résultat attendu: ['ODBC Driver 18 for SQL Server']
```

### Check #4: Queues Celery
```bash
curl -s "http://localhost:5555/api/workers" --user admin:admin | grep -o "urgent\|high_priority\|normal\|low_priority"
# Résultat attendu: Les 4 queues listées
```

### Check #5: RabbitMQ
```bash
curl -u guest:guest http://localhost:15672/api/overview
# Résultat attendu: JSON avec infos RabbitMQ
```

---

## 🔍 Diagnostic Complet

### Script de Santé Automatique
```bash
check_health.bat
```

### Diagnostic Manuel
```bash
# 1. Services
docker ps

# 2. API
curl http://localhost:8000

# 3. Drivers
docker exec samaconso_api python -c "import pyodbc; print(pyodbc.drivers())"

# 4. SQL Hosts
docker exec samaconso_api cat /etc/hosts | grep srv-

# 5. Redis
docker exec samaconso_redis redis-cli ping

# 6. RabbitMQ
curl -u guest:guest http://localhost:15672/api/overview

# 7. MinIO
curl http://localhost:9000/minio/health/live

# 8. Celery
curl -s "http://localhost:5555/api/workers" --user admin:admin
```

---

## 🌐 Configuration Réseau Senelec

```
Proxy Senelec:     10.101.201.204:8080
SQL SIC:           10.101.2.87 (srv-asreports)
SQL Postpaid:      10.101.3.243 (srv-commercial)
```

---

## 🐳 Images Docker

```
API:          samaconso_api:with-fixes
Worker:       samaconso_celery_worker:with-fixes
Redis:        redis:7-alpine
RabbitMQ:     rabbitmq:3-management-alpine
MinIO:        minio/minio:latest
```

---

## 📂 Fichiers Importants

```
docker-compose.fixed.yml    Configuration principale
.env.docker.fixed          Variables d'environnement
Dockerfile.fixed           Image Docker
requirements.txt           Dépendances Python
check_health.bat          Script vérification
send_test_notification.bat Script test notification
```

---

## 📚 Documentation Principale

| Document | Pour Qui | Temps |
|----------|----------|-------|
| [README.md](README.md) | Tous | 5 min |
| [QUICKSTART.md](QUICKSTART.md) | Débutant | 2 min |
| [GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md) | Admin | 30 min |
| [PROBLEMES_RESOLUS_FINAL.md](PROBLEMES_RESOLUS_FINAL.md) | Technique | 20 min |
| [PRODUCTION_README.md](PRODUCTION_README.md) | Production | 15 min |
| [DOCUMENTATION_COMPLETE.md](DOCUMENTATION_COMPLETE.md) | Vue d'ensemble | 10 min |

---

## ✅ Checklist Quotidienne

- [ ] Services running: `docker ps`
- [ ] API accessible: `curl http://localhost:8000`
- [ ] Logs propres: `docker logs samaconso_api --tail 20`
- [ ] Espace disque OK: `docker system df`
- [ ] RabbitMQ queues vides: http://localhost:15672
- [ ] Notifications fonctionnelles: `send_test_notification.bat <user_id>`

---

## 🔑 Credentials

| Service | Username | Password |
|---------|----------|----------|
| Flower | admin | admin |
| RabbitMQ | guest | guest |
| MinIO | minioadmin | minioadmin |

---

## 📞 Support

### Problème Connu?
→ [PROBLEMES_RESOLUS_FINAL.md](PROBLEMES_RESOLUS_FINAL.md)

### Nouveau Problème?
```bash
# 1. Collecter infos
docker ps
docker logs samaconso_api --tail 100 > api_logs.txt
docker logs samaconso_celery_worker --tail 100 > worker_logs.txt

# 2. Consulter documentation
INDEX_DOCUMENTATION.md

# 3. Chercher solution spécifique
grep -r "votre_erreur" *.md
```

---

## 🚀 Ports Exposés

```
8000  → API FastAPI
5555  → Flower (Monitoring Celery)
5672  → RabbitMQ AMQP
15672 → RabbitMQ Management
9000  → MinIO API
9001  → MinIO Console
6379  → Redis
```

---

## 💾 Backup Rapide

```bash
# Sauvegarder volumes
docker run --rm -v samaconso_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .

# Sauvegarder configuration
tar czf samaconso_config_backup.tar.gz docker-compose.fixed.yml .env.docker.fixed Dockerfile.fixed

# Sauvegarder images
docker save samaconso_api:with-fixes samaconso_celery_worker:with-fixes -o samaconso_images.tar
```

---

## 🔄 Mise à Jour Rapide

```bash
# 1. Arrêter
docker-compose -f docker-compose.fixed.yml down

# 2. Sauvegarder (optionnel)
docker commit samaconso_api samaconso_api:backup-$(date +%Y%m%d)

# 3. Mettre à jour code
git pull  # ou copier nouveaux fichiers

# 4. Rebuild (si nécessaire)
docker-compose -f docker-compose.fixed.yml build

# 5. Redémarrer
docker-compose -f docker-compose.fixed.yml up -d

# 6. Vérifier
check_health.bat
```

---

## 📈 Monitoring URLs

```
API Health:     http://localhost:8000/
API Docs:       http://localhost:8000/docs
Flower:         http://localhost:5555
RabbitMQ Mgmt:  http://localhost:15672
MinIO Console:  http://localhost:9001
```

---

## 🎯 Tests Rapides

```bash
# Test API
curl http://localhost:8000

# Test notification
send_test_notification.bat 9

# Test Redis
docker exec samaconso_redis redis-cli ping

# Test RabbitMQ
docker exec samaconso_rabbitmq rabbitmqctl status

# Test santé complète
check_health.bat
```

---

**💡 Conseil**: Gardez cette carte accessible pour référence rapide!

**📖 Documentation complète**: [INDEX_DOCUMENTATION.md](INDEX_DOCUMENTATION.md)

**🚀 Production**: [PRODUCTION_README.md](PRODUCTION_README.md)

---

**Version**: 2.0.0 | **Statut**: ✅ Production Ready | **Date**: 2025-11-12
