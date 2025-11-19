#!/bin/bash
# Configuration RabbitMQ Cluster
# À exécuter sur SRV-MOBAPP2 après démarrage des deux nodes

set -e

echo "=========================================="
echo "Configuration RabbitMQ Cluster"
echo "=========================================="

# Attendre que RabbitMQ Node 1 soit prêt
echo "Attente de RabbitMQ Node 1..."
sleep 30

# Joindre le cluster depuis Node 2
echo "Configuration du cluster..."
docker exec rabbitmq_node2 rabbitmqctl stop_app
docker exec rabbitmq_node2 rabbitmqctl join_cluster rabbit@rabbitmq-node1
docker exec rabbitmq_node2 rabbitmqctl start_app

# Vérifier le cluster
echo "Vérification du cluster..."
docker exec rabbitmq_node1 rabbitmqctl cluster_status
docker exec rabbitmq_node2 rabbitmqctl cluster_status

echo "=========================================="
echo "RabbitMQ Cluster configuré!"
echo "=========================================="

