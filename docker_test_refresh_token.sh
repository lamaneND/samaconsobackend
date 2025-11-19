#!/bin/bash
# Script pour tester le refresh token avec Docker

echo "============================================"
echo "  TEST REFRESH TOKEN - SamaConso API"
echo "============================================"

# Vérifier si Docker est en cours d'exécution
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker n'est pas en cours d'exécution"
    echo "   Veuillez démarrer Docker Desktop"
    exit 1
fi

# Vérifier si les conteneurs existent
if ! docker ps --filter "name=samaconso_api" --format "{{.Names}}" | grep -q "samaconso_api"; then
    echo "⚠️  Le conteneur samaconso_api n'est pas en cours d'exécution"
    echo "   Démarrage des conteneurs Docker..."
    docker-compose up -d
    echo "   Attente du démarrage de l'API (30 secondes)..."
    sleep 30
fi

# Vérifier que l'API répond
echo "Vérification de la santé de l'API..."
if curl -f http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ API accessible"
else
    echo "❌ API non accessible sur http://localhost:8000"
    echo "   Vérifiez les logs: docker logs samaconso_api"
    exit 1
fi

# Exécuter la migration Alembic
echo ""
echo "Exécution de la migration Alembic..."
docker exec samaconso_api alembic upgrade head
if [ $? -eq 0 ]; then
    echo "✅ Migration exécutée avec succès"
else
    echo "⚠️  Erreur lors de la migration (peut-être déjà appliquée)"
fi

# Exécuter les tests Python
echo ""
echo "Exécution des tests Python..."
docker exec -it samaconso_api python /app/test_refresh_token.py

echo ""
echo "============================================"
echo "  Tests terminés"
echo "============================================"

