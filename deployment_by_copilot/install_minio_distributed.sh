#!/bin/bash
# Installation MinIO Distribué (Natif)
# À exécuter sur les 3 serveurs : SRV-MOBAPPBD, SRV-MOBAPP1, SRV-MOBAPP2

if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter en tant que root (sudo)"
    exit 1
fi

# 1. Téléchargement du binaire
echo "Téléchargement de MinIO..."
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
mv minio /usr/local/bin/

# 2. Création utilisateur et dossiers
# Création de l'utilisateur de service 'samaconso' s'il n'existe pas
if ! id "samaconso" &>/dev/null; then
    useradd -r -s /bin/false samaconso
    echo "Utilisateur 'samaconso' créé."
fi

mkdir -p /data/minio
chown samaconso:samaconso /data/minio
chmod 750 /data/minio

# 3. Configuration Systemd
# Détecter l'IP du serveur actuel
CURRENT_IP=$(hostname -I | awk '{print $1}')

# Déterminer le rôle du serveur
if [[ "$CURRENT_IP" == *"212"* ]] || [[ "$(hostname)" == *"MOBAPPBD"* ]]; then
    SERVER_ROLE="node1"
    MINIO_VOLUMES="/data/minio"
elif [[ "$CURRENT_IP" == *"210"* ]] || [[ "$(hostname)" == *"MOBAPP1"* ]]; then
    SERVER_ROLE="node2"
    MINIO_VOLUMES="/data/minio"
elif [[ "$CURRENT_IP" == *"211"* ]] || [[ "$(hostname)" == *"MOBAPP2"* ]]; then
    SERVER_ROLE="node3"
    MINIO_VOLUMES="/data/minio"
else
    echo "ERREUR: Impossible de déterminer le rôle du serveur"
    exit 1
fi

cat > /etc/default/minio << EOF
# Volume à utiliser pour le stockage (chemin local uniquement)
# Pour un cluster distribué, chaque nœud doit pointer vers son propre répertoire
MINIO_VOLUMES="${MINIO_VOLUMES}"

# Options de démarrage
MINIO_OPTS="--console-address :9001 --address :9000"

# Identifiants Root
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=Senelec2024!

# Pour le mode distribué, ajouter après le premier démarrage:
# MINIO_VOLUMES="http://10.101.1.212:9000/data/minio http://10.101.1.210:9000/data/minio http://10.101.1.211:9000/data/minio"
EOF

cat > /etc/systemd/system/minio.service << EOF
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target

[Service]
User=samaconso
Group=samaconso
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server \$MINIO_OPTS \$MINIO_VOLUMES
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 4. Démarrage
systemctl daemon-reload
systemctl enable minio
systemctl start minio

echo "MinIO installé et démarré."
