#!/bin/bash
# Script de déploiement pour SRV-MOBAPPBD
# Déploie les services de base de données

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="/opt/samaconso"

echo "=========================================="
echo "Déploiement sur SRV-MOBAPPBD"
echo "=========================================="

# Vérifier si on est root
if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter ce script en tant que root (sudo)"
    exit 1
fi

# Créer le répertoire de déploiement
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# Copier les fichiers de configuration
echo "Copie des fichiers de configuration..."
cp "$PROJECT_DIR/deployment/docker-compose.db.yml" ./docker-compose.yml

# Créer le fichier .env si il n'existe pas
if [ ! -f .env ]; then
    echo "Création du fichier .env..."
    cat > .env << EOF
# Configuration PostgreSQL
POSTGRES_DB=samaconso
POSTGRES_USER=postgres
POSTGRES_PASSWORD=s3n3l3c123

# Configuration RabbitMQ
RABBITMQ_USER=admin
RABBITMQ_PASS=Senelec2024!

# Configuration MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=Senelec2024!
EOF
    chmod 600 .env
    echo "Fichier .env créé. Veuillez le modifier avec les mots de passe appropriés."
fi

# Créer les répertoires de données
echo "Création des répertoires de données..."
mkdir -p /data/{postgres,redis,rabbitmq,minio}
chmod 700 /data/{postgres,redis,rabbitmq,minio}

# Arrêter les conteneurs existants
echo "Arrêt des conteneurs existants..."
docker-compose down 2>/dev/null || true

# Démarrer les services
echo "Démarrage des services..."
docker-compose up -d

# Attendre que les services soient prêts
echo "Attente du démarrage des services..."
sleep 10

# Vérifier l'état des services
echo "Vérification de l'état des services..."
docker-compose ps

# Afficher les logs
echo "=========================================="
echo "Logs des services (Ctrl+C pour quitter):"
echo "=========================================="
docker-compose logs -f

