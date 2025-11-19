#!/bin/bash
# Installation PostgreSQL 17 PRIMARY + PgBouncer
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

# --- NETTOYAGE PRÉALABLE FORCÉ (POUR DÉBLOQUER LA SITUATION) ---
echo ">>> Nettoyage forcé des installations précédentes..."
systemctl stop postgresql || true
systemctl stop pgbouncer || true

# Utilisation des outils postgres pour nettoyer si possible
if command -v pg_dropcluster >/dev/null; then
    echo "Suppression du cluster via pg_dropcluster..."
    pg_dropcluster --stop 17 main || true
fi

# Nettoyage manuel des restes
rm -rf /data/postgres/data
rm -rf /etc/postgresql/17/main 
rm -rf /var/lib/postgresql/17/main
# Nettoyage du socket au cas où
rm -f /var/run/postgresql/.s.PGSQL.5432
rm -f /var/run/postgresql/.s.PGSQL.5432.lock

echo ">>> Nettoyage terminé. Début de l'installation propre."
# ---------------------------------------------------------------

# Mode non-interactif pour éviter les popups (needrestart, etc.)
export DEBIAN_FRONTEND=noninteractive
if [ -f /etc/needrestart/needrestart.conf ]; then
    sed -i "s/#\$nrconf{restart} = 'i';/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf
fi

# Mise à jour
apt-get update && apt-get upgrade -y

# CORRECTION : Génération des locales (Fix: invalid value for parameter "lc_messages": "en_US.UTF-8")
echo "Génération des locales..."
apt-get install -y locales
locale-gen en_US.UTF-8
locale-gen fr_FR.UTF-8
update-locale LANG=en_US.UTF-8

# Installation PostgreSQL 17
echo "Installation de PostgreSQL 17..."
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt-get update

# Installation avec réinitialisation des fichiers de config
apt-get -o Dpkg::Options::="--force-confnew" install --reinstall -y postgresql-17 postgresql-contrib-17

# --- CORRECTION : Forcer la création du cluster si apt ne l'a pas fait ---
if [ ! -d "/etc/postgresql/17/main" ]; then
    echo "Création explicite du cluster PostgreSQL 17 main..."
    # On s'assure que le dossier de données par défaut est propre
    rm -rf /var/lib/postgresql/17/main
    # On crée le cluster sans le démarrer tout de suite
    pg_createcluster 17 main
fi
# -----------------------------------------------------------------------

# Arrêter PostgreSQL pour la configuration
systemctl stop postgresql

# Installation PgBouncer
echo "Installation de PgBouncer..."
apt-get install -y pgbouncer

# Créer les répertoires
mkdir -p /data/postgres/{data,archive,backup,wal_archive}
mkdir -p /var/log/postgresql
# CORRECTION : On s'assure que postgres a accès à tout le chemin
chown -R postgres:postgres /data/postgres
chmod 750 /data/postgres
chmod 700 /data/postgres/data

# Configuration PostgreSQL
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_CONF="/etc/postgresql/17/main/postgresql.conf"

# Backup du fichier par défaut
if [ ! -f "$TARGET_CONF.bak" ]; then
    cp "$TARGET_CONF" "$TARGET_CONF.bak"
fi

# Ajouter nos configurations à la fin du fichier
cat "$SCRIPT_DIR/postgresql.conf" >> "$TARGET_CONF"

# Modifier le répertoire de données pour pointer vers /data/postgres/data
sed -i "s|data_directory = .*|data_directory = '/data/postgres/data'|g" "$TARGET_CONF"

# Configuration pg_hba.conf
cat >> /etc/postgresql/17/main/pg_hba.conf << EOF

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

# Initialisation des données (Puisqu'on a tout nettoyé au début, on passe forcément ici)
echo "Initialisation des données PostgreSQL 17 dans /data/postgres/data..."
if [ -d "/var/lib/postgresql/17/main" ]; then
    # On copie les fichiers de base créés par l'installation apt
    rsync -av /var/lib/postgresql/17/main/ /data/postgres/data/
fi

# CORRECTION : Supprimer un éventuel fichier PID copié par erreur qui empêcherait le démarrage
rm -f /data/postgres/data/postmaster.pid

# CORRECTION : On réapplique les droits après la copie
chown -R postgres:postgres /data/postgres/data
chmod 700 /data/postgres/data

# --- CORRECTION APPARMOR (Si présent) ---
# PostgreSQL peut être bloqué par AppArmor s'il essaie d'écrire ailleurs que dans /var/lib/postgresql
if [ -d "/etc/apparmor.d/local" ]; then
    echo "Configuration AppArmor pour autoriser /data/postgres..."
    AA_FILE="/etc/apparmor.d/local/usr.lib.postgresql.bin.postgres"
    # On vérifie si la ligne existe déjà pour éviter les doublons
    if ! grep -q "/data/postgres/" "$AA_FILE" 2>/dev/null; then
        echo "/data/postgres/ r," >> "$AA_FILE"
        echo "/data/postgres/** rwk," >> "$AA_FILE"
        systemctl reload apparmor || true
    fi
fi
# ----------------------------------------

# Démarrer PostgreSQL
echo "Démarrage de PostgreSQL..."
systemctl enable postgresql

# On redémarre le service parent (peut échouer si aucun cluster par défaut, on ignore)
systemctl restart postgresql || true

echo "Tentative de démarrage du cluster 17-main..."
# On utilise un bloc if pour capturer l'erreur sans quitter le script immédiatement (malgré set -e)
if ! systemctl restart postgresql@17-main; then
    echo "ERREUR CRITIQUE: Échec du démarrage du service postgresql@17-main"
    echo "--- DIAGNOSTIC IMMÉDIAT ---"
    echo ">>> journalctl -xeu postgresql@17-main :"
    journalctl -xeu postgresql@17-main --no-pager | tail -n 50
    echo ">>> Log file (/var/log/postgresql/postgresql-17-main.log) :"
    tail -n 50 /var/log/postgresql/postgresql-17-main.log 2>/dev/null || echo "Fichier de log introuvable."
    exit 1
fi

# Attente active du démarrage
echo "Attente du démarrage de PostgreSQL..."
for i in {1..30}; do
    # On vérifie le service SPÉCIFIQUE
    if systemctl is-active --quiet postgresql@17-main; then
        echo "Cluster PostgreSQL 17-main est démarré."
        break
    fi
    echo "En attente..."
    sleep 2
done

# Vérification supplémentaire du socket
echo "Vérification du socket..."
SOCKET_FOUND=false
for i in {1..30}; do
    if [ -S "/var/run/postgresql/.s.PGSQL.5432" ]; then
        echo "Socket PostgreSQL détecté."
        SOCKET_FOUND=true
        break
    fi
    sleep 1
done

if [ "$SOCKET_FOUND" = false ]; then
    echo "ERREUR: Le socket PostgreSQL n'a pas été détecté."
    echo "--- DIAGNOSTIC PRÉCIS ---"
    echo "État du cluster 17-main :"
    systemctl status postgresql@17-main --no-pager
    echo "--- LOGS DU CLUSTER ---"
    journalctl -xeu postgresql@17-main --no-pager | tail -n 50
    echo "--- LOGS POSTGRESQL (Fichier) ---"
    tail -n 50 /var/log/postgresql/postgresql-17-main.log 2>/dev/null || echo "Pas de fichier de log trouvé."
    echo "-------------------------"
    exit 1
fi

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
echo '"samaconso_app" "S3N3l3c2025!"' > /etc/pgbouncer/userlist.txt
echo '"postgres" "S3N3l3c2025!"' >> /etc/pgbouncer/userlist.txt

# CORRECTION : Forcer PgBouncer à tourner sous l'utilisateur 'postgres' pour éviter les problèmes de droits
# Cela permet de lire userlist.txt (600 postgres) et d'écrire dans les logs
mkdir -p /etc/systemd/system/pgbouncer.service.d
cat > /etc/systemd/system/pgbouncer.service.d/override.conf <<EOF
[Service]
User=postgres
Group=postgres
EOF
systemctl daemon-reload

# Permissions des fichiers de configuration
chown postgres:postgres /etc/pgbouncer/userlist.txt
chmod 600 /etc/pgbouncer/userlist.txt
chown postgres:postgres /etc/pgbouncer/pgbouncer.ini

# Préparation des dossiers de logs et run
mkdir -p /var/log/pgbouncer
chown -R postgres:postgres /var/log/pgbouncer
chmod 750 /var/log/pgbouncer

mkdir -p /var/run/pgbouncer
chown -R postgres:postgres /var/run/pgbouncer
chmod 750 /var/run/pgbouncer

# Redémarrer PgBouncer
systemctl enable pgbouncer
echo "Démarrage de PgBouncer..."
if ! systemctl restart pgbouncer; then
    echo "ERREUR: Échec du démarrage de PgBouncer"
    echo "--- DIAGNOSTIC PGBOUNCER ---"
    echo ">>> systemctl status pgbouncer :"
    systemctl status pgbouncer --no-pager
    echo ">>> journalctl -xeu pgbouncer :"
    journalctl -xeu pgbouncer --no-pager | tail -n 20
    echo ">>> Log file (/var/log/pgbouncer/pgbouncer.log) :"
    tail -n 20 /var/log/pgbouncer/pgbouncer.log 2>/dev/null || echo "Fichier de log introuvable."
    exit 1
fi

echo "Installation terminée avec succès !"
