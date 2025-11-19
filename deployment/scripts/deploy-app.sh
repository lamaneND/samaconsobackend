#!/bin/bash
# Script de déploiement pour SRV-MOBAPP1 et SRV-MOBAPP2
# Déploie l'application FastAPI

set -e

# Paramètres
SERVER_NAME=${1:-SRV-MOBAPP1}
SERVER_IP=${2:-10.101.1.210}
DB_SERVER_IP=${3:-10.101.1.57}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="/opt/samaconso"

echo "=========================================="
echo "Déploiement sur $SERVER_NAME ($SERVER_IP)"
echo "=========================================="

# Vérifier si on est root
if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter ce script en tant que root (sudo)"
    exit 1
fi

# Créer le répertoire de déploiement
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# Copier les fichiers de l'application
echo "Copie des fichiers de l'application..."
if [ -d "$PROJECT_DIR/app" ]; then
    rsync -av --exclude='__pycache__' --exclude='*.pyc' \
        "$PROJECT_DIR/app/" ./app/
fi

# Copier les fichiers de configuration
echo "Copie des fichiers de configuration..."
cp "$PROJECT_DIR/deployment/docker-compose.app.yml" ./docker-compose.yml
cp "$PROJECT_DIR/Dockerfile" ./Dockerfile 2>/dev/null || true
cp "$PROJECT_DIR/requirements.txt" ./requirements.txt 2>/dev/null || true

# Créer les répertoires nécessaires
mkdir -p uploaded_files logs

# Créer le fichier .env.production si il n'existe pas
if [ ! -f .env.production ]; then
    echo "Création du fichier .env.production..."
    cat > .env.production << EOF
# Configuration serveur
SERVER_NAME=$SERVER_NAME
SERVER_IP=$SERVER_IP

# Base de données (sur SRV-MOBAPPBD)
DATABASE_URL=postgresql://postgres:s3n3l3c123@$DB_SERVER_IP:5432/samaconso

# Redis (sur SRV-MOBAPPBD)
REDIS_URL=redis://$DB_SERVER_IP:6379/0

# RabbitMQ (sur SRV-MOBAPPBD)
RABBITMQ_URL=amqp://admin:Senelec2024!@$DB_SERVER_IP:5672/
CELERY_BROKER_URL=amqp://admin:Senelec2024!@$DB_SERVER_IP:5672/
CELERY_RESULT_BACKEND=redis://$DB_SERVER_IP:6379/0

# MinIO (sur SRV-MOBAPPBD)
MINIO_ENDPOINT=$DB_SERVER_IP:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=Senelec2024!
MINIO_SECURE=false

# Firebase
FIREBASE_CREDENTIALS_PATH=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
GOOGLE_APPLICATION_CREDENTIALS=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# Flower (monitoring)
FLOWER_USER=admin
FLOWER_PASS=Senelec2024!

# JWT
SECRET_KEY=\$3?N2LEC123
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
EOF
    chmod 600 .env.production
    echo "Fichier .env.production créé. Veuillez le modifier avec les valeurs appropriées."
fi

# Construire l'image Docker
echo "Construction de l'image Docker..."
if [ -f Dockerfile ]; then
    docker build -t samaconso_api:with-fixes .
    docker tag samaconso_api:with-fixes samaconso_celery_worker:with-fixes
else
    echo "ATTENTION: Dockerfile non trouvé. Assurez-vous de l'avoir copié."
    exit 1
fi

# Arrêter les conteneurs existants
echo "Arrêt des conteneurs existants..."
docker-compose down 2>/dev/null || true

# Démarrer les services
echo "Démarrage des services..."
if [ "$SERVER_NAME" = "SRV-MOBAPP1" ]; then
    # Démarrer avec Flower (monitoring)
    docker-compose --profile monitoring up -d
else
    # Démarrer sans Flower
    docker-compose up -d
fi

# Attendre que les services soient prêts
echo "Attente du démarrage des services..."
sleep 15

# Vérifier l'état des services
echo "Vérification de l'état des services..."
docker-compose ps

# Vérifier la santé de l'API
echo "Vérification de la santé de l'API..."
sleep 5
curl -f http://localhost:8000/health || echo "L'API n'est pas encore prête"

echo "=========================================="
echo "Déploiement terminé!"
echo "=========================================="
echo "Logs: docker-compose logs -f"
echo "Statut: docker-compose ps"
echo "=========================================="

