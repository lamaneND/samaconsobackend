#!/bin/bash
# Script de configuration de Nginx pour le load balancing
# À exécuter sur SRV-MOBAPP1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "Configuration Nginx Load Balancer"
echo "=========================================="

# Vérifier si on est root
if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter ce script en tant que root (sudo)"
    exit 1
fi

# Copier la configuration Nginx
echo "Copie de la configuration Nginx..."
cp "$PROJECT_DIR/deployment/nginx/nginx.conf" /etc/nginx/sites-available/samaconso

# Créer le lien symbolique
if [ ! -L /etc/nginx/sites-enabled/samaconso ]; then
    ln -s /etc/nginx/sites-available/samaconso /etc/nginx/sites-enabled/samaconso
fi

# Désactiver la configuration par défaut
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi

# Tester la configuration
echo "Test de la configuration Nginx..."
nginx -t

# Redémarrer Nginx
echo "Redémarrage de Nginx..."
systemctl restart nginx
systemctl enable nginx

# Vérifier le statut
systemctl status nginx --no-pager

echo "=========================================="
echo "Configuration terminée!"
echo "=========================================="
echo "Nginx est configuré pour le load balancing"
echo "Accès API: http://10.101.1.210/"
echo "Accès Flower: http://10.101.1.210/flower (réseau interne uniquement)"
echo "=========================================="

