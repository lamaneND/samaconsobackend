# Guide de Déploiement Rapide - Option 3

## Résumé des Étapes

### SRV-MOBAPPBD (10.101.1.212)
1. `git clone <REPO>` dans `/tmp`
2. `sudo bash deployment/architecture-option3/SRV-MOBAPPBD/install-postgres-primary.sh`
3. `sudo bash deployment/architecture-option3/shared/install-minio-distributed.sh SRV-MOBAPPBD 10.101.1.212 1`

### SRV-MOBAPP1 (10.101.1.210)
1. `git clone <REPO>` dans `/tmp` et `/opt/samaconso`
2. `sudo bash deployment/architecture-option3/SRV-MOBAPP1/install-postgres-standby.sh`
3. `sudo bash deployment/architecture-option3/shared/install-minio-distributed.sh SRV-MOBAPP1 10.101.1.210 2`
4. Configurer Docker Compose (voir GUIDE_DEPLOIEMENT_OPTION3.md)
5. `docker-compose up -d`
6. `sudo bash deployment/scripts/setup-nginx-lb.sh`

### SRV-MOBAPP2 (10.101.1.211)
1. `git clone <REPO>` dans `/tmp` et `/opt/samaconso`
2. `sudo bash deployment/architecture-option3/shared/install-minio-distributed.sh SRV-MOBAPP2 10.101.1.211 3`
3. Configurer Docker Compose (voir GUIDE_DEPLOIEMENT_OPTION3.md)
4. `docker-compose up -d`
5. `sudo bash deployment/architecture-option3/shared/setup-rabbitmq-cluster.sh`

### Initialisation
- `docker-compose exec api alembic upgrade head` (sur SRV-MOBAPP1 ou SRV-MOBAPP2)

## Fichiers Créés

✅ Tous les fichiers de configuration sont dans `deployment/architecture-option3/`

Consultez `GUIDE_DEPLOIEMENT_OPTION3.md` pour les instructions détaillées.

