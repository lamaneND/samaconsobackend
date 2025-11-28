# Guide de Déploiement - SamaConso API

Ce guide décrit le déploiement de l'application SamaConso sur 3 serveurs Ubuntu avec configuration de scalabilité.

## Architecture de Déploiement

### Serveurs

1. **SRV-MOBAPPBD** (10.101.1.57)
   - PostgreSQL (base de données principale)
   - Redis (cache)
   - RabbitMQ (message broker pour Celery)
   - MinIO (stockage de fichiers)
   - Partition données: 500 Go

2. **SRV-MOBAPP1** (10.101.1.210)
   - API FastAPI
   - Celery Worker
   - Flower (monitoring Celery)
   - Nginx (load balancer)
   - Partition données: 300 Go

3. **SRV-MOBAPP2** (10.101.1.211)
   - API FastAPI
   - Celery Worker
   - Partition données: 300 Go

## Prérequis

- Ubuntu Server 22.04 LTS sur les 3 serveurs
- Accès root/sudo sur tous les serveurs
- Accès réseau entre les serveurs (ports 5432, 6379, 5672, 8000)
- Fichier Firebase credentials: `app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json`

## Étapes de Déploiement

### Étape 1: Préparation des Serveurs

#### Sur SRV-MOBAPPBD (10.101.1.57)

```bash
# 1. Se connecter au serveur
ssh user@10.101.1.57

# 2. Monter la partition données (si nécessaire)
# Vérifier les partitions disponibles
lsblk

# Monter la partition données (exemple: /dev/sdb1)
sudo mkdir -p /data
sudo mount /dev/sdb1 /data
echo "/dev/sdb1 /data ext4 defaults 0 2" | sudo tee -a /etc/fstab

# 3. Exécuter le script d'installation
cd /tmp
# Copier le script setup-db-server.sh depuis votre machine locale
sudo bash setup-db-server.sh
```

#### Sur SRV-MOBAPP1 (10.101.1.210)

```bash
# 1. Se connecter au serveur
ssh user@10.101.1.210

# 2. Exécuter le script d'installation
cd /tmp
sudo bash setup-app-server.sh SRV-MOBAPP1 10.101.1.210 10.101.1.57
```

#### Sur SRV-MOBAPP2 (10.101.1.211)

```bash
# 1. Se connecter au serveur
ssh user@10.101.1.211

# 2. Exécuter le script d'installation
cd /tmp
sudo bash setup-app-server.sh SRV-MOBAPP2 10.101.1.211 10.101.1.57
```

### Étape 2: Transfert des Fichiers

Depuis votre machine locale, transférer les fichiers vers les serveurs:

```bash
# Créer une archive du projet
tar -czf samaconso-deployment.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    .

# Transférer vers SRV-MOBAPPBD
scp samaconso-deployment.tar.gz user@10.101.1.57:/tmp/
scp -r deployment/ user@10.101.1.57:/tmp/

# Transférer vers SRV-MOBAPP1
scp samaconso-deployment.tar.gz user@10.101.1.210:/tmp/
scp -r deployment/ user@10.101.1.210:/tmp/

# Transférer vers SRV-MOBAPP2
scp samaconso-deployment.tar.gz user@10.101.1.211:/tmp/
scp -r deployment/ user@10.101.1.211:/tmp/
```

### Étape 3: Déploiement sur SRV-MOBAPPBD

```bash
# Se connecter au serveur
ssh user@10.101.1.57

# Extraire les fichiers
cd /tmp
tar -xzf samaconso-deployment.tar.gz

# Exécuter le script de déploiement
cd deployment/scripts
sudo bash deploy-db.sh
```

**Vérification:**
```bash
# Vérifier les conteneurs
docker ps

# Vérifier les logs
docker-compose -f /opt/samaconso/docker-compose.yml logs

# Tester la connexion PostgreSQL
docker exec -it samaconso_postgres psql -U postgres -d samaconso -c "SELECT version();"

# Tester Redis
docker exec -it samaconso_redis redis-cli ping

# Tester RabbitMQ (accès management UI)
# Ouvrir http://10.101.1.57:15672 (admin/Senelec2024!)

# Tester MinIO (accès console)
# Ouvrir http://10.101.1.57:9001 (minioadmin/Senelec2024!)
```

### Étape 4: Déploiement sur SRV-MOBAPP1

```bash
# Se connecter au serveur
ssh user@10.101.1.210

# Extraire les fichiers
cd /tmp
tar -xzf samaconso-deployment.tar.gz

# Exécuter le script de déploiement
cd deployment/scripts
sudo bash deploy-app.sh SRV-MOBAPP1 10.101.1.210 10.101.1.57

# Configurer Nginx pour le load balancing
sudo bash setup-nginx-lb.sh
```

**Vérification:**
```bash
# Vérifier les conteneurs
docker ps

# Tester l'API
curl http://localhost:8000/health

# Tester via Nginx
curl http://localhost/health

# Vérifier Flower
curl http://localhost:5555
```

### Étape 5: Déploiement sur SRV-MOBAPP2

```bash
# Se connecter au serveur
ssh user@10.101.1.211

# Extraire les fichiers
cd /tmp
tar -xzf samaconso-deployment.tar.gz

# Exécuter le script de déploiement
cd deployment/scripts
sudo bash deploy-app.sh SRV-MOBAPP2 10.101.1.211 10.101.1.57
```

**Vérification:**
```bash
# Vérifier les conteneurs
docker ps

# Tester l'API
curl http://localhost:8000/health
```

### Étape 6: Initialisation de la Base de Données

```bash
# Se connecter à SRV-MOBAPPBD
ssh user@10.101.1.57

# Exécuter les migrations Alembic (depuis un serveur app)
# Sur SRV-MOBAPP1 ou SRV-MOBAPP2
ssh user@10.101.1.210
cd /opt/samaconso
docker-compose exec api alembic upgrade head
```

## Configuration de la Scalabilité

### Load Balancing

Le load balancing est configuré via Nginx sur SRV-MOBAPP1. La configuration utilise:
- **Méthode**: `least_conn` (répartition par nombre de connexions actives)
- **Health checks**: Détection automatique des serveurs indisponibles
- **Rate limiting**: 100 requêtes/seconde par IP

### Ajout d'un Nouveau Serveur d'Application

Pour ajouter un troisième serveur d'application:

1. Suivre les étapes 1 et 2 pour le nouveau serveur
2. Exécuter `deploy-app.sh` avec les paramètres appropriés
3. Ajouter le serveur dans `/etc/nginx/sites-available/samaconso`:
   ```nginx
   server 10.101.1.XXX:8000 max_fails=3 fail_timeout=30s weight=1;
   ```
4. Recharger Nginx: `sudo systemctl reload nginx`

### Scaling Horizontal des Workers Celery

Pour augmenter le nombre de workers Celery:

1. Modifier `docker-compose.app.yml` sur chaque serveur app
2. Augmenter `--concurrency` dans la commande Celery
3. Ou créer plusieurs instances de workers:
   ```yaml
   celery_worker_1:
     # ... configuration
   celery_worker_2:
     # ... configuration
   ```

### Monitoring et Observabilité

#### Flower (Monitoring Celery)
- URL: http://10.101.1.210:5555
- Accès: Réseau interne uniquement (10.101.0.0/16)
- Credentials: admin/Senelec2024!

#### Logs
```bash
# Logs de l'API
docker-compose logs -f api

# Logs des workers
docker-compose logs -f celery_worker

# Logs Nginx
tail -f /var/log/nginx/samaconso_access.log
tail -f /var/log/nginx/samaconso_error.log
```

#### Métriques Docker
```bash
# Utilisation des ressources
docker stats

# État des conteneurs
docker-compose ps
```

## Maintenance

### Mise à Jour de l'Application

```bash
# Sur chaque serveur app (SRV-MOBAPP1 et SRV-MOBAPP2)
cd /opt/samaconso

# 1. Arrêter les services
docker-compose down

# 2. Mettre à jour le code
# (copier les nouveaux fichiers)

# 3. Reconstruire l'image
docker build -t samaconso_api:with-fixes .

# 4. Redémarrer les services
docker-compose up -d
```

### Sauvegarde de la Base de Données

```bash
# Sur SRV-MOBAPPBD
docker exec samaconso_postgres pg_dump -U postgres samaconso > backup_$(date +%Y%m%d_%H%M%S).sql

# Restauration
docker exec -i samaconso_postgres psql -U postgres samaconso < backup_YYYYMMDD_HHMMSS.sql
```

### Redémarrage des Services

```bash
# Redémarrer tous les services
docker-compose restart

# Redémarrer un service spécifique
docker-compose restart api
docker-compose restart celery_worker
```

## Dépannage

### Problèmes de Connexion

1. **Vérifier le firewall:**
   ```bash
   sudo ufw status
   ```

2. **Vérifier la connectivité réseau:**
   ```bash
   # Depuis un serveur app vers le serveur DB
   telnet 10.101.1.57 5432
   telnet 10.101.1.57 6379
   telnet 10.101.1.57 5672
   ```

3. **Vérifier les logs:**
   ```bash
   docker-compose logs api
   docker-compose logs celery_worker
   ```

### Problèmes de Performance

1. **Vérifier l'utilisation des ressources:**
   ```bash
   htop
   docker stats
   ```

2. **Vérifier les connexions à la base de données:**
   ```bash
   docker exec samaconso_postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
   ```

3. **Optimiser Redis:**
   ```bash
   docker exec samaconso_redis redis-cli INFO memory
   ```

## Sécurité

### Recommandations

1. **Changer tous les mots de passe par défaut** dans les fichiers `.env`
2. **Configurer SSL/TLS** pour Nginx (certificat Let's Encrypt)
3. **Restreindre l'accès** aux ports de management (15672, 9001, 5555)
4. **Configurer un firewall** strict (UFW)
5. **Mettre à jour régulièrement** le système et les images Docker

### Configuration SSL (Optionnel)

```bash
# Installer Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtenir un certificat
sudo certbot --nginx -d votre-domaine.com

# Le certificat sera renouvelé automatiquement
```

## Support

Pour toute question ou problème, consulter:
- Les logs Docker: `docker-compose logs`
- Les logs système: `journalctl -u docker`
- La documentation de l'application

