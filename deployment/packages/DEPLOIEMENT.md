# Guide de déploiement SamaConso — Procédure complète

Déploiement sur 2 serveurs applicatifs : **SRV-MOBAPP1** (10.101.1.210) puis **SRV-MOBAPP2** (10.101.1.211).

---

## DEPUIS TON POSTE (Windows)

### 1. Ouvrir un invite de commande dans le dossier packages

```cmd
cd D:\Senelec\samaconso\samaconsoapi-dev_pcyn_new\deployment\packages
```

### 2. Récupérer ton adresse IP sur le réseau Senelec

```cmd
ipconfig | findstr "IPv4"
```

Prendre l'adresse en `10.101.x.x`.
**Note cette IP**, tu en auras besoin à l'étape suivante.

### 3. Lancer un serveur HTTP temporaire

```cmd
python -m http.server 8888
```

Laisser cette fenêtre ouverte pendant toute la procédure.

---

## SRV-MOBAPP1 — 10.101.1.210 (nouvelle fenêtre)

> Déployer SRV1 en premier — SRV2 dépend de son Redis Master.

### 4. Se connecter au serveur

```bash
ssh admin.pcyn@10.101.1.210
```

### 5. Télécharger les fichiers (remplacer `<TON_IP>` par l'IP notée à l'étape 2)

```bash
cd /tmp
wget http://<TON_IP>:8888/samaconso_api.tar
wget http://<TON_IP>:8888/redis_7_alpine.tar
wget http://<TON_IP>:8888/docker-compose.srv1.yml
```

### 6. Charger les nouvelles images Docker

```bash
docker load < /tmp/samaconso_api.tar
docker load < /tmp/redis_7_alpine.tar
```

Résultat attendu :
```
Loaded image: samaconso_api:latest
Loaded image: redis:7-alpine
```

### 7. Préparer le dossier de déploiement (1ère fois uniquement)

```bash
sudo mkdir -p /opt/samaconso
sudo chown -R samaconso:samaconso-admins /opt/samaconso
cd /opt/samaconso

# Créer les dossiers nécessaires
mkdir -p logs uploaded_files app

# Copier le docker-compose
cp /tmp/docker-compose.srv1.yml docker-compose.yml

# Déposer le fichier .env.production (à faire manuellement si pas déjà présent)
# nano .env.production

# Déposer le fichier Firebase credentials
# cp /chemin/vers/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json app/
```

> **Pré-requis :** `.env.production` et le fichier Firebase doivent être présents dans `/opt/samaconso/` avant de continuer.

### 8. Arrêter les anciens conteneurs (si déjà déployé)

```bash
cd /opt/samaconso
docker stop samaconso_api samaconso_worker_high samaconso_redis
docker rm samaconso_api samaconso_worker_high samaconso_redis
```

### 9. Lancer les conteneurs

```bash
cd /opt/samaconso
docker-compose up -d
```

Résultat attendu — 3 conteneurs en cours d'exécution :
```
samaconso_redis        (healthy)
samaconso_api          (healthy)
samaconso_worker_high
```

Vérification :
```bash
docker ps
docker-compose logs -f api   # Ctrl+C pour quitter
```

### 10. Appliquer les migrations Alembic

```bash
docker exec samaconso_api alembic upgrade head
```

### 11. Vérifier la santé de l'API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/redis
```

---

## SRV-MOBAPP2 — 10.101.1.211 (nouvelle fenêtre)

> À faire **après** SRV1 (le Redis replica a besoin que le Master soit actif).

### 12. Se connecter au serveur

```bash
ssh admin.pcyn@10.101.1.211
```

### 13. Télécharger les fichiers (même `<TON_IP>` qu'à l'étape 2)

```bash
cd /tmp
wget http://<TON_IP>:8888/samaconso_api.tar
wget http://<TON_IP>:8888/redis_7_alpine.tar
wget http://<TON_IP>:8888/docker-compose.srv2.yml
```

### 14. Charger les nouvelles images Docker

```bash
docker load < /tmp/samaconso_api.tar
docker load < /tmp/redis_7_alpine.tar
```

### 15. Préparer le dossier de déploiement (1ère fois uniquement)

```bash
sudo mkdir -p /opt/samaconso
sudo chown -R samaconso:samaconso-admins /opt/samaconso
cd /opt/samaconso

mkdir -p logs uploaded_files app
cp /tmp/docker-compose.srv2.yml docker-compose.yml

# Déposer .env.production et Firebase credentials (même que SRV1)
```

### 16. Arrêter les anciens conteneurs (si déjà déployé)

```bash
cd /opt/samaconso
docker stop samaconso_api samaconso_worker_low samaconso_redis_replica
docker rm samaconso_api samaconso_worker_low samaconso_redis_replica
```

### 17. Lancer les conteneurs

```bash
cd /opt/samaconso
docker-compose up -d
```

Résultat attendu — 3 conteneurs en cours d'exécution :
```
samaconso_redis_replica   (healthy)
samaconso_api             (healthy)
samaconso_worker_low
```

### 18. Vérifier la réplication Redis

```bash
docker exec samaconso_redis_replica redis-cli info replication | grep role
# Résultat attendu : role:slave
```

---

## FIN — Couper le serveur HTTP

Sur ton poste Windows, dans la fenêtre du serveur HTTP :

```
Ctrl+C
```

---

## Vérifications finales

```bash
# API accessible via le VIP Keepalived
curl http://10.101.1.250/health

# Queues Celery actives (depuis SRV1)
docker exec samaconso_worker_high celery -A app.celery_app inspect active_queues

# Queues Celery actives (depuis SRV2)
docker exec samaconso_worker_low celery -A app.celery_app inspect active_queues

# Console Flower (optionnel)
# http://10.101.1.210:5555
```

---

## Contenu du dossier packages/

| Fichier | Description |
|---------|-------------|
| `samaconso_api.tar` | Image Docker de l'API (à transférer) |
| `redis_7_alpine.tar` | Image Docker Redis 7-alpine (à transférer) |
| `docker-compose.srv1.yml` | Config Docker Compose pour SRV-MOBAPP1 |
| `docker-compose.srv2.yml` | Config Docker Compose pour SRV-MOBAPP2 |
| `DEPLOIEMENT.md` | Ce guide |
