# 🚀 Guide de Mise en Production - SamaConso API

**Architecture**: 3 Serveurs Linux + Load Balancer F5
**Capacité**: 1 Million d'utilisateurs
**Date**: 2025-11-12

---

## 📋 Table des Matières

1. [Vue d'Ensemble de l'Architecture](#vue-densemble-de-larchitecture)
2. [Prérequis](#prérequis)
3. [Serveur 1: Base de Données](#serveur-1-base-de-données)
4. [Serveur 2: API & RabbitMQ](#serveur-2-api--rabbitmq)
5. [Serveur 3: Workers Celery & Redis](#serveur-3-workers-celery--redis)
6. [Configuration Load Balancer F5](#configuration-load-balancer-f5)
7. [Sécurité](#sécurité)
8. [Monitoring & Logs](#monitoring--logs)
9. [Procédures de Déploiement](#procédures-de-déploiement)
10. [Procédures de Rollback](#procédures-de-rollback)
11. [Maintenance](#maintenance)
12. [Troubleshooting](#troubleshooting)

---

## 🏗️ Vue d'Ensemble de l'Architecture

### Architecture Haute Disponibilité

```
                    ┌─────────────────────┐
                    │   Load Balancer F5  │
                    │   (IP Virtuelle)    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ↓                ↓                ↓
     ┌────────────────┐ ┌────────────┐ ┌────────────────┐
     │  SERVEUR 1     │ │ SERVEUR 2  │ │  SERVEUR 3     │
     │  Base Données  │ │  API       │ │  Workers       │
     └────────────────┘ └────────────┘ └────────────────┘
```

### Détails par Serveur

#### 🗄️ SERVEUR 1: Base de Données & Stockage
```
┌─────────────────────────────────────┐
│         SERVEUR 1 (Linux)           │
├─────────────────────────────────────┤
│  📊 PostgreSQL (Port 5432)          │
│     • Base principale samaconso     │
│     • Max connections: 200          │
│                                     │
│  🔄 PgBouncer (Port 6432)           │
│     • Pool mode: transaction        │
│     • Max client conn: 10,000       │
│     • Default pool size: 100        │
│                                     │
│  📦 MinIO (Ports 9000, 9001)        │
│     • Stockage S3-compatible        │
│     • Buckets: avatars, documents   │
│                                     │
│  🔐 Backup automatique quotidien    │
└─────────────────────────────────────┘
```

#### 🌐 SERVEUR 2: API & Message Broker
```
┌─────────────────────────────────────┐
│         SERVEUR 2 (Linux)           │
├─────────────────────────────────────┤
│  🐳 Docker Compose                  │
│                                     │
│  📡 API Instance 1 (Port 8001)      │
│     • Container: samaconso_api_1    │
│     • CPU: 2 cores                  │
│     • RAM: 2GB                      │
│     • Health check actif            │
│                                     │
│  📡 API Instance 2 (Port 8002)      │
│     • Container: samaconso_api_2    │
│     • CPU: 2 cores                  │
│     • RAM: 2GB                      │
│     • Health check actif            │
│                                     │
│  🐰 RabbitMQ (Ports 5672, 15672)    │
│     • Queues: urgent, high, normal, │
│                low_priority          │
│     • Management UI: 15672          │
│     • Disk free limit: 10GB         │
└─────────────────────────────────────┘
```

#### ⚙️ SERVEUR 3: Workers & Cache
```
┌─────────────────────────────────────┐
│         SERVEUR 3 (Linux)           │
├─────────────────────────────────────┤
│  🐳 Docker Compose                  │
│                                     │
│  👷 Celery Worker 1                 │
│     • Container: celery_worker_1    │
│     • Queues: urgent, high_priority │
│     • Concurrency: 4                │
│     • CPU: 2 cores / RAM: 2GB       │
│                                     │
│  👷 Celery Worker 2                 │
│     • Container: celery_worker_2    │
│     • Queues: normal, low_priority  │
│     • Concurrency: 4                │
│     • CPU: 2 cores / RAM: 2GB       │
│                                     │
│  🔴 Redis (Port 6379)               │
│     • Maxmemory: 4GB                │
│     • Maxmemory-policy: allkeys-lru │
│     • Persistence: AOF + RDB        │
│                                     │
│  🌺 Flower (Port 5555)              │
│     • Monitoring Celery             │
└─────────────────────────────────────┘
```

### Flux de Données

```
Client Mobile
     ↓
Load Balancer F5 (VIP: 10.101.X.X)
     ↓
API Instance 1 ou 2 (SERVEUR 2)
     ↓
     ├→ PostgreSQL (via PgBouncer) → SERVEUR 1
     ├→ Redis (cache) → SERVEUR 3
     ├→ MinIO (fichiers) → SERVEUR 1
     └→ RabbitMQ (tâches async) → SERVEUR 2
            ↓
       Celery Workers → SERVEUR 3
            ↓
       Firebase FCM (notifications push)
```

---

## 🔧 Prérequis

### Serveurs Linux

#### Spécifications Minimales

| Serveur | CPU | RAM | Disque | OS |
|---------|-----|-----|--------|-----|
| **Serveur 1** | 4 cores | 8GB | 200GB SSD | Ubuntu 22.04 LTS |
| **Serveur 2** | 4 cores | 8GB | 100GB SSD | Ubuntu 22.04 LTS |
| **Serveur 3** | 4 cores | 8GB | 100GB SSD | Ubuntu 22.04 LTS |

#### Logiciels Requis (Tous Serveurs)

```bash
# Docker & Docker Compose
Docker version: 24.0+
Docker Compose version: 2.20+

# Outils système
- curl
- wget
- git
- htop
- net-tools
```

### Réseau Senelec

#### Adresses IP

**À définir par l'équipe réseau**:
```
SERVEUR 1 (DB):      10.101.X.X1
SERVEUR 2 (API):     10.101.X.X2
SERVEUR 3 (Workers): 10.101.X.X3
Load Balancer F5:    10.101.X.X0 (VIP)

Proxy Senelec:       10.101.201.204:8080
SQL Server SIC:      10.101.2.87
SQL Server Postpaid: 10.101.3.243
```

#### Ports à Ouvrir sur Firewall

**Entre Load Balancer et SERVEUR 2**:
- `8001, 8002` → API instances

**Entre SERVEUR 2 et SERVEUR 1**:
- `6432` → PgBouncer (PostgreSQL)
- `9000` → MinIO API

**Entre SERVEUR 2 et SERVEUR 3**:
- `6379` → Redis

**Entre SERVEUR 3 et SERVEUR 2**:
- `5672` → RabbitMQ

**Accès Management (depuis réseau admin)**:
- `15672` → RabbitMQ Management (SERVEUR 2)
- `5555` → Flower Monitoring (SERVEUR 3)
- `9001` → MinIO Console (SERVEUR 1)

### Accès Externes

- ✅ Firebase FCM: `fcm.googleapis.com:443` (via proxy)
- ✅ OAuth2 Google: `oauth2.googleapis.com:443` (via proxy)

---

## 🗄️ SERVEUR 1: Base de Données

### 1.1 Installation PostgreSQL

```bash
#!/bin/bash
# Installation PostgreSQL 15

# Ajouter le dépôt PostgreSQL
sudo apt update
sudo apt install -y wget ca-certificates
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# Installer PostgreSQL 15
sudo apt update
sudo apt install -y postgresql-15 postgresql-contrib-15

# Démarrer et activer PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Vérifier l'installation
sudo systemctl status postgresql
```

### 1.2 Configuration PostgreSQL

**Fichier**: `/etc/postgresql/15/main/postgresql.conf`

```ini
# Connexions
listen_addresses = '*'              # Écouter sur toutes les interfaces
max_connections = 200               # Limité car PgBouncer gère le pooling

# Mémoire
shared_buffers = 2GB                # 25% de la RAM
effective_cache_size = 6GB          # 75% de la RAM
maintenance_work_mem = 512MB
work_mem = 10MB

# WAL (Write-Ahead Logging)
wal_level = replica
max_wal_size = 2GB
min_wal_size = 1GB
checkpoint_completion_target = 0.9

# Performances
random_page_cost = 1.1              # SSD
effective_io_concurrency = 200      # SSD

# Logging
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_min_duration_statement = 500    # Log queries > 500ms
log_line_prefix = '%m [%p] %u@%d '
log_timezone = 'Africa/Dakar'
```

**Fichier**: `/etc/postgresql/15/main/pg_hba.conf`

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     peer

# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256

# Connexions depuis les autres serveurs
host    samaconso       samaconso_user  10.101.X.X2/32         scram-sha-256
host    samaconso       samaconso_user  10.101.X.X3/32         scram-sha-256

# Connexion PgBouncer locale
host    samaconso       samaconso_user  127.0.0.1/32           scram-sha-256
```

### 1.3 Création de la Base de Données

```bash
#!/bin/bash
# Script: create_database.sh

# Se connecter en tant que postgres
sudo -u postgres psql <<EOF

-- Créer l'utilisateur
CREATE USER samaconso_user WITH PASSWORD 'VOTRE_MOT_DE_PASSE_SECURISE';

-- Créer la base de données
CREATE DATABASE samaconso
    WITH OWNER = samaconso_user
    ENCODING = 'UTF8'
    LC_COLLATE = 'fr_FR.UTF-8'
    LC_CTYPE = 'fr_FR.UTF-8'
    TEMPLATE = template0;

-- Donner les privilèges
GRANT ALL PRIVILEGES ON DATABASE samaconso TO samaconso_user;

-- Se connecter à la base
\c samaconso

-- Créer les extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Accorder les privilèges sur le schéma public
GRANT ALL ON SCHEMA public TO samaconso_user;

EOF

echo "✓ Base de données créée"
```

### 1.4 Installation et Configuration PgBouncer

```bash
#!/bin/bash
# Installation PgBouncer

sudo apt install -y pgbouncer

# Sauvegarder la config originale
sudo cp /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini.backup
```

**Fichier**: `/etc/pgbouncer/pgbouncer.ini`

```ini
[databases]
samaconso = host=127.0.0.1 port=5432 dbname=samaconso

[pgbouncer]
# Écoute
listen_addr = *
listen_port = 6432

# Authentification
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

# Pool configuration
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 100
min_pool_size = 20
reserve_pool_size = 10
reserve_pool_timeout = 5

# Timeouts
server_idle_timeout = 600
server_lifetime = 3600
server_connect_timeout = 15
query_timeout = 0
query_wait_timeout = 120
client_idle_timeout = 0

# Logs
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
stats_period = 60

# Admin
admin_users = postgres
stats_users = postgres, samaconso_user
```

**Fichier**: `/etc/pgbouncer/userlist.txt`

```
"samaconso_user" "SCRAM-SHA-256$HASH_DU_MOT_DE_PASSE"
```

**Générer le hash**:
```bash
# Se connecter à PostgreSQL
sudo -u postgres psql samaconso -c "SELECT concat('\"', usename, '\" \"', passwd, '\"') FROM pg_shadow WHERE usename = 'samaconso_user';"

# Copier le résultat dans /etc/pgbouncer/userlist.txt
```

**Démarrer PgBouncer**:
```bash
sudo systemctl start pgbouncer
sudo systemctl enable pgbouncer
sudo systemctl status pgbouncer

# Test de connexion
psql -h localhost -p 6432 -U samaconso_user samaconso -c "SELECT version();"
```

### 1.5 Installation MinIO

```bash
#!/bin/bash
# Installation MinIO

# Créer un utilisateur minio
sudo useradd -r -s /sbin/nologin minio

# Télécharger MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio
sudo chmod +x minio
sudo mv minio /usr/local/bin/

# Créer les répertoires
sudo mkdir -p /data/minio
sudo chown minio:minio /data/minio
sudo mkdir -p /etc/minio
```

**Fichier**: `/etc/default/minio`

```bash
# Variables d'environnement MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=VOTRE_MOT_DE_PASSE_SECURISE
MINIO_VOLUMES="/data/minio"
MINIO_OPTS="--console-address :9001"
MINIO_SERVER_URL="http://10.101.X.X1:9000"
```

**Fichier**: `/etc/systemd/system/minio.service`

```ini
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target
AssertFileIsExecutable=/usr/local/bin/minio

[Service]
Type=notify
User=minio
Group=minio
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server $MINIO_OPTS $MINIO_VOLUMES
Restart=always
LimitNOFILE=65536
TasksMax=infinity
TimeoutStopSec=infinity
SendSIGKILL=no

[Install]
WantedBy=multi-user.target
```

**Démarrer MinIO**:
```bash
sudo systemctl daemon-reload
sudo systemctl start minio
sudo systemctl enable minio
sudo systemctl status minio

# Vérifier
curl http://localhost:9000/minio/health/live
```

### 1.6 Backup Automatique

**Fichier**: `/usr/local/bin/backup_samaconso.sh`

```bash
#!/bin/bash
# Script de backup automatique

BACKUP_DIR="/data/backups/postgresql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="samaconso"
DB_USER="samaconso_user"
RETENTION_DAYS=7

# Créer le répertoire de backup
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
echo "Début du backup PostgreSQL..."
pg_dump -h localhost -U $DB_USER -F c -b -v -f "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.backup" $DB_NAME

# Backup MinIO (optionnel)
echo "Début du backup MinIO..."
tar -czf "$BACKUP_DIR/minio_${TIMESTAMP}.tar.gz" /data/minio

# Supprimer les backups de plus de 7 jours
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

echo "Backup terminé: ${TIMESTAMP}"
```

**Crontab** (sudo crontab -e):
```cron
# Backup quotidien à 2h du matin
0 2 * * * /usr/local/bin/backup_samaconso.sh >> /var/log/backup_samaconso.log 2>&1
```

---

## 🌐 SERVEUR 2: API & RabbitMQ

### 2.1 Installation Docker

```bash
#!/bin/bash
# Installation Docker et Docker Compose

# Désinstaller les anciennes versions
sudo apt remove docker docker-engine docker.io containerd runc

# Installer les prérequis
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Ajouter la clé GPG Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Ajouter le dépôt Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installer Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Ajouter l'utilisateur au groupe docker
sudo usermod -aG docker $USER

# Démarrer Docker
sudo systemctl start docker
sudo systemctl enable docker

# Vérifier
docker --version
docker compose version
```

### 2.2 Préparation de l'Application

```bash
#!/bin/bash
# Cloner le projet

# Créer le répertoire applicatif
sudo mkdir -p /opt/samaconso
sudo chown $USER:$USER /opt/samaconso
cd /opt/samaconso

# Cloner ou copier le code
# git clone <votre-repo> .
# OU copier depuis la machine de dev

# Créer les répertoires nécessaires
mkdir -p logs uploaded_files
```

### 2.3 Images Docker

**Option 1: Build local**
```bash
# Builder l'image
cd /opt/samaconso
docker build -f Dockerfile.fixed -t samaconso_api:production .
```

**Option 2: Import depuis dev**
```bash
# Sur la machine de dev
docker save samaconso_api:with-fixes -o samaconso_api.tar

# Transférer vers le serveur
scp samaconso_api.tar user@SERVEUR_2:/tmp/

# Sur SERVEUR 2
docker load -i /tmp/samaconso_api.tar
docker tag samaconso_api:with-fixes samaconso_api:production
```

### 2.4 Configuration Docker Compose

**Fichier**: `/opt/samaconso/docker-compose.production.yml`

```yaml
version: '3.8'

services:
  # RabbitMQ - Message Broker
  rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: samaconso_rabbitmq
    hostname: rabbitmq
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASS}
      - RABBITMQ_DEFAULT_VHOST=/
      - RABBITMQ_VM_MEMORY_HIGH_WATERMARK=0.7
    ports:
      - "5672:5672"   # AMQP
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  # API Instance 1
  api_1:
    image: samaconso_api:production
    container_name: samaconso_api_1
    hostname: api_1
    ports:
      - "8001:8000"
    env_file:
      - .env.production
    environment:
      - INSTANCE_ID=api_1
      - REDIS_URL=redis://10.101.X.X3:6379/0
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@rabbitmq:5672/
      - CELERY_BROKER_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@rabbitmq:5672/
      - CELERY_RESULT_BACKEND=redis://10.101.X.X3:6379/0
      - MINIO_ENDPOINT=10.101.X.X1:9000
      - DATABASE_URL=postgresql://samaconso_user:${DB_PASSWORD}@10.101.X.X1:6432/samaconso
      - HTTP_PROXY=http://10.101.201.204:8080
      - HTTPS_PROXY=http://10.101.201.204:8080
    depends_on:
      rabbitmq:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./uploaded_files:/app/uploaded_files
      - ./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    extra_hosts:
      - "srv-asreports:10.101.2.87"
      - "srv-commercial:10.101.3.243"
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  # API Instance 2
  api_2:
    image: samaconso_api:production
    container_name: samaconso_api_2
    hostname: api_2
    ports:
      - "8002:8000"
    env_file:
      - .env.production
    environment:
      - INSTANCE_ID=api_2
      - REDIS_URL=redis://10.101.X.X3:6379/0
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@rabbitmq:5672/
      - CELERY_BROKER_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@rabbitmq:5672/
      - CELERY_RESULT_BACKEND=redis://10.101.X.X3:6379/0
      - MINIO_ENDPOINT=10.101.X.X1:9000
      - DATABASE_URL=postgresql://samaconso_user:${DB_PASSWORD}@10.101.X.X1:6432/samaconso
      - HTTP_PROXY=http://10.101.201.204:8080
      - HTTPS_PROXY=http://10.101.201.204:8080
    depends_on:
      rabbitmq:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./uploaded_files:/app/uploaded_files
      - ./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    extra_hosts:
      - "srv-asreports:10.101.2.87"
      - "srv-commercial:10.101.3.243"
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

volumes:
  rabbitmq_data:

networks:
  samaconso_network:
    driver: bridge
```

### 2.5 Variables d'Environnement

**Fichier**: `/opt/samaconso/.env.production`

```bash
# Base de données
DATABASE_URL=postgresql://samaconso_user:MOT_DE_PASSE@10.101.X.X1:6432/samaconso
DB_PASSWORD=MOT_DE_PASSE_SECURISE

# Redis
REDIS_URL=redis://10.101.X.X3:6379/0

# RabbitMQ
RABBITMQ_USER=samaconso_admin
RABBITMQ_PASS=MOT_DE_PASSE_SECURISE
CELERY_BROKER_URL=amqp://samaconso_admin:MOT_DE_PASSE@rabbitmq:5672/
CELERY_RESULT_BACKEND=redis://10.101.X.X3:6379/0

# MinIO
MINIO_ENDPOINT=10.101.X.X1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=MOT_DE_PASSE_SECURISE
MINIO_SECURE=false

# Firebase
FIREBASE_CREDENTIALS_PATH=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
GOOGLE_APPLICATION_CREDENTIALS=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# Proxy Senelec
HTTP_PROXY=http://10.101.201.204:8080
HTTPS_PROXY=http://10.101.201.204:8080
NO_PROXY=localhost,127.0.0.1,10.101.X.X1,10.101.X.X2,10.101.X.X3

# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=GENERER_UNE_CLE_SECURISEE_UNIQUE

# Sécurité
ALLOWED_HOSTS=10.101.X.X0,10.101.X.X2,api.samaconso.senelec.sn
CORS_ORIGINS=https://app.samaconso.senelec.sn,https://web.samaconso.senelec.sn
```

**Sécuriser le fichier**:
```bash
chmod 600 /opt/samaconso/.env.production
```

### 2.6 Configuration RabbitMQ

**Fichier**: `/opt/samaconso/rabbitmq.conf`

```
# Networking
listeners.tcp.default = 5672
management.tcp.port = 15672

# Memory
vm_memory_high_watermark.relative = 0.7
vm_memory_high_watermark_paging_ratio = 0.75
total_memory_available_override_value = 2GB

# Disk
disk_free_limit.absolute = 10GB

# Logging
log.file.level = info
log.console = true
log.console.level = info

# Performance
channel_max = 2047
heartbeat = 60
frame_max = 131072

# Queue settings
queue_master_locator = min-masters
```

### 2.7 Démarrage

```bash
cd /opt/samaconso

# Démarrer les services
docker compose -f docker-compose.production.yml up -d

# Vérifier
docker ps
docker compose -f docker-compose.production.yml logs -f
```

---

## ⚙️ SERVEUR 3: Workers Celery & Redis

### 3.1 Installation Docker

```bash
# Même procédure que SERVEUR 2 (section 2.1)
```

### 3.2 Préparation

```bash
sudo mkdir -p /opt/samaconso
sudo chown $USER:$USER /opt/samaconso
cd /opt/samaconso

# Transférer l'image Docker
# scp samaconso_api.tar user@SERVEUR_3:/tmp/
docker load -i /tmp/samaconso_api.tar
docker tag samaconso_api:with-fixes samaconso_api:production
```

### 3.3 Configuration Docker Compose

**Fichier**: `/opt/samaconso/docker-compose.workers.yml`

```yaml
version: '3.8'

services:
  # Redis - Cache et résultats Celery
  redis:
    image: redis:7.4.4-alpine
    container_name: samaconso_redis
    command: >
      redis-server
      --appendonly yes
      --maxmemory 4gb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
      --save 60 10000
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

  # Celery Worker 1 - Queues prioritaires
  celery_worker_1:
    image: samaconso_api:production
    container_name: samaconso_celery_worker_1
    hostname: celery_worker_1
    command: celery -A app.celery_app worker --loglevel=info --pool=prefork -n worker1@%h --concurrency=4 -Q urgent,high_priority
    env_file:
      - .env.production
    environment:
      - WORKER_ID=worker_1
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@10.101.X.X2:5672/
      - CELERY_BROKER_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@10.101.X.X2:5672/
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - DATABASE_URL=postgresql://samaconso_user:${DB_PASSWORD}@10.101.X.X1:6432/samaconso
      - MINIO_ENDPOINT=10.101.X.X1:9000
      - HTTP_PROXY=http://10.101.201.204:8080
      - HTTPS_PROXY=http://10.101.201.204:8080
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:ro
    restart: unless-stopped
    extra_hosts:
      - "srv-asreports:10.101.2.87"
      - "srv-commercial:10.101.3.243"
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  # Celery Worker 2 - Queues normales
  celery_worker_2:
    image: samaconso_api:production
    container_name: samaconso_celery_worker_2
    hostname: celery_worker_2
    command: celery -A app.celery_app worker --loglevel=info --pool=prefork -n worker2@%h --concurrency=4 -Q normal,low_priority
    env_file:
      - .env.production
    environment:
      - WORKER_ID=worker_2
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@10.101.X.X2:5672/
      - CELERY_BROKER_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@10.101.X.X2:5672/
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - DATABASE_URL=postgresql://samaconso_user:${DB_PASSWORD}@10.101.X.X1:6432/samaconso
      - MINIO_ENDPOINT=10.101.X.X1:9000
      - HTTP_PROXY=http://10.101.201.204:8080
      - HTTPS_PROXY=http://10.101.201.204:8080
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json:ro
    restart: unless-stopped
    extra_hosts:
      - "srv-asreports:10.101.2.87"
      - "srv-commercial:10.101.3.243"
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  # Flower - Monitoring Celery
  flower:
    image: samaconso_api:production
    container_name: samaconso_flower
    hostname: flower
    command: celery -A app.celery_app flower --port=5555 --basic_auth=${FLOWER_USER}:${FLOWER_PASS}
    ports:
      - "5555:5555"
    env_file:
      - .env.production
    environment:
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@10.101.X.X2:5672/
      - CELERY_BROKER_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@10.101.X.X2:5672/
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - samaconso_network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

volumes:
  redis_data:

networks:
  samaconso_network:
    driver: bridge
```

### 3.4 Variables d'Environnement

**Fichier**: `/opt/samaconso/.env.production`

```bash
# Même fichier que SERVEUR 2, ajouter:
FLOWER_USER=admin
FLOWER_PASS=MOT_DE_PASSE_SECURISE
```

### 3.5 Démarrage

```bash
cd /opt/samaconso

# Démarrer les services
docker compose -f docker-compose.workers.yml up -d

# Vérifier
docker ps
docker compose -f docker-compose.workers.yml logs -f
```

---

## 🔄 Configuration Load Balancer F5

### 4.1 Pool Members

**Pool**: `samaconso_api_pool`

| Member | IP | Port | Health Monitor |
|--------|-----|----|----------------|
| api_1 | 10.101.X.X2 | 8001 | HTTP GET /health |
| api_2 | 10.101.X.X2 | 8002 | HTTP GET /health |

### 4.2 Virtual Server

```
Name: samaconso_api_vip
IP: 10.101.X.X0
Port: 80 (HTTP) et 443 (HTTPS)
Protocol: TCP
Pool: samaconso_api_pool
```

### 4.3 Load Balancing Method

**Recommandé**: `Least Connections`

Alternative: `Round Robin`

### 4.4 Health Monitor

```
Type: HTTP
Interval: 10 seconds
Timeout: 5 seconds
Send String: GET /health HTTP/1.1\r\nHost: api.samaconso.senelec.sn\r\n\r\n
Receive String: "status":"running"
```

### 4.5 Persistence

**Session Persistence**: Cookie Insert
**Cookie Name**: `SAMACONSOSERVERID`
**Timeout**: 1800 seconds (30 minutes)

### 4.6 SSL/TLS (Si HTTPS)

```
Certificate: Certificat Senelec
Client SSL Profile: clientssl
Server SSL Profile: serverssl-insecure-compatible (pour backend)
```

### 4.7 Configuration Exemple F5 (tmsh)

```bash
# Créer le pool
create ltm pool samaconso_api_pool {
    members {
        10.101.X.X2:8001 { address 10.101.X.X2 }
        10.101.X.X2:8002 { address 10.101.X.X2 }
    }
    monitor http_health_samaconso
    load-balancing-mode least-connections-member
}

# Créer le health monitor
create ltm monitor http http_health_samaconso {
    defaults-from http
    interval 10
    timeout 30
    send "GET /health HTTP/1.1\r\nHost: api.samaconso.senelec.sn\r\n\r\n"
    recv "running"
}

# Créer le virtual server
create ltm virtual samaconso_api_vip {
    destination 10.101.X.X0:80
    pool samaconso_api_pool
    profiles {
        http { }
        tcp { }
    }
    persist {
        cookie { default yes }
    }
    source-address-translation {
        type automap
    }
}
```

---

**(La suite dans le prochain message - document trop long)**

Voulez-vous que je continue avec les sections Sécurité, Monitoring, Procédures de Déploiement, etc.?