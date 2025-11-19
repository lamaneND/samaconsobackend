#!/bin/bash
# Script pour configurer le cluster RabbitMQ
# À exécuter sur SRV-MOBAPP2 (10.101.1.211) après le démarrage des deux nœuds

set -e

echo "=========================================="
echo "Configuration du Cluster RabbitMQ"
echo "=========================================="

# Vérifier qu'on est sur SRV-MOBAPP2
HOSTNAME=$(hostname)
if [[ ! "$HOSTNAME" == *"MOBAPP2"* ]] && [[ ! "$(hostname -I)" == *"211"* ]]; then
    echo "ATTENTION: Ce script doit être exécuté sur SRV-MOBAPP2"
    read -p "Continuer quand même? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

CONTAINER_NAME="samaconso_rabbitmq"
MASTER_NODE="rabbit@rabbitmq1"

echo "Vérification que RabbitMQ est démarré..."
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "ERREUR: Le conteneur $CONTAINER_NAME n'est pas démarré"
    exit 1
fi

echo "Arrêt de l'application RabbitMQ..."
docker exec -it $CONTAINER_NAME rabbitmqctl stop_app

echo "Rejoindre le cluster (Master: $MASTER_NODE)..."
docker exec -it $CONTAINER_NAME rabbitmqctl join_cluster $MASTER_NODE

echo "Démarrage de l'application RabbitMQ..."
docker exec -it $CONTAINER_NAME rabbitmqctl start_app

echo "Vérification du statut du cluster..."
docker exec -it $CONTAINER_NAME rabbitmqctl cluster_status

echo ""
echo "=========================================="
echo "Cluster RabbitMQ configuré avec succès!"
echo "=========================================="
echo "Accédez à la console: http://10.101.1.210:15672"
echo "Utilisateur: admin / Mot de passe: S3N3l3c2025!"

