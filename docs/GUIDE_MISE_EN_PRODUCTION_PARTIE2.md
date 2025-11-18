# 🚀 Guide de Mise en Production - Partie 2

**Suite de**: [GUIDE_MISE_EN_PRODUCTION.md](GUIDE_MISE_EN_PRODUCTION.md)

---

## 🔐 Sécurité

### 5.1 Firewall (iptables)

#### SERVEUR 1 (Base de Données)

```bash
#!/bin/bash
# Fichier: /usr/local/bin/firewall_serveur1.sh

# Réinitialiser
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

# Politique par défaut: DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Autoriser loopback
iptables -A INPUT -i lo -j ACCEPT

# Autoriser connexions établies
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# SSH (depuis réseau admin uniquement)
iptables -A INPUT -p tcp --dport 22 -s 10.101.0.0/16 -j ACCEPT

# PostgreSQL via PgBouncer (depuis SERVEUR 2 et 3)
iptables -A INPUT -p tcp --dport 6432 -s 10.101.X.X2 -j ACCEPT
iptables -A INPUT -p tcp --dport 6432 -s 10.101.X.X3 -j ACCEPT

# MinIO (depuis SERVEUR 2 et 3)
iptables -A INPUT -p tcp --dport 9000 -s 10.101.X.X2 -j ACCEPT
iptables -A INPUT -p tcp --dport 9000 -s 10.101.X.X3 -j ACCEPT

# MinIO Console (depuis réseau admin uniquement)
iptables -A INPUT -p tcp --dport 9001 -s 10.101.0.0/16 -j ACCEPT

# Ping (ICMP)
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT

# Sauvegarder les règles
iptables-save > /etc/iptables/rules.v4

echo "Firewall SERVEUR 1 configuré"
```

#### SERVEUR 2 (API)

```bash
#!/bin/bash
# Fichier: /usr/local/bin/firewall_serveur2.sh

# Réinitialiser
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

# Politique par défaut: DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Autoriser loopback
iptables -A INPUT -i lo -j ACCEPT

# Autoriser connexions établies
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# SSH (depuis réseau admin uniquement)
iptables -A INPUT -p tcp --dport 22 -s 10.101.0.0/16 -j ACCEPT

# API port 8001 (depuis Load Balancer)
iptables -A INPUT -p tcp --dport 8001 -s 10.101.X.X0 -j ACCEPT

# API port 8002 (depuis Load Balancer)
iptables -A INPUT -p tcp --dport 8002 -s 10.101.X.X0 -j ACCEPT

# RabbitMQ AMQP (depuis SERVEUR 3)
iptables -A INPUT -p tcp --dport 5672 -s 10.101.X.X3 -j ACCEPT

# RabbitMQ Management (depuis réseau admin uniquement)
iptables -A INPUT -p tcp --dport 15672 -s 10.101.0.0/16 -j ACCEPT

# Ping (ICMP)
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT

# Sauvegarder les règles
iptables-save > /etc/iptables/rules.v4

echo "Firewall SERVEUR 2 configuré"
```

#### SERVEUR 3 (Workers)

```bash
#!/bin/bash
# Fichier: /usr/local/bin/firewall_serveur3.sh

# Réinitialiser
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

# Politique par défaut: DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Autoriser loopback
iptables -A INPUT -i lo -j ACCEPT

# Autoriser connexions établies
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# SSH (depuis réseau admin uniquement)
iptables -A INPUT -p tcp --dport 22 -s 10.101.0.0/16 -j ACCEPT

# Redis (depuis SERVEUR 2)
iptables -A INPUT -p tcp --dport 6379 -s 10.101.X.X2 -j ACCEPT

# Flower (depuis réseau admin uniquement)
iptables -A INPUT -p tcp --dport 5555 -s 10.101.0.0/16 -j ACCEPT

# Ping (ICMP)
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT

# Sauvegarder les règles
iptables-save > /etc/iptables/rules.v4

echo "Firewall SERVEUR 3 configuré"
```

**Rendre persistant**:
```bash
# Sur tous les serveurs
sudo apt install -y iptables-persistent
sudo systemctl enable netfilter-persistent
```

### 5.2 Sécurisation SSH

**Fichier**: `/etc/ssh/sshd_config` (tous serveurs)

```
# Désactiver root login
PermitRootLogin no

# Utiliser uniquement les clés SSH
PasswordAuthentication no
PubkeyAuthentication yes

# Limiter les tentatives
MaxAuthTries 3
MaxSessions 5

# Timeout
ClientAliveInterval 300
ClientAliveCountMax 2

# Désactiver les fonctionnalités dangereuses
X11Forwarding no
PermitEmptyPasswords no
PermitUserEnvironment no

# Logging
SyslogFacility AUTH
LogLevel INFO
```

**Appliquer**:
```bash
sudo systemctl restart sshd
```

### 5.3 Fail2Ban

```bash
# Installation (tous serveurs)
sudo apt install -y fail2ban

# Configuration
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
```

**Fichier**: `/etc/fail2ban/jail.local`

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
destemail = admin@senelec.sn
sendername = Fail2Ban

[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log
maxretry = 3
```

**Démarrer**:
```bash
sudo systemctl start fail2ban
sudo systemctl enable fail2ban
```

### 5.4 Secrets Management

**Ne JAMAIS commiter**:
- `.env.production`
- Mots de passe
- Clés API
- Certificats Firebase

**Utiliser**: Ansible Vault ou HashiCorp Vault pour gérer les secrets en production.

### 5.5 SSL/TLS pour Communications Internes

#### Générer des Certificats Auto-signés

```bash
#!/bin/bash
# Script: generate_certs.sh

# Créer une CA
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 3650 -key ca-key.pem -sha256 -out ca.pem -subj "/CN=SamaConso CA"

# Générer certificat pour chaque serveur
for server in serveur1 serveur2 serveur3; do
    openssl genrsa -out ${server}-key.pem 4096
    openssl req -subj "/CN=${server}" -sha256 -new -key ${server}-key.pem -out ${server}.csr
    openssl x509 -req -days 3650 -sha256 -in ${server}.csr -CA ca.pem -CAkey ca-key.pem \
        -CAcreateserial -out ${server}-cert.pem
done
```

---

## 📊 Monitoring & Logs

### 6.1 Prometheus & Grafana (Optionnel mais Recommandé)

#### Installation sur SERVEUR 3

**Docker Compose** pour monitoring:

```yaml
# Fichier: docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    restart: unless-stopped
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=VOTRE_MOT_DE_PASSE
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    networks:
      - monitoring

  node_exporter:
    image: prom/node-exporter:latest
    container_name: node_exporter
    ports:
      - "9100:9100"
    restart: unless-stopped
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:

networks:
  monitoring:
    driver: bridge
```

**Configuration Prometheus**: `prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Node Exporter (métriques système)
  - job_name: 'node_exporter'
    static_configs:
      - targets:
          - '10.101.X.X1:9100'  # SERVEUR 1
          - '10.101.X.X2:9100'  # SERVEUR 2
          - '10.101.X.X3:9100'  # SERVEUR 3

  # API instances
  - job_name: 'samaconso_api'
    metrics_path: '/metrics'
    static_configs:
      - targets:
          - '10.101.X.X2:8001'
          - '10.101.X.X2:8002'

  # PostgreSQL Exporter
  - job_name: 'postgresql'
    static_configs:
      - targets: ['10.101.X.X1:9187']

  # Redis Exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['10.101.X.X3:9121']

  # RabbitMQ
  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['10.101.X.X2:15692']
```

### 6.2 Centralization des Logs (ELK Stack)

**Alternative Simple**: Utiliser Loki + Promtail

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  loki:
    image: grafana/loki:latest
    container_name: loki
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    volumes:
      - /var/log:/var/log:ro
      - /opt/samaconso/logs:/app/logs:ro
      - ./promtail-config.yml:/etc/promtail/config.yml:ro
    restart: unless-stopped

volumes:
  loki_data:
```

### 6.3 Alerting

**Fichier**: `alertmanager.yml`

```yaml
route:
  receiver: 'email'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'email'
    email_configs:
      - to: 'ops@senelec.sn'
        from: 'alerts@samaconso.senelec.sn'
        smarthost: 'smtp.senelec.sn:587'
        auth_username: 'alerts@samaconso.senelec.sn'
        auth_password: 'MOT_DE_PASSE'
        headers:
          Subject: '🚨 Alerte SamaConso: {{ .GroupLabels.alertname }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

**Règles d'alerte**: `alert.rules.yml`

```yaml
groups:
  - name: samaconso_alerts
    interval: 30s
    rules:
      # API down
      - alert: APIDown
        expr: up{job="samaconso_api"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Instance API {{ $labels.instance }} down"
          description: "L'API {{ $labels.instance }} est inaccessible depuis 2 minutes"

      # High CPU
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CPU élevé sur {{ $labels.instance }}"
          description: "CPU à {{ $value }}% sur {{ $labels.instance }}"

      # High Memory
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Mémoire élevée sur {{ $labels.instance }}"
          description: "Mémoire à {{ $value }}% sur {{ $labels.instance }}"

      # Database connections
      - alert: HighDatabaseConnections
        expr: pg_stat_activity_count > 180
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Nombre élevé de connexions PostgreSQL"
          description: "{{ $value }} connexions actives (max 200)"

      # RabbitMQ queue size
      - alert: LargeRabbitMQQueue
        expr: rabbitmq_queue_messages > 10000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "File RabbitMQ {{ $labels.queue }} volumineuse"
          description: "{{ $value }} messages en attente"

      # Celery workers down
      - alert: CeleryWorkersDown
        expr: celery_workers == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Aucun worker Celery actif"
          description: "Les tâches asynchrones ne seront pas traitées"
```

### 6.4 Health Checks

**Endpoint API**: `/health`

```python
# À ajouter dans app/main.py
from fastapi import APIRouter
import redis
import psycopg2

health_router = APIRouter()

@health_router.get("/health")
async def health_check():
    """
    Health check endpoint pour le Load Balancer
    """
    checks = {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check PostgreSQL
    try:
        conn = get_db_connection_samaconso()
        if conn:
            conn.close()
            checks["services"]["database"] = "ok"
        else:
            checks["services"]["database"] = "error"
    except Exception as e:
        checks["services"]["database"] = "error"
        checks["status"] = "degraded"

    # Check Redis
    try:
        r = redis.Redis.from_url(REDIS_URL)
        r.ping()
        checks["services"]["redis"] = "ok"
    except Exception:
        checks["services"]["redis"] = "error"
        checks["status"] = "degraded"

    # Check RabbitMQ (via Celery)
    try:
        celery_app.connection().ensure_connection(max_retries=1)
        checks["services"]["rabbitmq"] = "ok"
    except Exception:
        checks["services"]["rabbitmq"] = "error"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "running" else 503
    return JSONResponse(content=checks, status_code=status_code)
```

### 6.5 Log Rotation

**Fichier**: `/etc/logrotate.d/samaconso`

```
/opt/samaconso/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        docker kill -s USR1 samaconso_api_1 samaconso_api_2
    endscript
}
```

---

## 🚀 Procédures de Déploiement

### 7.1 Déploiement Initial (Premier déploiement)

#### Phase 1: Préparation (J-7)

**Checklist**:
- [ ] Serveurs provisionnés et configurés
- [ ] Accès réseau validés
- [ ] Certificats SSL obtenus
- [ ] DNS configurés
- [ ] Load Balancer F5 configuré
- [ ] Mots de passe générés et stockés de manière sécurisée
- [ ] Backups planifiés

#### Phase 2: Installation Infrastructure (J-3)

**SERVEUR 1**:
```bash
# 1. Installation PostgreSQL
sudo bash /scripts/install_postgresql.sh

# 2. Configuration PgBouncer
sudo bash /scripts/configure_pgbouncer.sh

# 3. Installation MinIO
sudo bash /scripts/install_minio.sh

# 4. Création base de données
sudo bash /scripts/create_database.sh

# 5. Migration données (si nécessaire)
# Restaurer depuis backup ou importer données initiales

# 6. Configurer firewall
sudo bash /usr/local/bin/firewall_serveur1.sh

# 7. Vérifier
psql -h localhost -p 6432 -U samaconso_user samaconso -c "SELECT version();"
curl http://localhost:9000/minio/health/live
```

**SERVEUR 2**:
```bash
# 1. Installation Docker
sudo bash /scripts/install_docker.sh

# 2. Déployer l'application
cd /opt/samaconso
docker compose -f docker-compose.production.yml up -d

# 3. Vérifier
docker ps
curl http://localhost:8001/health
curl http://localhost:8002/health

# 4. Configurer firewall
sudo bash /usr/local/bin/firewall_serveur2.sh
```

**SERVEUR 3**:
```bash
# 1. Installation Docker
sudo bash /scripts/install_docker.sh

# 2. Déployer workers et Redis
cd /opt/samaconso
docker compose -f docker-compose.workers.yml up -d

# 3. Vérifier
docker ps
docker logs samaconso_celery_worker_1
docker logs samaconso_celery_worker_2

# 4. Vérifier Flower
curl http://localhost:5555

# 5. Configurer firewall
sudo bash /usr/local/bin/firewall_serveur3.sh
```

#### Phase 3: Tests (J-2)

```bash
# 1. Test de bout en bout
curl -X POST http://10.101.X.X0/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'

# 2. Test notification
curl -X POST http://10.101.X.X0/notifications/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"user_id": 1, "title": "Test", "body": "Test notification"}'

# 3. Test charge (optionnel)
# Utiliser Apache Bench ou Locust
ab -n 1000 -c 100 http://10.101.X.X0/health
```

#### Phase 4: Go Live (J-Day)

**Matin**:
1. Vérification finale de tous les services
2. Backup complet de la base de données
3. Activer monitoring et alerting
4. Équipe sur site et en attente

**Midi** (heure creuse):
1. Basculer le DNS/Load Balancer vers la nouvelle infrastructure
2. Surveiller les logs en temps réel
3. Valider les métriques

**Après-midi**:
1. Tests avec utilisateurs pilotes
2. Monitoring continu
3. Corrections si nécessaire

**Soir**:
1. Bilan de la journée
2. Documentation des incidents
3. Planification du lendemain

### 7.2 Déploiement de Mises à Jour

#### Strategy: Blue-Green Deployment

**Principe**: Garder l'ancienne version en running pendant le déploiement de la nouvelle.

```bash
#!/bin/bash
# Script: deploy_update.sh

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: ./deploy_update.sh <version>"
    exit 1
fi

echo "🚀 Déploiement de la version $VERSION"

# 1. Pull la nouvelle image
docker pull samaconso_api:$VERSION

# 2. Tag comme production
docker tag samaconso_api:$VERSION samaconso_api:production-new

# 3. Mettre à jour api_2 (50% du trafic)
echo "📦 Mise à jour de api_2..."
docker stop samaconso_api_2
docker rm samaconso_api_2
docker compose -f docker-compose.production.yml up -d api_2

# 4. Attendre et vérifier
sleep 30
if curl -f http://localhost:8002/health; then
    echo "✅ api_2 OK"
else
    echo "❌ api_2 FAILED - Rollback"
    # Rollback api_2
    docker tag samaconso_api:production-old samaconso_api:production
    docker compose -f docker-compose.production.yml up -d api_2
    exit 1
fi

# 5. Mettre à jour api_1
echo "📦 Mise à jour de api_1..."
docker stop samaconso_api_1
docker rm samaconso_api_1
docker compose -f docker-compose.production.yml up -d api_1

# 6. Attendre et vérifier
sleep 30
if curl -f http://localhost:8001/health; then
    echo "✅ api_1 OK"
else
    echo "❌ api_1 FAILED - Rollback"
    # Rollback api_1
    docker tag samaconso_api:production-old samaconso_api:production
    docker compose -f docker-compose.production.yml up -d api_1
    exit 1
fi

# 7. Tag final
docker tag samaconso_api:production-new samaconso_api:production
docker rmi samaconso_api:production-old

echo "✅ Déploiement terminé avec succès"
```

**Utilisation**:
```bash
# Déployer la version 2.1.0
sudo bash /opt/samaconso/scripts/deploy_update.sh 2.1.0
```

### 7.3 Maintenance Programmée

**Fenêtre de maintenance**: Dimanche 02h00 - 06h00

```bash
#!/bin/bash
# Script: maintenance_window.sh

echo "🔧 Début de la maintenance programmée"

# 1. Activer le mode maintenance sur le Load Balancer
# (Rediriger vers une page de maintenance)

# 2. Attendre que les requêtes en cours se terminent
sleep 60

# 3. Sauvegarder la base de données
pg_dump -h 10.101.X.X1 -p 6432 -U samaconso_user -F c -f /backups/pre_maintenance_$(date +%Y%m%d).backup samaconso

# 4. Effectuer les opérations de maintenance
# - Migrations base de données
# - Mises à jour système
# - Nettoyage des logs
# - Optimisations

# 5. Redémarrer les services si nécessaire
docker compose -f /opt/samaconso/docker-compose.production.yml restart

# 6. Vérifications
curl http://localhost:8001/health
curl http://localhost:8002/health

# 7. Désactiver le mode maintenance
# (Réactiver le trafic sur le Load Balancer)

echo "✅ Maintenance terminée"
```

---

## ⏮️ Procédures de Rollback

### 8.1 Rollback Application

```bash
#!/bin/bash
# Script: rollback.sh

PREVIOUS_VERSION=$1

if [ -z "$PREVIOUS_VERSION" ]; then
    echo "Usage: ./rollback.sh <version_precedente>"
    exit 1
fi

echo "⏮️ Rollback vers version $PREVIOUS_VERSION"

# 1. Vérifier que l'image existe
if ! docker image inspect samaconso_api:$PREVIOUS_VERSION > /dev/null 2>&1; then
    echo "❌ Image samaconso_api:$PREVIOUS_VERSION introuvable"
    exit 1
fi

# 2. Tag comme production
docker tag samaconso_api:$PREVIOUS_VERSION samaconso_api:production

# 3. Redémarrer les conteneurs
docker compose -f /opt/samaconso/docker-compose.production.yml down
docker compose -f /opt/samaconso/docker-compose.production.yml up -d

# 4. Vérifier
sleep 30
if curl -f http://localhost:8001/health && curl -f http://localhost:8002/health; then
    echo "✅ Rollback réussi"
else
    echo "❌ Rollback échoué - intervention manuelle requise"
    exit 1
fi
```

### 8.2 Rollback Base de Données

```bash
#!/bin/bash
# Script: rollback_database.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./rollback_database.sh <fichier_backup>"
    exit 1
fi

echo "⏮️ Rollback base de données depuis $BACKUP_FILE"

# 1. Arrêter les applications
docker compose -f /opt/samaconso/docker-compose.production.yml stop api_1 api_2
docker compose -f /opt/samaconso/docker-compose.workers.yml stop celery_worker_1 celery_worker_2

# 2. Terminer les connexions actives
psql -h 10.101.X.X1 -p 6432 -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'samaconso' AND pid <> pg_backend_pid();"

# 3. Drop et recréer la base
psql -h 10.101.X.X1 -p 6432 -U postgres <<EOF
DROP DATABASE samaconso;
CREATE DATABASE samaconso OWNER samaconso_user;
EOF

# 4. Restaurer le backup
pg_restore -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso -v $BACKUP_FILE

# 5. Redémarrer les applications
docker compose -f /opt/samaconso/docker-compose.production.yml start api_1 api_2
docker compose -f /opt/samaconso/docker-compose.workers.yml start celery_worker_1 celery_worker_2

echo "✅ Rollback base de données terminé"
```

---

**(Fin de la Partie 2)**

**La suite avec Maintenance, Troubleshooting et Checklist finale sera dans la Partie 3.**

Voulez-vous que je continue?