#!/bin/bash
# Script de vérification de santé de tous les services

set -e

DB_SERVER="10.101.1.57"
APP_SERVER_1="10.101.1.210"
APP_SERVER_2="10.101.1.211"

echo "=========================================="
echo "Vérification de Santé - SamaConso"
echo "=========================================="
echo ""

# Fonction pour tester la connectivité
test_connection() {
    local host=$1
    local port=$2
    local service=$3
    
    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        echo "✓ $service ($host:$port) - OK"
        return 0
    else
        echo "✗ $service ($host:$port) - ÉCHEC"
        return 1
    fi
}

# Tests sur SRV-MOBAPPBD
echo "=== SRV-MOBAPPBD (10.101.1.57) ==="
test_connection $DB_SERVER 5432 "PostgreSQL"
test_connection $DB_SERVER 6379 "Redis"
test_connection $DB_SERVER 5672 "RabbitMQ"
test_connection $DB_SERVER 15672 "RabbitMQ Management"
test_connection $DB_SERVER 9000 "MinIO API"
test_connection $DB_SERVER 9001 "MinIO Console"
echo ""

# Tests sur SRV-MOBAPP1
echo "=== SRV-MOBAPP1 (10.101.1.210) ==="
test_connection $APP_SERVER_1 8000 "API FastAPI"
test_connection $APP_SERVER_1 5555 "Flower"
test_connection $APP_SERVER_1 80 "Nginx"
echo ""

# Tests sur SRV-MOBAPP2
echo "=== SRV-MOBAPP2 (10.101.1.211) ==="
test_connection $APP_SERVER_2 8000 "API FastAPI"
echo ""

# Test de l'API via HTTP
echo "=== Tests HTTP ==="
echo -n "API SRV-MOBAPP1: "
if curl -sf http://$APP_SERVER_1:8000/health > /dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ ÉCHEC"
fi

echo -n "API SRV-MOBAPP2: "
if curl -sf http://$APP_SERVER_2:8000/health > /dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ ÉCHEC"
fi

echo -n "Load Balancer (Nginx): "
if curl -sf http://$APP_SERVER_1/health > /dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ ÉCHEC"
fi

echo ""
echo "=========================================="
echo "Vérification terminée"
echo "=========================================="

