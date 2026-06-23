#!/bin/bash
# Installation PostgreSQL STANDBY
# SRV-MOBAPP1 (10.101.1.210)

set -e

echo "=========================================="
echo "Installation PostgreSQL STANDBY"
echo "SRV-MOBAPP1 (10.101.1.210)"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter en tant que root (sudo)"
    exit 1
fi

# Installation PostgreSQL 15
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt-get update
apt-get install -y postgresql-15 postgresql-contrib-15

# Créer les répertoires
mkdir -p /data/postgres/standby
chown -R postgres:postgres /data/postgres
chmod 700 /data/postgres/standby

# Arrêter PostgreSQL
systemctl stop postgresql

# Backup depuis Primary
echo "Création du backup depuis Primary..."
sudo -u postgres pg_basebackup \
    -h 10.101.1.212 \
    -D /data/postgres/standby \
    -U replicator \
    -P -v -R -X stream \
    -S replication_slot_1

# Configuration recovery
cat > /data/postgres/standby/postgresql.auto.conf << EOF
primary_conninfo = 'host=10.101.1.212 port=5432 user=replicator password=Replicator2024!'
primary_slot_name = 'replication_slot_1'
EOF

# Configuration postgresql.conf pour Standby
cat >> /etc/postgresql/15/main/postgresql.conf << EOF
# Standby configuration
hot_standby = on
hot_standby_feedback = on
max_standby_streaming_delay = 30s
wal_receiver_timeout = 60s
EOF

# Modifier data_directory
sed -i "s|data_directory = .*|data_directory = '/data/postgres/standby'|" /etc/postgresql/15/main/postgresql.conf

# Démarrer PostgreSQL
systemctl start postgresql

echo "=========================================="
echo "PostgreSQL Standby installé!"
echo "=========================================="

