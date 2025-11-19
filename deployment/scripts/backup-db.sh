#!/bin/bash
# Script de sauvegarde de la base de données PostgreSQL

set -e

BACKUP_DIR="/opt/backups/samaconso"
DB_SERVER="10.101.1.57"
DB_NAME="samaconso"
DB_USER="postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/samaconso_backup_$TIMESTAMP.sql"

echo "=========================================="
echo "Sauvegarde de la base de données"
echo "=========================================="

# Créer le répertoire de sauvegarde
mkdir -p $BACKUP_DIR

# Exécuter la sauvegarde
echo "Création de la sauvegarde..."
docker exec samaconso_postgres pg_dump -U $DB_USER $DB_NAME > $BACKUP_FILE

# Compresser la sauvegarde
echo "Compression de la sauvegarde..."
gzip $BACKUP_FILE
BACKUP_FILE="${BACKUP_FILE}.gz"

# Vérifier la taille
SIZE=$(du -h $BACKUP_FILE | cut -f1)
echo "Sauvegarde créée: $BACKUP_FILE ($SIZE)"

# Nettoyer les anciennes sauvegardes (garder les 7 derniers jours)
echo "Nettoyage des anciennes sauvegardes..."
find $BACKUP_DIR -name "samaconso_backup_*.sql.gz" -mtime +7 -delete

echo "=========================================="
echo "Sauvegarde terminée"
echo "=========================================="

