#!/bin/bash
# Script d'installation pour SRV-MOBAPPBD (10.101.1.57)
# Installation de Docker, Docker Compose et configuration des partitions

set -e

echo "=========================================="
echo "Installation SRV-MOBAPPBD (Serveur Base de Données)"
echo "=========================================="

# Vérifier si on est root
if [ "$EUID" -ne 0 ]; then 
    echo "Veuillez exécuter ce script en tant que root (sudo)"
    exit 1
fi

# Mise à jour du système
echo "Mise à jour du système..."
apt-get update && apt-get upgrade -y

# Installation des dépendances
echo "Installation des dépendances..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    vim \
    htop \
    net-tools

# Installation de Docker
echo "Installation de Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
else
    echo "Docker est déjà installé"
fi

# Installation de Docker Compose standalone (si nécessaire)
if ! command -v docker-compose &> /dev/null; then
    echo "Installation de Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
else
    echo "Docker Compose est déjà installé"
fi

# Configuration des partitions de données
echo "Configuration des partitions de données..."
mkdir -p /data/{postgres,redis,rabbitmq,minio}
chmod 755 /data
chmod 700 /data/{postgres,redis,rabbitmq,minio}

# Configuration des limites système pour PostgreSQL
echo "Configuration des limites système..."
cat >> /etc/sysctl.conf << EOF
# Optimisations pour PostgreSQL
kernel.shmmax = 68719476736
kernel.shmall = 16777216
vm.overcommit_memory = 2
vm.swappiness = 1
EOF

sysctl -p

# Configuration des limites utilisateur
cat >> /etc/security/limits.conf << EOF
# Limites pour PostgreSQL
postgres soft nofile 65536
postgres hard nofile 65536
postgres soft nproc 16384
postgres hard nproc 16384
EOF

# Configuration du firewall
echo "Configuration du firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp    # SSH
    ufw allow 5432/tcp  # PostgreSQL
    ufw allow 6379/tcp  # Redis
    ufw allow 5672/tcp  # RabbitMQ
    ufw allow 15672/tcp # RabbitMQ Management
    ufw allow 9000/tcp # MinIO API
    ufw allow 9001/tcp # MinIO Console
    ufw --force enable
fi

# Création de l'utilisateur pour l'application
echo "Création de l'utilisateur samaconso..."
if ! id "samaconso" &>/dev/null; then
    useradd -m -s /bin/bash samaconso
    usermod -aG docker samaconso
else
    echo "L'utilisateur samaconso existe déjà"
fi

echo "=========================================="
echo "Installation terminée!"
echo "=========================================="
echo "Prochaines étapes:"
echo "1. Copier les fichiers de configuration dans /opt/samaconso"
echo "2. Créer le fichier .env avec les variables d'environnement"
echo "3. Exécuter: docker-compose -f docker-compose.db.yml up -d"
echo "=========================================="

