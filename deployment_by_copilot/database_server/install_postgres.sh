#!/bin/bash
# Installation PostgreSQL 15 PRIMARY + PgBouncer
# SRV-MOBAPPBD (10.101.1.212)

set -e

echo "=========================================="
echo "Installation PostgreSQL PRIMARY + PgBouncer"
echo "SRV-MOBAPPBD (10.101.1.212)"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter en tant que root (sudo)"
    exit 1
fi

# Mise à jour
apt-get update && apt-get upgrade -y

# Installation PostgreSQL 15
echo "Installation de PostgreSQL 15..."
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt-get update
apt-get install -y postgresql-15 postgresql-contrib-15 postgresql-15-pg-stat-statements

# Installation PgBouncer
echo "Installation de PgBouncer..."
apt-get install -y pgbouncer

# Créer les répertoires
mkdir -p /data/postgres/{data,archive,backup,wal_archive}
mkdir -p /var/log/postgresql
chown -R postgres:postgres /data/postgres
chmod 700 /data/postgres/data

# Copier la configuration PostgreSQL
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/postgresql.conf" /etc/postgresql/15/main/postgresql.conf

# Configuration pg_hba.conf
cat >> /etc/postgresql/15/main/pg_hba.conf << EOF

# SamaConso - Connexions via PgBouncer
host    samaconso    samaconso_app    10.101.1.0/24    md5
host    samaconso    samaconso_app    127.0.0.1/32     md5

# Réplication streaming
host    replication     replicator     10.101.1.210/32    md5
host    replication     replicator     10.101.1.211/32    md5

# Connexions locales
local   all         postgres                          peer
local   all         all                               peer
host    all         postgres    127.0.0.1/32          md5
EOF

# Déplacer les données vers /data/postgres/data
if [ ! -d "/data/postgres/data/base" ]; then
    echo "Déplacement des données vers /data/postgres/data..."
    systemctl stop postgresql
    if [ -d "/var/lib/postgresql/15/main" ]; then
        rsync -av /var/lib/postgresql/15/main/ /data/postgres/data/
    fi
    chown -R postgres:postgres /data/postgres/data
fi

# Démarrer PostgreSQL
systemctl enable postgresql
systemctl start postgresql

# Créer la base de données et les utilisateurs
sudo -u postgres psql << EOF
-- Créer l'utilisateur application
CREATE USER samaconso_app WITH PASSWORD 'S3N3l3c2025!';

-- Créer l'utilisateur de réplication
CREATE USER replicator WITH REPLICATION PASSWORD 'Replicator2025!';

-- Créer la base de données
CREATE DATABASE samaconso OWNER samaconso_app;

-- Permissions
GRANT ALL PRIVILEGES ON DATABASE samaconso TO samaconso_app;
ALTER USER samaconso_app WITH CONNECTION LIMIT 100;

-- Extensions
\c samaconso
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
EOF

# Configuration PgBouncer
cp "$SCRIPT_DIR/pgbouncer.ini" /etc/pgbouncer/pgbouncer.ini

# Création du fichier userlist.txt pour PgBouncer
echo '"samaconso_app" "Senelec2024!"' > /etc/pgbouncer/userlist.txt
echo '"postgres" "Senelec2024!"' >> /etc/pgbouncer/userlist.txt
chown postgres:postgres /etc/pgbouncer/userlist.txt
chmod 600 /etc/pgbouncer/userlist.txt

# Redémarrer PgBouncer
systemctl enable pgbouncer
systemctl restart pgbouncer

echo "Installation terminée avec succès !"
