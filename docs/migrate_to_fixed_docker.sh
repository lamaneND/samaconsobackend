#!/bin/bash

###############################################################################
# Script de Migration vers la Configuration Docker Corrigée
# SamaConso API - Correction des problèmes SQL Server et Firebase
###############################################################################

set -e  # Arrêter en cas d'erreur

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Migration Docker - SamaConso API                         ║"
echo "║   Correction SQL Server + Firebase                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Fonction pour afficher les étapes
step() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

# Fonction pour succès
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Fonction pour avertissement
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Fonction pour erreur
error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "Dockerfile.fixed" ]; then
    error "Fichier Dockerfile.fixed non trouvé. Êtes-vous dans le bon répertoire?"
fi

step "Étape 1: Vérification des prérequis"

# Vérifier Docker
if ! command -v docker &> /dev/null; then
    error "Docker n'est pas installé"
fi
success "Docker installé"

# Vérifier Docker Compose
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose n'est pas installé"
fi
success "Docker Compose installé"

# Vérifier le fichier Firebase
FIREBASE_FILE="app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json"
if [ ! -f "$FIREBASE_FILE" ]; then
    warning "Fichier Firebase non trouvé: $FIREBASE_FILE"
    echo "Vous devrez le copier manuellement avant de démarrer"
else
    success "Fichier Firebase trouvé"
fi

step "Étape 2: Configuration des IPs des serveurs SQL"

echo ""
echo "Veuillez entrer les adresses IP des serveurs SQL Server:"
echo "(Appuyez sur Entrée pour garder les valeurs par défaut)"
echo ""

read -p "IP de srv-asreports [10.101.1.50]: " IP_ASREPORTS
IP_ASREPORTS=${IP_ASREPORTS:-10.101.1.50}

read -p "IP de srv-commercial [10.101.1.51]: " IP_COMMERCIAL
IP_COMMERCIAL=${IP_COMMERCIAL:-10.101.1.51}

echo ""
success "Configuration des IPs:"
echo "  srv-asreports  → $IP_ASREPORTS"
echo "  srv-commercial → $IP_COMMERCIAL"

step "Étape 3: Sauvegarde de l'ancienne configuration"

BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "Dockerfile" ]; then
    cp Dockerfile "$BACKUP_DIR/"
    success "Dockerfile sauvegardé"
fi

if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml "$BACKUP_DIR/"
    success "docker-compose.yml sauvegardé"
fi

if [ -f ".env.docker" ]; then
    cp .env.docker "$BACKUP_DIR/"
    success ".env.docker sauvegardé"
fi

success "Sauvegarde créée dans: $BACKUP_DIR/"

step "Étape 4: Sauvegarde des données Docker"

# Sauvegarder Redis
if docker ps -a | grep -q samaconso_redis; then
    echo "Sauvegarde de Redis..."
    docker exec samaconso_redis redis-cli SAVE 2>/dev/null || warning "Impossible de sauvegarder Redis"
    docker cp samaconso_redis:/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb" 2>/dev/null || warning "Redis dump non disponible"
    success "Redis sauvegardé"
fi

step "Étape 5: Arrêt des conteneurs actuels"

if docker-compose ps | grep -q "Up"; then
    docker-compose down
    success "Conteneurs arrêtés"
else
    warning "Aucun conteneur en cours d'exécution"
fi

step "Étape 6: Mise à jour du fichier docker-compose.fixed.yml avec les IPs"

# Créer une copie temporaire avec les IPs
cp docker-compose.fixed.yml docker-compose.fixed.yml.tmp

# Remplacer les placeholders par les vraies IPs
sed -i "s/srv-asreports:10.101.1.XXX/srv-asreports:$IP_ASREPORTS/g" docker-compose.fixed.yml.tmp
sed -i "s/srv-commercial:10.101.1.XXX/srv-commercial:$IP_COMMERCIAL/g" docker-compose.fixed.yml.tmp

success "IPs configurées dans docker-compose.fixed.yml"

step "Étape 7: Choix du mode de migration"

echo ""
echo "Choisissez le mode de migration:"
echo "1) Tester avec les fichiers .fixed (recommandé pour premier test)"
echo "2) Migration complète (remplacer les fichiers existants)"
echo ""
read -p "Votre choix [1]: " MIGRATION_MODE
MIGRATION_MODE=${MIGRATION_MODE:-1}

if [ "$MIGRATION_MODE" == "2" ]; then
    step "Migration complète sélectionnée"

    mv Dockerfile.fixed Dockerfile
    mv docker-compose.fixed.yml.tmp docker-compose.yml
    mv .env.docker.fixed .env.docker

    success "Fichiers remplacés"
    COMPOSE_FILE="docker-compose.yml"
else
    step "Mode test sélectionné"

    mv docker-compose.fixed.yml.tmp docker-compose.fixed.yml

    success "Utilisation des fichiers .fixed"
    COMPOSE_FILE="docker-compose.fixed.yml"
fi

step "Étape 8: Construction des images Docker"

echo ""
read -p "Reconstruire les images? (recommandé) [O/n]: " REBUILD
REBUILD=${REBUILD:-O}

if [[ "$REBUILD" =~ ^[Oo]$ ]]; then
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    success "Images reconstruites"
else
    warning "Images non reconstruites"
fi

step "Étape 9: Démarrage des services"

echo ""
read -p "Démarrer les services maintenant? [O/n]: " START_SERVICES
START_SERVICES=${START_SERVICES:-O}

if [[ "$START_SERVICES" =~ ^[Oo]$ ]]; then
    docker-compose -f "$COMPOSE_FILE" up -d
    success "Services démarrés"

    echo ""
    echo "Attente du démarrage complet (30 secondes)..."
    sleep 30

    step "Étape 10: Vérification de l'état des conteneurs"

    docker-compose -f "$COMPOSE_FILE" ps

    step "Étape 11: Tests de connectivité"

    echo ""
    echo "Test des drivers ODBC..."
    docker exec samaconso_api python -c "import pyodbc; print('Drivers:', pyodbc.drivers())" || warning "Test drivers échoué"

    echo ""
    echo "Test complet de connectivité..."
    docker exec samaconso_api python test_docker_connectivity.py || warning "Certains tests ont échoué"

else
    warning "Services non démarrés"
    echo ""
    echo "Pour démarrer manuellement:"
    echo "  docker-compose -f $COMPOSE_FILE up -d"
fi

echo ""
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Migration Terminée!                                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo ""
echo "📋 Prochaines étapes:"
echo ""
echo "1. Vérifier les logs:"
echo "   docker logs samaconso_api -f"
echo "   docker logs samaconso_celery_worker -f"
echo ""
echo "2. Tester une API SQL Server:"
echo "   curl http://localhost:8000/api/sic/..."
echo ""
echo "3. Tester les notifications:"
echo "   curl -X POST http://localhost:8000/api/notifications/test"
echo ""
echo "4. Accéder au monitoring:"
echo "   Flower:   http://localhost:5555"
echo "   RabbitMQ: http://localhost:15672"
echo ""
echo "5. Pour restaurer l'ancienne config:"
echo "   cp $BACKUP_DIR/* ."
echo ""

if [ -f "$BACKUP_DIR/redis-dump.rdb" ]; then
    echo "6. Pour restaurer Redis:"
    echo "   docker cp $BACKUP_DIR/redis-dump.rdb samaconso_redis:/data/dump.rdb"
    echo "   docker-compose restart redis"
    echo ""
fi

echo "📖 Consultez GUIDE_DEPLOYMENT_DOCKER.md pour plus de détails"
echo ""

success "Migration terminée avec succès!"
