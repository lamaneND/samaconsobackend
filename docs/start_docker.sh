#!/bin/bash

# Script de démarrage pour l'application SamaConso

echo "🚀 Démarrage de SamaConso API avec Docker..."

# Vérifier si Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

# Arrêter les conteneurs existants
echo "🛑 Arrêt des conteneurs existants..."
docker-compose down

# Construire les images
echo "🔨 Construction des images Docker..."
docker-compose build

# Démarrer les services
echo "▶️ Démarrage des services..."
docker-compose up -d

# Attendre que les services soient prêts
echo "⏳ Attente du démarrage des services..."
sleep 10

# Vérifier le statut des services
echo "🔍 Vérification du statut des services..."
docker-compose ps

echo "✅ SamaConso API démarré avec succès !"
echo ""
echo "📊 Services disponibles :"
echo "   - API FastAPI: http://localhost:8000"
echo "   - RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "   - Flower (Celery Monitor): http://localhost:5555"
echo "   - Redis: localhost:6379"
echo ""
echo "📝 Commandes utiles :"
echo "   - Voir les logs: docker-compose logs -f"
echo "   - Arrêter: docker-compose down"
echo "   - Redémarrer: docker-compose restart"
echo "   - Shell dans le conteneur API: docker exec -it samaconso_api bash"