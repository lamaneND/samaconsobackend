#!/bin/bash
# Installation MinIO en mode distribué
# Usage: install-minio-distributed.sh SERVER_NAME SERVER_IP NODE_NUMBER

set -e

SERVER_NAME=${1}
SERVER_IP=${2}
NODE_NUMBER=${3}

echo "=========================================="
echo "Installation MinIO Node $NODE_NUMBER"
echo "Serveur: $SERVER_NAME ($SERVER_IP)"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter en tant que root (sudo)"
    exit 1
fi

# Télécharger MinIO
cd /tmp
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
mv minio /usr/local/bin/

# Créer l'utilisateur
if ! id "minio" &>/dev/null; then
    useradd -r -s /bin/false minio
fi

# Créer les répertoires
mkdir -p /data/minio/{data1,data2,data3,data4}
chown -R minio:minio /data/minio

# Configuration MinIO distribué
cat > /etc/minio/minio.env << EOF
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=Senelec2024!
MINIO_VOLUMES=http://10.101.1.212/data/minio/data{1...4} http://10.101.1.210/data/minio/data{1...4} http://10.101.1.211/data/minio/data{1...4}
MINIO_OPTS="--console-address :9001"
EOF

# Configuration systemd
cat > /etc/systemd/system/minio.service << EOF
[Unit]
Description=MinIO Object Storage
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target
AssertFileIsExecutable=/usr/local/bin/minio

[Service]
WorkingDirectory=/usr/local/
User=minio
Group=minio
EnvironmentFile=/etc/minio/minio.env
ExecStartPre=/bin/bash -c "if [ -z \"\${MINIO_VOLUMES}\" ]; then echo \"Variable MINIO_VOLUMES not set\"; exit 1; fi"
ExecStart=/usr/local/bin/minio server \$MINIO_OPTS \$MINIO_VOLUMES
Restart=always
LimitNOFILE=65536
TasksMax=infinity
SendSIGPIPE=no

[Install]
WantedBy=multi-user.target
EOF

# Démarrer MinIO
systemctl daemon-reload
systemctl enable minio
systemctl start minio

# Firewall
if command -v ufw &> /dev/null; then
    ufw allow 9000/tcp
    ufw allow 9001/tcp
fi

echo "=========================================="
echo "MinIO Node $NODE_NUMBER installé!"
echo "=========================================="

