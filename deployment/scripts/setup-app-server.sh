#!/bin/bash
# Script d'installation pour SRV-MOBAPP1 et SRV-MOBAPP2
# Installation de Docker, Docker Compose et Nginx

set -e

# Paramètres
SERVER_NAME=${1:-SRV-MOBAPP1}
SERVER_IP=${2:-10.101.1.210}
DB_SERVER_IP=${3:-10.101.1.57}

echo "=========================================="
echo "Installation $SERVER_NAME ($SERVER_IP)"
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
    net-tools \
    nginx

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

# Configuration Nginx (seulement sur SRV-MOBAPP1 pour le load balancing)
if [ "$SERVER_NAME" = "SRV-MOBAPP1" ]; then
    echo "Configuration de Nginx pour le load balancing..."
    # La configuration Nginx sera copiée séparément
    systemctl enable nginx
fi

# Configuration du firewall
echo "Configuration du firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw allow 8000/tcp  # API FastAPI
    ufw allow 5555/tcp  # Flower (seulement SRV-MOBAPP1)
    ufw --force enable
fi

# Création des répertoires
echo "Création des répertoires..."
mkdir -p /opt/samaconso/{uploaded_files,logs}
chmod 755 /opt/samaconso
chmod 755 /opt/samaconso/{uploaded_files,logs}

# Création de l'utilisateur pour l'application
echo "Création de l'utilisateur samaconso..."
if ! id "samaconso" &>/dev/null; then
    useradd -m -s /bin/bash samaconso
    usermod -aG docker samaconso
    chown -R samaconso:samaconso /opt/samaconso
else
    echo "L'utilisateur samaconso existe déjà"
    chown -R samaconso:samaconso /opt/samaconso
fi

# Configuration des limites système
echo "Configuration des limites système..."
cat >> /etc/sysctl.conf << EOF
# Optimisations pour l'application
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
vm.swappiness = 10
EOF

sysctl -p

echo "=========================================="
echo "Installation terminée!"
echo "=========================================="
echo "Prochaines étapes:"
echo "1. Copier les fichiers de l'application dans /opt/samaconso"
echo "2. Construire l'image Docker: docker build -t samaconso_api:with-fixes ."
echo "3. Créer le fichier .env.production avec les variables d'environnement"
echo "4. Exécuter: docker-compose -f docker-compose.app.yml up -d"
if [ "$SERVER_NAME" = "SRV-MOBAPP1" ]; then
    echo "5. Configurer Nginx pour le load balancing"
fi
echo "=========================================="

