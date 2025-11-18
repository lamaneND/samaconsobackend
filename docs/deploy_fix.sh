#!/bin/bash

###############################################################################
# Script de déploiement rapide - SamaConso API
# Correction SQL Server + Firebase
# IPs configurées: srv-asreports=10.101.2.87, srv-commercial=10.101.3.243
###############################################################################

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "============================================================"
echo "  Déploiement Docker Corrigé - SamaConso API"
echo "  IPs: srv-asreports=10.101.2.87"
echo "       srv-commercial=10.101.3.243"
echo "============================================================"
echo -e "${NC}"

echo -e "${BLUE}[Etape 1/5]${NC} Arrêt des conteneurs actuels..."
docker-compose down || echo -e "${YELLOW}ATTENTION: Impossible d'arrêter les conteneurs existants${NC}"

echo ""
echo -e "${BLUE}[Etape 2/5]${NC} Vérification du fichier Firebase..."
if [ -f "app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json" ]; then
    echo -e "${GREEN}✅ Fichier Firebase trouvé${NC}"
else
    echo -e "${RED}❌ Fichier Firebase NON trouvé!${NC}"
    echo "Veuillez copier le fichier dans app/"
    exit 1
fi

echo ""
echo -e "${BLUE}[Etape 3/5]${NC} Construction des images Docker (cela peut prendre 2-3 minutes)..."
docker-compose -f docker-compose.fixed.yml build --no-cache

echo ""
echo -e "${BLUE}[Etape 4/5]${NC} Démarrage des conteneurs..."
docker-compose -f docker-compose.fixed.yml up -d

echo ""
echo -e "${BLUE}[Etape 5/5]${NC} Attente du démarrage complet (30 secondes)..."
sleep 30

echo ""
echo -e "${BLUE}"
echo "============================================================"
echo "  État des conteneurs"
echo "============================================================"
echo -e "${NC}"
docker ps --filter "name=samaconso"

echo ""
echo -e "${BLUE}"
echo "============================================================"
echo "  Tests de validation"
echo "============================================================"
echo -e "${NC}"

echo ""
echo "Test 1: Vérification des drivers SQL Server..."
docker exec samaconso_api python -c "import pyodbc; print('Drivers:', pyodbc.drivers())" || echo -e "${RED}Test échoué${NC}"

echo ""
echo "Test 2: Diagnostic complet..."
docker exec samaconso_api python test_docker_connectivity.py || echo -e "${YELLOW}Certains tests ont échoué${NC}"

echo ""
echo -e "${GREEN}"
echo "============================================================"
echo "  Déploiement Terminé!"
echo "============================================================"
echo -e "${NC}"
echo ""
echo "Services disponibles:"
echo "  - API FastAPI:         http://localhost:8000"
echo "  - Flower (Celery):     http://localhost:5555"
echo "  - RabbitMQ Management: http://localhost:15672"
echo ""
echo "Pour voir les logs:"
echo "  docker logs samaconso_api -f"
echo "  docker logs samaconso_celery_worker -f"
echo ""
