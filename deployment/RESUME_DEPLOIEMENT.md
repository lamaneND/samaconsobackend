# Résumé du Déploiement SamaConso

## Vue d'Ensemble

Ce package de déploiement permet de déployer l'application SamaConso sur 3 serveurs Ubuntu avec une architecture scalable.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              SRV-MOBAPPBD (10.101.1.57)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │PostgreSQL│  │  Redis   │  │ RabbitMQ │  │  MinIO   ││
│  │  :5432   │  │  :6379   │  │  :5672   │  │  :9000   ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
└─────────────────────────────────────────────────────────┘
                        ▲
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────┴────────┐            ┌────────┴────────┐
│ SRV-MOBAPP1    │            │ SRV-MOBAPP2     │
│ (10.101.1.210) │            │ (10.101.1.211) │
│                │            │                 │
│ ┌────────────┐ │            │ ┌────────────┐ │
│ │ FastAPI    │ │            │ │ FastAPI    │ │
│ │   :8000    │ │            │ │   :8000    │ │
│ └────────────┘ │            │ └────────────┘ │
│ ┌────────────┐ │            │ ┌────────────┐ │
│ │ Celery     │ │            │ │ Celery     │ │
│ │  Worker    │ │            │ │  Worker    │ │
│ └────────────┘ │            │ └────────────┘ │
│ ┌────────────┐ │            │                 │
│ │ Flower     │ │            │                 │
│ │   :5555    │ │            │                 │
│ └────────────┘ │            │                 │
│ ┌────────────┐ │            │                 │
│ │  Nginx     │ │            │                 │
│ │   :80      │ │            │                 │
│ │ (Load Bal) │ │            │                 │
│ └────────────┘ │            │                 │
└─────────────────┘            └─────────────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                ┌───────▼───────┐
                │   Clients     │
                │  (Mobile App) │
                └───────────────┘
```

## Fichiers Créés

### Configuration Docker
- `docker-compose.db.yml` - Services de base de données (PostgreSQL, Redis, RabbitMQ, MinIO)
- `docker-compose.app.yml` - Services d'application (API, Celery, Flower)

### Configuration Nginx
- `nginx/nginx.conf` - Configuration du load balancer avec health checks

### Scripts d'Installation
- `scripts/setup-db-server.sh` - Installation sur SRV-MOBAPPBD
- `scripts/setup-app-server.sh` - Installation sur SRV-MOBAPP1 et SRV-MOBAPP2
- `scripts/deploy-db.sh` - Déploiement sur SRV-MOBAPPBD
- `scripts/deploy-app.sh` - Déploiement sur les serveurs app
- `scripts/setup-nginx-lb.sh` - Configuration Nginx
- `scripts/health-check.sh` - Vérification de santé
- `scripts/backup-db.sh` - Sauvegarde de la base de données
- `scripts/quick-start.sh` - Guide rapide

### Templates de Configuration
- `env.db.template` - Variables d'environnement pour le serveur DB
- `env.app.template` - Variables d'environnement pour les serveurs app

### Documentation
- `GUIDE_DEPLOIEMENT.md` - Guide complet et détaillé
- `README.md` - Vue d'ensemble et démarrage rapide
- `RESUME_DEPLOIEMENT.md` - Ce fichier

## Modifications Apportées

### Application
- Ajout de l'endpoint `/health` dans `app/main.py` pour les health checks

## Ordre de Déploiement

1. **SRV-MOBAPPBD** - Installer et déployer les services de base de données
2. **SRV-MOBAPP1** - Installer, déployer l'application et configurer Nginx
3. **SRV-MOBAPP2** - Installer et déployer l'application
4. **Initialisation** - Exécuter les migrations Alembic
5. **Vérification** - Tester tous les services

## Points Importants

### Sécurité
- ⚠️ **Changer tous les mots de passe par défaut** dans les fichiers `.env`
- ⚠️ Configurer le firewall (UFW) sur tous les serveurs
- ⚠️ Restreindre l'accès aux ports de management (15672, 9001, 5555)

### Réseau
- Vérifier que les ports suivants sont ouverts entre les serveurs:
  - 5432 (PostgreSQL)
  - 6379 (Redis)
  - 5672 (RabbitMQ)
  - 8000 (API FastAPI)

### Stockage
- Configurer les partitions de données avant le déploiement:
  - SRV-MOBAPPBD: `/data` (500 Go)
  - SRV-MOBAPP1: `/opt/samaconso` (300 Go)
  - SRV-MOBAPP2: `/opt/samaconso` (300 Go)

### Fichiers Requis
- `app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json` - Credentials Firebase

## Commandes Utiles

### Vérification des Services
```bash
# Vérifier les conteneurs
docker ps

# Vérifier les logs
docker-compose logs -f

# Vérifier la santé
bash deployment/scripts/health-check.sh
```

### Maintenance
```bash
# Redémarrer les services
docker-compose restart

# Mettre à jour l'application
docker-compose down
docker build -t samaconso_api:with-fixes .
docker-compose up -d

# Sauvegarder la base de données
bash deployment/scripts/backup-db.sh
```

### Monitoring
- **Flower**: http://10.101.1.210:5555 (admin/Senelec2024!)
- **RabbitMQ Management**: http://10.101.1.57:15672 (admin/Senelec2024!)
- **MinIO Console**: http://10.101.1.57:9001 (minioadmin/Senelec2024!)

## Scalabilité

### Ajouter un Serveur d'Application
1. Suivre les étapes d'installation et déploiement
2. Ajouter le serveur dans la configuration Nginx
3. Recharger Nginx: `sudo systemctl reload nginx`

### Scaling des Workers Celery
- Modifier `--concurrency` dans `docker-compose.app.yml`
- Ou créer plusieurs instances de workers

## Support

Pour plus de détails, consulter:
- `GUIDE_DEPLOIEMENT.md` - Guide complet
- `README.md` - Vue d'ensemble
- Logs Docker: `docker-compose logs -f`

