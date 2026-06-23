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
CREATE USER samaconso_app WITH PASSWORD '$3N3l3c2025!';

-- Créer l'utilisateur de réplication
CREATE USER replicator WITH REPLICATION PASSWORD 'Replicator2024!';

-- Créer la base de données
CREATE DATABASE samaconso OWNER samaconso_app;

-- Permissions
GRANT ALL PRIVILEGES ON DATABASE samaconso TO samaconso_app;
ALTER USER samaconso_app WITH CONNECTION LIMIT 100;

-- Créer les slots de réplication
SELECT pg_create_physical_replication_slot('replication_slot_1');
SELECT pg_create_physical_replication_slot('replication_slot_2');

-- Extensions
\c samaconso
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
EOF

# Configuration PgBouncer
cp "$SCRIPT_DIR/pgbouncer.ini" /etc/pgbouncer/pgbouncer.ini

# Créer le fichier d'authentification PgBouncer
mkdir -p /etc/pgbouncer
PG_PASSWORD_HASH=$(echo -n 'postgres' + 's3n3l3c123' | md5sum | cut -d' ' -f1)
APP_PASSWORD_HASH=$(echo -n 'samaconso_app' + '$3N3l3c2025!' | md5sum | cut -d' ' -f1)

cat > /etc/pgbouncer/userlist.txt << EOF
"postgres" "md5${PG_PASSWORD_HASH}"
"samaconso_app" "md5${APP_PASSWORD_HASH}"
EOF

# Créer les répertoires pour PgBouncer
mkdir -p /var/log/pgbouncer /var/run/pgbouncer
chown -R postgres:postgres /var/log/pgbouncer /var/run/pgbouncer
chmod 755 /var/log/pgbouncer /var/run/pgbouncer

# Configuration systemd pour PgBouncer
cat > /etc/systemd/system/pgbouncer.service << EOF
[Unit]
Description=pgBouncer connection pooler
After=network.target postgresql.service

[Service]
Type=forking
User=postgres
ExecStart=/usr/bin/pgbouncer -d /etc/pgbouncer/pgbouncer.ini
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Démarrer PgBouncer
systemctl daemon-reload
systemctl enable pgbouncer
systemctl start pgbouncer

# Configuration firewall
if command -v ufw &> /dev/null; then
    ufw allow 5432/tcp  # PostgreSQL (seulement local)
    ufw allow 6432/tcp  # PgBouncer
fi

echo "=========================================="
echo "Installation terminée!"
echo "=========================================="
echo "PostgreSQL: localhost:5432"
echo "PgBouncer:  0.0.0.0:6432"
echo "=========================================="

