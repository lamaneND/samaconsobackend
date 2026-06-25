#!/bin/bash
# =============================================================================
#  Déploiement SamaConso — SRV-MOBAPP2 (10.101.1.211)
#  Rôles : Redis REPLICA, API (9 workers), Celery worker_low (toutes queues)
#
#  PRÉREQUIS : SRV-MOBAPP1 doit être déployé et Redis Master actif.
#
#  Usage : sudo bash deploy_srv2.sh <IP_MACHINE_DEV> [PORT_HTTP]
#  Ex.   : sudo bash deploy_srv2.sh 10.101.1.50 8888
# =============================================================================
set -e

DEV_IP="${1:?Usage : $0 <IP_machine_dev> [port]}"
DEV_PORT="${2:-8888}"
BASE_URL="http://${DEV_IP}:${DEV_PORT}"
DEPLOY_DIR="/opt/samaconsobackend"
FIREBASE_FILE="samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json"
REDIS_MASTER_IP="10.101.1.210"

# ─── Couleurs ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERREUR]${NC} $*"; exit 1; }
step() { echo -e "\n${YELLOW}[$1/8]${NC} $2"; }

echo ""
echo "============================================================"
echo "  Déploiement SamaConso — SRV-MOBAPP2 (10.101.1.211)"
echo "  Redis Replica | API | Celery worker_low (toutes queues)"
echo "  Source : ${BASE_URL}"
echo "============================================================"
echo ""

# ─── Vérifications préalables ─────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || err "Docker non installé."
command -v wget   >/dev/null 2>&1 || err "wget non disponible."
command -v curl   >/dev/null 2>&1 || err "curl non disponible."

wget -q --spider "${BASE_URL}/samaconso_api.tar" 2>/dev/null \
  || err "Impossible de joindre ${BASE_URL} — vérifiez que 'python -m http.server ${DEV_PORT}' tourne sur la machine dev."

echo "   Vérification de Redis Master sur SRV1 (${REDIS_MASTER_IP}:6379)..."
if curl -sf --connect-timeout 3 "http://${REDIS_MASTER_IP}:8000/health/redis" >/dev/null 2>&1; then
  ok "SRV1 accessible et Redis Master actif."
else
  warn "Impossible de joindre SRV1 — assurez-vous que SRV1 est déployé avant de continuer."
fi

# ─── [1/8] Répertoires ────────────────────────────────────────────────────────

step 1 "Création des répertoires..."
mkdir -p "${DEPLOY_DIR}/logs" "${DEPLOY_DIR}/uploaded_files" "${DEPLOY_DIR}/app"
chown -R 1000:1000 "${DEPLOY_DIR}/logs" "${DEPLOY_DIR}/uploaded_files"
ok "Répertoires créés : ${DEPLOY_DIR}/{logs,uploaded_files,app}"

# ─── [2/8] Fichier Firebase ───────────────────────────────────────────────────

step 2 "Vérification du fichier Firebase credentials..."
if [ ! -f "${DEPLOY_DIR}/app/${FIREBASE_FILE}" ]; then
  warn "Fichier Firebase absent — téléchargement depuis la machine dev..."
  wget -q --show-progress "${BASE_URL}/${FIREBASE_FILE}" \
    -O "${DEPLOY_DIR}/app/${FIREBASE_FILE}" \
    || err "Impossible de télécharger le fichier Firebase. Déposez-le manuellement dans ${DEPLOY_DIR}/app/ et relancez."
fi
ok "Firebase credentials présent."

# ─── [3/8] Téléchargement des images Docker ───────────────────────────────────

step 3 "Téléchargement des images Docker depuis ${BASE_URL}..."
cd /tmp

echo "   → samaconso_api.tar"
wget -q --show-progress "${BASE_URL}/samaconso_api.tar" -O /tmp/samaconso_api.tar

echo "   → redis_7_alpine.tar"
wget -q --show-progress "${BASE_URL}/redis_7_alpine.tar" -O /tmp/redis_7_alpine.tar

ok "Téléchargements terminés."

# ─── [4/8] Chargement des images Docker ──────────────────────────────────────

step 4 "Chargement des images Docker..."
docker load -i /tmp/samaconso_api.tar  && ok "samaconso_api:latest chargée."
docker load -i /tmp/redis_7_alpine.tar && ok "redis:7-alpine chargée."
rm -f /tmp/samaconso_api.tar /tmp/redis_7_alpine.tar

# ─── [5/8] Fichier d'environnement ───────────────────────────────────────────

step 5 "Création du fichier .env.production..."
cat > "${DEPLOY_DIR}/.env.production" << 'ENVEOF'
# SRV-MOBAPP2 — généré par deploy_srv2.sh
SERVER_NAME=SRV-MOBAPP2
ENVIRONMENT=production

# JWT
SECRET_KEY=$3?N2LEC123
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# PostgreSQL (SRV-MOBAPPBD via PgBouncer)
DATABASE_URL=postgresql://samaconso_app:S3N3l3c2025!@10.101.1.212:6432/samaconso

# LDAP
LDAP_SEARCH_PASSWORD=!!=++PT25@--ZmA

# Redis — replica locale pour le cache lecture, Master SRV1 pour le broker Celery
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

# Celery (broker toujours sur le Master SRV1)
CELERY_BROKER_URL=redis://10.101.1.210:6379/0
CELERY_RESULT_BACKEND=redis://10.101.1.210:6379/0

# MinIO (SRV-MOBAPPBD)
MINIO_ENDPOINT=10.101.1.212:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_NAME=samaconso-uploads

# Firebase
FIREBASE_CREDENTIALS_PATH=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json
GOOGLE_APPLICATION_CREDENTIALS=/app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json

# Logs
LOG_LEVEL=info
ENVEOF

chmod 600 "${DEPLOY_DIR}/.env.production"
ok "Fichier .env.production créé (permissions 600)."

# ─── [6/8] Arrêt des anciens conteneurs ──────────────────────────────────────

step 6 "Arrêt des anciens conteneurs..."
for c in samaconso_api samaconso_worker_low samaconso_redis_replica; do
  if docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
    docker stop "${c}" 2>/dev/null && docker rm "${c}" 2>/dev/null
    ok "Conteneur ${c} supprimé."
  else
    warn "Conteneur ${c} absent — ignoré."
  fi
done

# ─── Fonction wait_healthy ────────────────────────────────────────────────────

wait_healthy() {
  local container="$1" max="${2:-30}" interval="${3:-3}"
  echo "   Attente du health check de ${container}..."
  for i in $(seq 1 "${max}"); do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "${container}" 2>/dev/null || echo "none")
    case "${STATUS}" in
      healthy) ok "${container} est sain."; return 0 ;;
      none)    warn "${container} sans health check — on continue."; return 0 ;;
      *)       echo "   (${i}/${max}) ${STATUS}..." ;;
    esac
    sleep "${interval}"
  done
  err "${container} non sain après $((max * interval))s."
}

# ─── [7/8] Démarrage des conteneurs ──────────────────────────────────────────

step 7 "Démarrage des conteneurs..."

echo ""
echo "   → Redis Replica de ${REDIS_MASTER_IP}:6379 (port 6379 local)"
docker run -d \
  --name samaconso_redis_replica \
  --restart always \
  -p 6379:6379 \
  -v samaconso_redis_data:/data \
  --health-cmd="redis-cli ping" \
  --health-interval=10s \
  --health-timeout=5s \
  --health-retries=5 \
  redis:7-alpine \
  redis-server \
    --replicaof "${REDIS_MASTER_IP}" 6379 \
    --replica-announce-ip 10.101.1.211 \
    --replica-read-only yes

wait_healthy samaconso_redis_replica 30 3

echo ""
echo "   Vérification de la réplication Redis..."
sleep 3
REPL_ROLE=$(docker exec samaconso_redis_replica redis-cli info replication 2>/dev/null | grep "role:" || echo "inconnu")
echo "   ${REPL_ROLE}"
echo "${REPL_ROLE}" | grep -q "role:slave" \
  && ok "Réplication active vers ${REDIS_MASTER_IP}." \
  || warn "Réplication non confirmée — elle se synchronisera dès que SRV1 sera joignable."

echo ""
echo "   → API Gunicorn (9 workers, port 8000)"
docker run -d \
  --name samaconso_api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file "${DEPLOY_DIR}/.env.production" \
  -v "${DEPLOY_DIR}/logs:/app/logs" \
  -v "${DEPLOY_DIR}/uploaded_files:/app/uploaded_files" \
  -v "${DEPLOY_DIR}/app/${FIREBASE_FILE}:/app/app/${FIREBASE_FILE}:ro" \
  --add-host srv-mobappbd:10.101.1.212 \
  --add-host srv-mobapp1:10.101.1.210 \
  --add-host srv-asreports:10.101.2.87 \
  --add-host srv-commercial:10.101.3.243 \
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --health-start-period=60s \
  samaconso_api:latest \
  gunicorn -w 9 -k uvicorn.workers.UvicornWorker app.main:app \
    --bind 0.0.0.0:8000 --timeout 120

echo ""
echo "   → Celery worker_low (toutes queues : urgent, high_priority, normal, low_priority)"
docker run -d \
  --name samaconso_worker_low \
  --restart unless-stopped \
  --env-file "${DEPLOY_DIR}/.env.production" \
  --add-host srv-mobappbd:10.101.1.212 \
  --add-host srv-mobapp1:10.101.1.210 \
  --add-host srv-asreports:10.101.2.87 \
  --add-host srv-commercial:10.101.3.243 \
  samaconso_api:latest \
  celery -A app.celery_app worker --loglevel=info --concurrency=4 \
    -Q urgent,high_priority,normal,low_priority -n worker_low@%h

# ─── [8/8] Vérification finale ────────────────────────────────────────────────

step 8 "Vérification du déploiement..."
sleep 5

echo ""
echo "--- Conteneurs actifs ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=samaconso"

echo ""
echo "--- Health checks ---"
curl -sf http://localhost:8000/health       && ok "GET /health → OK"       || warn "API pas encore prête."
curl -sf http://localhost:8000/health/redis && ok "GET /health/redis → OK" || warn "Redis non accessible depuis l'API."

echo ""
echo "--- Statut réplication Redis ---"
docker exec samaconso_redis_replica redis-cli info replication 2>/dev/null \
  | grep -E "role:|master_host:|master_link_status:" || warn "Redis non accessible."

echo ""
echo "============================================================"
echo "  SRV-MOBAPP2 déployé avec succès"
echo ""
echo "  API    : http://10.101.1.211:8000"
echo "  Docs   : http://10.101.1.211:8000/docs"
echo "  Health : http://10.101.1.211:8000/health"
echo ""
echo "  VIP Keepalived : http://10.101.1.250"
echo "  Flower (Celery): http://10.101.1.210:5555"
echo "============================================================"
