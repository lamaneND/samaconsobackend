#!/bin/bash

# Script de démarrage des workers Celery pour SamaConso

echo "🚀 Démarrage des workers Celery pour SamaConso"

# Worker urgent (notifications critiques)
echo "⚡ Démarrage worker urgent..."
celery -A app.celery_app worker \
    --loglevel=info \
    --queues=urgent,high_priority \
    --concurrency=4 \
    --prefetch-multiplier=1 \
    --pool=prefork \
    --time-limit=300 \
    --soft-time-limit=240 \
    --max-tasks-per-child=50 \
    --logfile=logs/celery-urgent.log \
    --pidfile=pids/celery-urgent.pid \
    --detach

# Worker normal (notifications standards)
echo "📤 Démarrage worker normal..."
celery -A app.celery_app worker \
    --loglevel=info \
    --queues=normal \
    --concurrency=6 \
    --prefetch-multiplier=4 \
    --pool=prefork \
    --time-limit=600 \
    --soft-time-limit=540 \
    --max-tasks-per-child=100 \
    --logfile=logs/celery-normal.log \
    --pidfile=pids/celery-normal.pid \
    --detach

# Worker broadcast (diffusions massives)
echo "📡 Démarrage worker broadcast..."
celery -A app.celery_app worker \
    --loglevel=info \
    --queues=low_priority \
    --concurrency=2 \
    --prefetch-multiplier=10 \
    --pool=prefork \
    --time-limit=1200 \
    --soft-time-limit=1080 \
    --max-tasks-per-child=20 \
    --logfile=logs/celery-broadcast.log \
    --pidfile=pids/celery-broadcast.pid \
    --detach

echo "✅ Tous les workers Celery sont démarrés"
echo "📊 Monitoring disponible sur Flower: http://localhost:5555"
echo "🐰 RabbitMQ Management: http://localhost:15672"