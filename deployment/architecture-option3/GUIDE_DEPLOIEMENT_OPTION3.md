# Guide de Déploiement Pas à Pas - Architecture Option 3

## Architecture

### SRV-MOBAPPBD (10.101.1.212)
- PostgreSQL 15 PRIMARY (natif) + PgBouncer
- MinIO Node 1 (natif, distribué)

### SRV-MOBAPP1 (10.101.1.210)
- API FastAPI (Docker)
- Celery Worker urgent/high (Docker)
- Redis Master (Docker) + Sentinel
- RabbitMQ Node 1 (Docker)
- PostgreSQL Standby (natif)
- MinIO Node 2 (natif)
- Nginx Load Balancer

### SRV-MOBAPP2 (10.101.1.211)
- API FastAPI (Docker)
- Celery Worker normal/low (Docker)
- Redis Replica (Docker) + Sentinel
- RabbitMQ Node 2 (Docker)
- MinIO Node 3 (natif)

---

## PRÉPARATION (Sur votre machine locale)

### 1. Cloner le repository GitHub

```bash
# Cloner le repository
git clone <URL_DU_REPO_GITHUB>
cd samaconsoapi-dev_pcyn_new

# Vérifier que les fichiers de déploiement sont présents
ls -la deployment/architecture-option3/
```

---

## ÉTAPE 1 : SRV-MOBAPPBD (10.101.1.212)

### 1.1 Connexion au serveur

```bash
ssh user@10.101.1.212
```

### 1.2 Préparation du système

```bash
# Mise à jour
sudo apt-get update && sudo apt-get upgrade -y

# Installation des outils de base
sudo apt-get install -y curl wget git vim htop net-tools

# Créer les répertoires de données
sudo mkdir -p /data/{postgres,redis,rabbitmq,minio}
sudo chmod 755 /data
```

### 1.3 Récupération des fichiers de déploiement

**Option A : Via Git (Recommandé)**
```bash
cd /tmp
git clone <URL_DU_REPO_GITHUB>
cd samaconsoapi-dev_pcyn_new
```

**Option B : Via SCP (si Git n'est pas disponible)**
```bash
# Depuis votre machine locale
scp -r deployment/ user@10.101.1.212:/tmp/

# Sur le serveur
cd /tmp
```

### 1.4 Installation PostgreSQL Primary + PgBouncer

```bash
cd /tmp/samaconsoapi-dev_pcyn_new/deployment/architecture-option3/SRV-MOBAPPBD

# Rendre le script exécutable
chmod +x install-postgres-primary.sh

# Exécuter l'installation
sudo bash install-postgres-primary.sh
```

**Vérification :**
```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -c "SELECT version();"

# Vérifier PgBouncer
sudo systemctl status pgbouncer
psql -h localhost -p 6432 -U samaconso_app -d samaconso -c "SELECT 1;"
```

### 1.5 Installation MinIO Node 1

```bash
cd /tmp/samaconsoapi-dev_pcyn_new/deployment/architecture-option3/shared

# Rendre le script exécutable
chmod +x install-minio-distributed.sh

# Exécuter l'installation
sudo bash install-minio-distributed.sh SRV-MOBAPPBD 10.101.1.212 1
```

**Vérification :**
```bash
# Vérifier MinIO
sudo systemctl status minio
curl http://localhost:9000/minio/health/live
```

### 1.6 Configuration du firewall

```bash
# Vérifier les règles
sudo ufw status

# Si nécessaire, ouvrir les ports
sudo ufw allow 5432/tcp  # PostgreSQL (local uniquement)
sudo ufw allow 6432/tcp  # PgBouncer
sudo ufw allow 9000/tcp  # MinIO API
sudo ufw allow 9001/tcp  # MinIO Console
```

---

## ÉTAPE 2 : SRV-MOBAPP1 (10.101.1.210)

### 2.1 Connexion au serveur

```bash
ssh user@10.101.1.210
```

### 2.2 Préparation du système

```bash
# Mise à jour
sudo apt-get update && sudo apt-get upgrade -y

# Installation Docker (si pas déjà installé)
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    newgrp docker
fi

# Installation Docker Compose
sudo apt-get install -y docker-compose-plugin

# Créer les répertoires
sudo mkdir -p /data/{postgres,redis,rabbitmq,minio}
sudo mkdir -p /opt/samaconso
```

### 2.3 Récupération des fichiers

**Option A : Via Git**
```bash
cd /tmp
git clone <URL_DU_REPO_GITHUB>
cd samaconsoapi-dev_pcyn_new
```

**Option B : Via SCP**
```bash
# Depuis votre machine locale
scp -r deployment/ user@10.101.1.210:/tmp/
```

### 2.4 Installation PostgreSQL Standby

```bash
cd /tmp/samaconsoapi-dev_pcyn_new/deployment/architecture-option3/SRV-MOBAPP1

# Rendre le script exécutable
chmod +x install-postgres-standby.sh

# Exécuter l'installation
sudo bash install-postgres-standby.sh
```

**Vérification :**
```bash
# Vérifier la réplication
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"
# Doit retourner 't' (true) pour un standby
```

### 2.5 Installation MinIO Node 2

```bash
cd /tmp/samaconsoapi-dev_pcyn_new/deployment/architecture-option3/shared

# Rendre le script exécutable
chmod +x install-minio-distributed.sh

# Exécuter l'installation
sudo bash install-minio-distributed.sh SRV-MOBAPP1 10.101.1.210 2
```

### 2.6 Récupération de l'API depuis GitHub

```bash
# Cloner le repository dans /opt/samaconso
cd /opt/samaconso
git clone <URL_DU_REPO_GITHUB> .

# Ou si vous avez déjà cloné dans /tmp
cd /opt/samaconso
cp -r /tmp/samaconsoapi-dev_pcyn_new/* .
```

### 2.7 Configuration Docker Compose

```bash
cd /opt/samaconso

# Copier la configuration Docker Compose
cp deployment/architecture-option3/SRV-MOBAPP1/docker-compose.app-redis.yml docker-compose.yml

# Copier la configuration Redis Sentinel
mkdir -p redis
cp deployment/architecture-option3/SRV-MOBAPP1/redis/sentinel.conf redis/

# Créer le fichier .env.production
cat > .env.production << 'EOF'
# Configuration serveur
SERVER_NAME=SRV-MOBAPP1
SERVER_IP=10.101.1.210

# Base de données via PgBouncer
DATABASE_URL=postgresql://samaconso_app:Senelec2024!@10.101.1.212:6432/samaconso

# Redis Master (local)
REDIS_URL=redis://:Senelec2024!@redis-master:6379/0
REDIS_SENTINEL_HOSTS=redis-sentinel:26379
REDIS_SENTINEL_MASTER=samaconso-redis

# RabbitMQ (sur SRV-MOBAPP2)
RABBITMQ_URL=amqp://admin:Senelec2024!@10.101.1.211:5672/
CELERY_BROKER_URL=amqp://admin:Senelec2024!@10.101.1.211:5672/
CELERY_RESULT_BACKEND=redis://:Senelec2024!@redis-master:6379/0

# MinIO (distributed)
MINIO_ENDPOINT=10.101.1.212:9000,10.101.1.210:9000,10.101.1.211:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=Senelec2024!
MINIO_SECURE=false

# Firebase
FIREBASE_CREDENTIALS_PATH=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
GOOGLE_APPLICATION_CREDENTIALS=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# Flower
FLOWER_USER=admin
FLOWER_PASS=Senelec2024!

# JWT
SECRET_KEY=$3?N2LEC123
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
EOF

chmod 600 .env.production
```

### 2.8 Construction de l'image Docker

```bash
cd /opt/samaconso

# Construire l'image
docker build -t samaconso_api:with-fixes .
docker tag samaconso_api:with-fixes samaconso_celery_worker:with-fixes
```

### 2.9 Démarrage des services Docker

```bash
cd /opt/samaconso

# Démarrer les services
docker-compose up -d

# Vérifier les conteneurs
docker-compose ps

# Vérifier les logs
docker-compose logs -f
```

**Vérification :**
```bash
# Vérifier l'API
curl http://localhost:8000/health

# Vérifier Redis
docker exec redis_master redis-cli -a Senelec2024! ping

# Vérifier RabbitMQ
docker exec rabbitmq_node1 rabbitmq-diagnostics ping
```

### 2.10 Configuration Nginx Load Balancer

```bash
cd /tmp/samaconsoapi-dev_pcyn_new/deployment/scripts

# Rendre le script exécutable
chmod +x setup-nginx-lb.sh

# Exécuter la configuration
sudo bash setup-nginx-lb.sh
```

**Vérification :**
```bash
# Tester via Nginx
curl http://localhost/health

# Vérifier Nginx
sudo systemctl status nginx
```

---

## ÉTAPE 3 : SRV-MOBAPP2 (10.101.1.211)

### 3.1 Connexion au serveur

```bash
ssh user@10.101.1.211
```

### 3.2 Préparation du système

```bash
# Mise à jour
sudo apt-get update && sudo apt-get upgrade -y

# Installation Docker (si pas déjà installé)
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    newgrp docker
fi

# Installation Docker Compose
sudo apt-get install -y docker-compose-plugin

# Créer les répertoires
sudo mkdir -p /data/{redis,rabbitmq,minio}
sudo mkdir -p /opt/samaconso
```

### 3.3 Récupération des fichiers

**Option A : Via Git**
```bash
cd /tmp
git clone <URL_DU_REPO_GITHUB>
cd samaconsoapi-dev_pcyn_new
```

**Option B : Via SCP**
```bash
# Depuis votre machine locale
scp -r deployment/ user@10.101.1.211:/tmp/
```

### 3.4 Installation MinIO Node 3

```bash
cd /tmp/samaconsoapi-dev_pcyn_new/deployment/architecture-option3/shared

# Rendre le script exécutable
chmod +x install-minio-distributed.sh

# Exécuter l'installation
sudo bash install-minio-distributed.sh SRV-MOBAPP2 10.101.1.211 3
```

### 3.5 Récupération de l'API depuis GitHub

```bash
# Cloner le repository dans /opt/samaconso
cd /opt/samaconso
git clone <URL_DU_REPO_GITHUB> .

# Ou si vous avez déjà cloné dans /tmp
cd /opt/samaconso
cp -r /tmp/samaconsoapi-dev_pcyn_new/* .
```

### 3.6 Configuration Docker Compose

```bash
cd /opt/samaconso

# Copier la configuration Docker Compose
cp deployment/architecture-option3/SRV-MOBAPP2/docker-compose.app-rabbitmq.yml docker-compose.yml

# Copier la configuration Redis Sentinel
mkdir -p redis
cp deployment/architecture-option3/SRV-MOBAPP2/redis/sentinel.conf redis/

# Créer le fichier .env.production
cat > .env.production << 'EOF'
# Configuration serveur
SERVER_NAME=SRV-MOBAPP2
SERVER_IP=10.101.1.211

# Base de données via PgBouncer
DATABASE_URL=postgresql://samaconso_app:Senelec2024!@10.101.1.212:6432/samaconso

# Redis Replica (local)
REDIS_URL=redis://:Senelec2024!@redis-replica:6379/0
REDIS_SENTINEL_HOSTS=redis-sentinel:26379
REDIS_SENTINEL_MASTER=samaconso-redis

# RabbitMQ (local - Node 2)
RABBITMQ_URL=amqp://admin:Senelec2024!@rabbitmq-node2:5672/
CELERY_BROKER_URL=amqp://admin:Senelec2024!@rabbitmq-node2:5672/
CELERY_RESULT_BACKEND=redis://:Senelec2024!@redis-replica:6379/0

# MinIO (distributed)
MINIO_ENDPOINT=10.101.1.212:9000,10.101.1.210:9000,10.101.1.211:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=Senelec2024!
MINIO_SECURE=false

# Firebase
FIREBASE_CREDENTIALS_PATH=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
GOOGLE_APPLICATION_CREDENTIALS=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# JWT
SECRET_KEY=$3?N2LEC123
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
EOF

chmod 600 .env.production
```

### 3.7 Construction de l'image Docker

```bash
cd /opt/samaconso

# Construire l'image
docker build -t samaconso_api:with-fixes .
docker tag samaconso_api:with-fixes samaconso_celery_worker:with-fixes
```

### 3.8 Démarrage des services Docker

```bash
cd /opt/samaconso

# Démarrer les services
docker-compose up -d

# Vérifier les conteneurs
docker-compose ps

# Vérifier les logs
docker-compose logs -f
```

### 3.9 Configuration RabbitMQ Cluster

```bash
# ATTENTION: Attendre que RabbitMQ Node 1 soit prêt sur SRV-MOBAPP1
# Vérifier d'abord sur SRV-MOBAPP1:
# docker exec rabbitmq_node1 rabbitmq-diagnostics ping

cd /tmp/samaconsoapi-dev_pcyn_new/deployment/architecture-option3/shared

# Rendre le script exécutable
chmod +x setup-rabbitmq-cluster.sh

# Exécuter la configuration du cluster
sudo bash setup-rabbitmq-cluster.sh
```

**Vérification :**
```bash
# Vérifier le cluster
docker exec rabbitmq_node2 rabbitmqctl cluster_status

# Vérifier l'API
curl http://localhost:8000/health

# Vérifier Redis Replica
docker exec redis_replica redis-cli -a Senelec2024! ping
```

---

## ÉTAPE 4 : Initialisation de la Base de Données

### 4.1 Exécuter les migrations Alembic

```bash
# Sur SRV-MOBAPP1 ou SRV-MOBAPP2
cd /opt/samaconso

# Exécuter les migrations
docker-compose exec api alembic upgrade head
```

**Vérification :**
```bash
# Vérifier les tables
docker-compose exec api python -c "from app.database import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"
```

---

## ÉTAPE 5 : Vérifications Finales

### 5.1 Vérification de tous les services

**Sur SRV-MOBAPPBD :**
```bash
# PostgreSQL
sudo systemctl status postgresql
psql -h localhost -p 6432 -U samaconso_app -d samaconso -c "SELECT version();"

# PgBouncer
sudo systemctl status pgbouncer

# MinIO
sudo systemctl status minio
curl http://localhost:9000/minio/health/live
```

**Sur SRV-MOBAPP1 :**
```bash
# API
curl http://localhost:8000/health

# Redis
docker exec redis_master redis-cli -a Senelec2024! ping

# RabbitMQ
docker exec rabbitmq_node1 rabbitmq-diagnostics ping

# PostgreSQL Standby
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"

# Nginx
curl http://localhost/health
sudo systemctl status nginx
```

**Sur SRV-MOBAPP2 :**
```bash
# API
curl http://localhost:8000/health

# Redis Replica
docker exec redis_replica redis-cli -a Senelec2024! ping

# RabbitMQ Cluster
docker exec rabbitmq_node2 rabbitmqctl cluster_status
```

### 5.2 Test de charge via Nginx

```bash
# Depuis votre machine locale ou un autre serveur
curl http://10.101.1.210/health

# Vérifier que les deux serveurs répondent
curl http://10.101.1.210:8000/health
curl http://10.101.1.211:8000/health
```

### 5.3 Vérification des workers Celery

```bash
# Sur SRV-MOBAPP1
docker-compose logs celery_worker_urgent

# Sur SRV-MOBAPP2
docker-compose logs celery_worker_normal

# Accéder à Flower (sur SRV-MOBAPP1)
# http://10.101.1.210:5555 (admin/Senelec2024!)
```

---

## COMMANDES UTILES

### Monitoring

```bash
# Vérifier l'utilisation des ressources
htop
docker stats

# Logs en temps réel
docker-compose logs -f api
docker-compose logs -f celery_worker_urgent

# Statut PostgreSQL
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"
sudo -u postgres psql -c "SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;"
```

### Maintenance

```bash
# Redémarrer un service
docker-compose restart api

# Mettre à jour l'application
cd /opt/samaconso
git pull
docker-compose build api
docker-compose up -d api

# Backup PostgreSQL
sudo -u postgres pg_dump samaconso > backup_$(date +%Y%m%d).sql
```

### Dépannage

```bash
# Vérifier les connexions réseau
telnet 10.101.1.212 6432  # PgBouncer
telnet 10.101.1.210 6379 # Redis Master
telnet 10.101.1.211 5672 # RabbitMQ Node 2

# Vérifier les logs système
journalctl -u postgresql -f
journalctl -u pgbouncer -f
journalctl -u minio -f
```

---

## CHECKLIST FINALE

- [ ] PostgreSQL Primary fonctionne sur SRV-MOBAPPBD
- [ ] PgBouncer accessible depuis les serveurs app
- [ ] PostgreSQL Standby configuré sur SRV-MOBAPP1
- [ ] MinIO distribué fonctionne sur les 3 serveurs
- [ ] Redis Master + Sentinel sur SRV-MOBAPP1
- [ ] Redis Replica + Sentinel sur SRV-MOBAPP2
- [ ] RabbitMQ Cluster configuré (2 nodes)
- [ ] API fonctionne sur SRV-MOBAPP1 et SRV-MOBAPP2
- [ ] Workers Celery fonctionnent (urgent sur SRV-MOBAPP1, normal sur SRV-MOBAPP2)
- [ ] Nginx Load Balancer fonctionne
- [ ] Migrations Alembic exécutées
- [ ] Health checks passent sur tous les services
- [ ] Flower accessible
- [ ] Tous les services redémarrés après configuration

---

## SUPPORT

En cas de problème :
1. Vérifier les logs : `docker-compose logs -f`
2. Vérifier les services système : `systemctl status <service>`
3. Vérifier la connectivité réseau : `telnet <ip> <port>`
4. Consulter les logs système : `journalctl -u <service> -f`

---

## NOTES IMPORTANTES

1. **Ordre de déploiement** : Respecter l'ordre SRV-MOBAPPBD → SRV-MOBAPP1 → SRV-MOBAPP2
2. **RabbitMQ Cluster** : Attendre que Node 1 soit prêt avant de configurer le cluster
3. **MinIO Distributed** : Tous les nodes doivent être démarrés pour que le mode distribué fonctionne
4. **Mots de passe** : Changer tous les mots de passe par défaut en production
5. **Firewall** : Vérifier que tous les ports nécessaires sont ouverts entre les serveurs

