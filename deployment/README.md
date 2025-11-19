# Déploiement SamaConso API

Ce répertoire contient tous les fichiers nécessaires pour déployer l'application SamaConso sur 3 serveurs Ubuntu avec configuration de scalabilité.

## Structure des Fichiers

```
deployment/
├── docker-compose.db.yml          # Configuration Docker pour le serveur de base de données
├── docker-compose.app.yml          # Configuration Docker pour les serveurs d'application
├── nginx/
│   └── nginx.conf                  # Configuration Nginx pour le load balancing
├── scripts/
│   ├── setup-db-server.sh          # Installation sur SRV-MOBAPPBD
│   ├── setup-app-server.sh         # Installation sur SRV-MOBAPP1 et SRV-MOBAPP2
│   ├── deploy-db.sh                # Déploiement sur SRV-MOBAPPBD
│   ├── deploy-app.sh               # Déploiement sur les serveurs app
│   ├── setup-nginx-lb.sh           # Configuration Nginx load balancer
│   ├── health-check.sh             # Vérification de santé des services
│   └── backup-db.sh                # Script de sauvegarde de la base de données
├── env.db.template                 # Template variables d'environnement (DB)
├── env.app.template                # Template variables d'environnement (App)
├── GUIDE_DEPLOIEMENT.md            # Guide complet de déploiement
└── README.md                       # Ce fichier
```

## Architecture

### Serveur de Base de Données (SRV-MOBAPPBD)
- **IP**: 10.101.1.57
- **Services**: PostgreSQL, Redis, RabbitMQ, MinIO
- **Stockage**: 500 Go (partition données)

### Serveurs d'Application
- **SRV-MOBAPP1** (10.101.1.210): API + Celery Worker + Flower + Nginx LB
- **SRV-MOBAPP2** (10.101.1.211): API + Celery Worker
- **Stockage**: 300 Go chacun (partition données)

## Démarrage Rapide

### 1. Préparation

Sur chaque serveur, rendre les scripts exécutables:
```bash
chmod +x deployment/scripts/*.sh
```

### 2. Installation des Serveurs

```bash
# Sur SRV-MOBAPPBD
sudo bash deployment/scripts/setup-db-server.sh

# Sur SRV-MOBAPP1
sudo bash deployment/scripts/setup-app-server.sh SRV-MOBAPP1 10.101.1.210 10.101.1.57

# Sur SRV-MOBAPP2
sudo bash deployment/scripts/setup-app-server.sh SRV-MOBAPP2 10.101.1.211 10.101.1.57
```

### 3. Déploiement

```bash
# Sur SRV-MOBAPPBD
sudo bash deployment/scripts/deploy-db.sh

# Sur SRV-MOBAPP1
sudo bash deployment/scripts/deploy-app.sh SRV-MOBAPP1 10.101.1.210 10.101.1.57
sudo bash deployment/scripts/setup-nginx-lb.sh

# Sur SRV-MOBAPP2
sudo bash deployment/scripts/deploy-app.sh SRV-MOBAPP2 10.101.1.211 10.101.1.57
```

### 4. Vérification

```bash
# Vérifier la santé de tous les services
bash deployment/scripts/health-check.sh
```

## Documentation Complète

Consulter [GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md) pour:
- Instructions détaillées étape par étape
- Configuration de la scalabilité
- Procédures de maintenance
- Dépannage
- Recommandations de sécurité

## Notes Importantes

1. **Mots de passe**: Modifier tous les mots de passe par défaut dans les fichiers `.env`
2. **Firebase**: S'assurer que le fichier `samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json` est présent
3. **Réseau**: Vérifier que tous les ports nécessaires sont ouverts entre les serveurs
4. **Partitions**: Configurer les partitions de données avant le déploiement

## Support

Pour toute question, consulter le guide de déploiement ou les logs Docker:
```bash
docker-compose logs -f
```

