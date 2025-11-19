# Changement d'IP - Base de Données

## Modification effectuée

L'adresse IP du serveur de base de données a été changée de **10.101.1.57** à **10.101.1.212**.

## Fichiers mis à jour

### Configuration PostgreSQL
- ✅ `SRV-MOBAPPBD/install-postgres-primary.sh` - Commentaires et messages
- ✅ `SRV-MOBAPP1/install-postgres-standby.sh` - Connexion au Primary

### Configuration Docker Compose
- ✅ `SRV-MOBAPP1/docker-compose.app-redis.yml` - DATABASE_URL et MINIO_ENDPOINT
- ✅ `SRV-MOBAPP2/docker-compose.app-rabbitmq.yml` - DATABASE_URL et MINIO_ENDPOINT

### Configuration MinIO
- ✅ `shared/install-minio-distributed.sh` - MINIO_VOLUMES avec la nouvelle IP

### Documentation
- ✅ `GUIDE_DEPLOIEMENT_OPTION3.md` - Toutes les références à l'IP
- ✅ `QUICK_START.md` - Références à l'IP

## Nouvelle architecture

### SRV-MOBAPPBD (10.101.1.212) ← **NOUVELLE IP**
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

## Points d'attention

1. **PgBouncer** : Accessible sur `10.101.1.212:6432`
2. **PostgreSQL** : Accessible via PgBouncer sur `10.101.1.212:6432`
3. **MinIO Node 1** : Accessible sur `10.101.1.212:9000` (API) et `10.101.1.212:9001` (Console)
4. **Réplication PostgreSQL** : Le Standby sur SRV-MOBAPP1 se connecte au Primary sur `10.101.1.212:5432`

## Vérification

Après le déploiement, vérifier la connectivité :

```bash
# Depuis SRV-MOBAPP1 ou SRV-MOBAPP2
telnet 10.101.1.212 6432  # PgBouncer
telnet 10.101.1.212 9000  # MinIO API
```

