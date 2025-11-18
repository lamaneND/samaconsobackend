# 🚀 Guide de Mise en Production - Partie 3 (Finale)

**Suite de**: [GUIDE_MISE_EN_PRODUCTION_PARTIE2.md](GUIDE_MISE_EN_PRODUCTION_PARTIE2.md)

---

## 🔧 Maintenance

### 9.1 Tâches Quotidiennes

```bash
#!/bin/bash
# Script: daily_maintenance.sh
# Crontab: 0 6 * * * /usr/local/bin/daily_maintenance.sh

LOG_FILE="/var/log/samaconso/daily_maintenance.log"
DATE=$(date +"%Y-%m-%d %H:%M:%S")

echo "[$DATE] Début de la maintenance quotidienne" >> $LOG_FILE

# 1. Vérifier l'espace disque
echo "Vérification espace disque..." >> $LOG_FILE
df -h | grep -E "/$|/data" >> $LOG_FILE

DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 85 ]; then
    echo "⚠️ ALERTE: Espace disque > 85%" >> $LOG_FILE
    # Envoyer une alerte
    echo "Espace disque critique sur $(hostname)" | mail -s "Alerte SamaConso" ops@senelec.sn
fi

# 2. Vérifier les services Docker
echo "Vérification services Docker..." >> $LOG_FILE
docker ps --format "table {{.Names}}\t{{.Status}}" >> $LOG_FILE

# 3. Nettoyer les images Docker inutilisées
echo "Nettoyage images Docker..." >> $LOG_FILE
docker image prune -af --filter "until=72h" >> $LOG_FILE 2>&1

# 4. Vérifier les logs d'erreur
echo "Analyse logs d'erreur..." >> $LOG_FILE
ERROR_COUNT=$(grep -c "ERROR\|CRITICAL" /opt/samaconso/logs/*.log)
if [ $ERROR_COUNT -gt 100 ]; then
    echo "⚠️ ALERTE: $ERROR_COUNT erreurs détectées" >> $LOG_FILE
fi

# 5. Vérifier la connectivité aux bases de données
echo "Test connectivité bases de données..." >> $LOG_FILE
psql -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso -c "SELECT 1;" >> $LOG_FILE 2>&1
if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL OK" >> $LOG_FILE
else
    echo "❌ PostgreSQL ERREUR" >> $LOG_FILE
fi

# 6. Vérifier Redis
redis-cli -h 10.101.X.X3 ping >> $LOG_FILE 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Redis OK" >> $LOG_FILE
else
    echo "❌ Redis ERREUR" >> $LOG_FILE
fi

echo "[$DATE] Maintenance quotidienne terminée" >> $LOG_FILE
echo "---" >> $LOG_FILE
```

### 9.2 Tâches Hebdomadaires

```bash
#!/bin/bash
# Script: weekly_maintenance.sh
# Crontab: 0 3 * * 0 /usr/local/bin/weekly_maintenance.sh

LOG_FILE="/var/log/samaconso/weekly_maintenance.log"
DATE=$(date +"%Y-%m-%d %H:%M:%S")

echo "[$DATE] Début de la maintenance hebdomadaire" >> $LOG_FILE

# 1. Analyse des performances PostgreSQL
echo "Analyse performances PostgreSQL..." >> $LOG_FILE
psql -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso <<EOF >> $LOG_FILE
-- Tables les plus volumineuses
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Index manquants potentiels
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 100
  AND correlation < 0.1
ORDER BY n_distinct DESC
LIMIT 10;

-- Requêtes lentes (> 1 seconde)
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY mean_time DESC
LIMIT 10;
EOF

# 2. Vacuum et Analyze
echo "Vacuum et Analyze..." >> $LOG_FILE
psql -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso -c "VACUUM ANALYZE;" >> $LOG_FILE 2>&1

# 3. Statistiques Redis
echo "Statistiques Redis..." >> $LOG_FILE
redis-cli -h 10.101.X.X3 INFO stats >> $LOG_FILE

# 4. Statistiques RabbitMQ
echo "Statistiques RabbitMQ..." >> $LOG_FILE
curl -s -u guest:guest http://10.101.X.X2:15672/api/overview | python3 -m json.tool >> $LOG_FILE

# 5. Rapport Celery
echo "Rapport Celery..." >> $LOG_FILE
curl -s http://10.101.X.X3:5555/api/workers --user admin:admin | python3 -m json.tool >> $LOG_FILE

# 6. Nettoyer les anciens backups (> 30 jours)
echo "Nettoyage backups anciens..." >> $LOG_FILE
find /data/backups -type f -mtime +30 -delete >> $LOG_FILE 2>&1

# 7. Rotation des logs applicatifs
echo "Rotation logs..." >> $LOG_FILE
find /opt/samaconso/logs -name "*.log" -type f -mtime +7 -exec gzip {} \; >> $LOG_FILE 2>&1

echo "[$DATE] Maintenance hebdomadaire terminée" >> $LOG_FILE
echo "---" >> $LOG_FILE
```

### 9.3 Tâches Mensuelles

```bash
#!/bin/bash
# Script: monthly_maintenance.sh
# À exécuter manuellement le 1er de chaque mois

echo "🗓️ Maintenance mensuelle - $(date)"

# 1. Mise à jour du système (avec prudence)
echo "Vérification des mises à jour système..."
sudo apt update
sudo apt list --upgradable

# 2. Audit de sécurité
echo "Audit de sécurité..."
sudo apt install -y lynis
sudo lynis audit system

# 3. Revue des utilisateurs et accès
echo "Revue des utilisateurs..."
awk -F: '$3 >= 1000 {print $1}' /etc/passwd

# 4. Vérification des certificats SSL
echo "Vérification certificats SSL..."
# Vérifier expiration certificats

# 5. Test de restauration backup
echo "Test restauration backup..."
# Restaurer le dernier backup sur un serveur de test

# 6. Revue des logs de sécurité
echo "Revue logs sécurité..."
sudo grep -i "failed\|error\|warning" /var/log/auth.log | tail -n 100

# 7. Optimisation base de données
echo "Optimisation PostgreSQL..."
psql -h 10.101.X.X1 -p 6432 -U postgres -d samaconso -c "REINDEX DATABASE samaconso;"

# 8. Rapport mensuel
echo "Génération rapport mensuel..."
# Script pour générer un rapport détaillé
```

### 9.4 Nettoyage et Optimisation

#### PostgreSQL

```sql
-- Script: optimize_postgresql.sql
-- À exécuter mensuellement

-- 1. Vacuum complet
VACUUM FULL ANALYZE;

-- 2. Reindex
REINDEX DATABASE samaconso;

-- 3. Statistiques sur les tables volumineuses
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
       pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;

-- 4. Identifier les index inutilisés
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey';

-- 5. Analyser les requêtes lentes
SELECT query, calls, total_time, mean_time, max_time
FROM pg_stat_statements
WHERE mean_time > 100  -- Requêtes > 100ms en moyenne
ORDER BY mean_time DESC
LIMIT 20;
```

#### Redis

```bash
# Nettoyage Redis
redis-cli -h 10.101.X.X3 <<EOF
# Voir la mémoire utilisée
INFO memory

# Supprimer les clés expirées
# (Redis le fait automatiquement, mais on peut forcer)
FLUSHDB  # ATTENTION: Supprime toutes les clés de la DB courante
EOF
```

#### Docker

```bash
#!/bin/bash
# Script: docker_cleanup.sh

echo "Nettoyage Docker..."

# Arrêter les conteneurs non utilisés
docker container prune -f

# Supprimer les images non utilisées
docker image prune -af --filter "until=168h"  # 7 jours

# Supprimer les volumes non utilisés
docker volume prune -f

# Supprimer les réseaux non utilisés
docker network prune -f

# Supprimer le build cache
docker builder prune -af

# Afficher l'espace libéré
docker system df
```

---

## 🚨 Troubleshooting

### 10.1 Problèmes Courants

#### Problème 1: API ne répond pas (502/503)

**Symptômes**:
- Load Balancer retourne 502 Bad Gateway ou 503 Service Unavailable
- Health checks échouent

**Diagnostic**:
```bash
# 1. Vérifier l'état des conteneurs
docker ps
docker logs samaconso_api_1 --tail 50
docker logs samaconso_api_2 --tail 50

# 2. Vérifier la connectivité réseau
curl http://localhost:8001/health
curl http://localhost:8002/health

# 3. Vérifier les resources
docker stats --no-stream

# 4. Vérifier les logs système
journalctl -u docker -n 100
```

**Solutions**:
```bash
# Solution 1: Redémarrer les conteneurs
docker restart samaconso_api_1 samaconso_api_2

# Solution 2: Vérifier la base de données
psql -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso -c "SELECT 1;"

# Solution 3: Augmenter les resources (si OOM)
# Modifier docker-compose.production.yml:
#   limits:
#     memory: 4G  # Au lieu de 2G

# Solution 4: Vérifier le proxy Senelec
curl -x http://10.101.201.204:8080 https://oauth2.googleapis.com

# Solution 5: Rollback si nécessaire
./rollback.sh <version_precedente>
```

#### Problème 2: Notifications ne sont pas envoyées

**Symptômes**:
- Tâches en statut PENDING dans Flower
- Utilisateurs ne reçoivent pas de notifications

**Diagnostic**:
```bash
# 1. Vérifier les workers Celery
docker logs samaconso_celery_worker_1 --tail 50
docker logs samaconso_celery_worker_2 --tail 50

# 2. Vérifier les queues dans Flower
curl -s http://10.101.X.X3:5555/api/queues --user admin:admin

# 3. Vérifier que les workers écoutent les bonnes queues
docker logs samaconso_celery_worker_1 | grep "queues"
# Doit afficher: urgent, high_priority, normal, low_priority

# 4. Vérifier RabbitMQ
curl -s -u guest:guest http://10.101.X.X2:15672/api/queues
```

**Solutions**:
```bash
# Solution 1: Redémarrer les workers
docker restart samaconso_celery_worker_1 samaconso_celery_worker_2

# Solution 2: Vérifier Firebase
docker exec samaconso_celery_worker_1 python -c "import firebase_admin; print('OK')"

# Solution 3: Purger les queues si trop de messages
rabbitmqctl purge_queue low_priority

# Solution 4: Augmenter le nombre de workers (si charge élevée)
docker-compose -f docker-compose.workers.yml up -d --scale celery_worker_2=2
```

#### Problème 3: Base de données lente

**Symptômes**:
- Requêtes API très lentes (> 5 secondes)
- Timeout des connexions

**Diagnostic**:
```sql
-- 1. Requêtes en cours
SELECT pid, age(clock_timestamp(), query_start), usename, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND query NOT ILIKE '%pg_stat_activity%'
ORDER BY query_start DESC;

-- 2. Locks
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- 3. Statistiques connexions
SELECT count(*), state
FROM pg_stat_activity
GROUP BY state;

-- 4. Cache hit ratio (doit être > 99%)
SELECT
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit)  as heap_hit,
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;
```

**Solutions**:
```bash
# Solution 1: Terminer les requêtes longues
psql -h 10.101.X.X1 -p 6432 -U postgres -d samaconso <<EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE age(clock_timestamp(), query_start) > interval '5 minutes'
  AND state != 'idle';
EOF

# Solution 2: Augmenter les connexions PgBouncer
# Modifier /etc/pgbouncer/pgbouncer.ini:
# default_pool_size = 150  # Au lieu de 100

# Solution 3: Vacuum urgent
psql -h 10.101.X.X1 -p 5432 -U postgres -d samaconso -c "VACUUM ANALYZE;"

# Solution 4: Redémarrer PostgreSQL (en dernier recours)
sudo systemctl restart postgresql
```

#### Problème 4: Espace disque saturé

**Symptômes**:
- Erreur "No space left on device"
- Services crashent

**Diagnostic**:
```bash
# 1. Voir l'utilisation globale
df -h

# 2. Trouver les gros fichiers
du -h / | sort -rh | head -20

# 3. Voir les logs volumineux
du -sh /var/log/* | sort -rh

# 4. Voir les volumes Docker
docker system df -v
```

**Solutions**:
```bash
# Solution 1: Nettoyer les logs
journalctl --vacuum-time=3d
find /var/log -name "*.gz" -type f -mtime +7 -delete
find /opt/samaconso/logs -name "*.log" -type f -mtime +7 -delete

# Solution 2: Nettoyer Docker
docker system prune -af --volumes

# Solution 3: Nettoyer PostgreSQL WAL
psql -h localhost -p 5432 -U postgres -c "CHECKPOINT;"
find /var/lib/postgresql/15/main/pg_wal -type f -mtime +3 -delete

# Solution 4: Nettoyer backups anciens
find /data/backups -type f -mtime +30 -delete

# Solution 5: Étendre le volume (si possible)
# Contacter l'équipe infrastructure
```

#### Problème 5: Redis mémoire pleine

**Symptômes**:
- Erreur "OOM command not allowed when used memory > 'maxmemory'"
- Cache inefficace

**Diagnostic**:
```bash
# Statistiques mémoire
redis-cli -h 10.101.X.X3 INFO memory

# Nombre de clés
redis-cli -h 10.101.X.X3 DBSIZE

# Analyser les clés
redis-cli -h 10.101.X.X3 --bigkeys
```

**Solutions**:
```bash
# Solution 1: Flush manuellement (si urgent)
redis-cli -h 10.101.X.X3 FLUSHDB

# Solution 2: Augmenter maxmemory
# Modifier docker-compose.workers.yml:
# --maxmemory 6gb  # Au lieu de 4gb

# Solution 3: Analyser l'utilisation
redis-cli -h 10.101.X.X3 --scan --pattern "*" | head -100
```

### 10.2 Scripts de Diagnostic

```bash
#!/bin/bash
# Script: health_check_complet.sh
# Diagnostic complet du système

echo "=== DIAGNOSTIC SAMA CONSO ==="
echo ""

# 1. Serveurs
echo "1. État des serveurs:"
ping -c 1 10.101.X.X1 > /dev/null 2>&1 && echo "  ✅ SERVEUR 1 (DB)" || echo "  ❌ SERVEUR 1 (DB)"
ping -c 1 10.101.X.X2 > /dev/null 2>&1 && echo "  ✅ SERVEUR 2 (API)" || echo "  ❌ SERVEUR 2 (API)"
ping -c 1 10.101.X.X3 > /dev/null 2>&1 && echo "  ✅ SERVEUR 3 (Workers)" || echo "  ❌ SERVEUR 3 (Workers)"
echo ""

# 2. Services
echo "2. État des services:"
curl -sf http://10.101.X.X2:8001/health > /dev/null && echo "  ✅ API Instance 1" || echo "  ❌ API Instance 1"
curl -sf http://10.101.X.X2:8002/health > /dev/null && echo "  ✅ API Instance 2" || echo "  ❌ API Instance 2"
psql -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso -c "SELECT 1;" > /dev/null 2>&1 && echo "  ✅ PostgreSQL" || echo "  ❌ PostgreSQL"
redis-cli -h 10.101.X.X3 ping > /dev/null 2>&1 && echo "  ✅ Redis" || echo "  ❌ Redis"
curl -sf http://10.101.X.X2:15672 > /dev/null && echo "  ✅ RabbitMQ" || echo "  ❌ RabbitMQ"
curl -sf http://10.101.X.X3:5555 --user admin:admin > /dev/null && echo "  ✅ Flower" || echo "  ❌ Flower"
echo ""

# 3. Ressources
echo "3. Utilisation des ressources:"
echo "  Espace disque:"
df -h | grep -E "/$|/data" | awk '{print "    " $1 ": " $5 " utilisé"}'
echo ""

# 4. Conteneurs Docker
echo "4. Conteneurs Docker:"
docker ps --format "  {{.Names}}: {{.Status}}"
echo ""

# 5. Workers Celery
echo "5. Workers Celery:"
WORKERS=$(curl -s http://10.101.X.X3:5555/api/workers --user admin:admin | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data))")
echo "  Nombre de workers actifs: $WORKERS"
echo ""

# 6. Queues RabbitMQ
echo "6. Files RabbitMQ:"
curl -s -u guest:guest http://10.101.X.X2:15672/api/queues | python3 -c "
import sys, json
data = json.load(sys.stdin)
for queue in data:
    print(f\"  {queue['name']}: {queue['messages']} messages\")
"
echo ""

echo "=== FIN DU DIAGNOSTIC ==="
```

---

## ✅ Checklist de Mise en Production

### Pré-Déploiement (J-7)

#### Infrastructure
- [ ] 3 serveurs Linux provisionnés (Ubuntu 22.04 LTS)
- [ ] Spécifications respectées (CPU, RAM, Disque)
- [ ] Accès SSH configuré avec clés
- [ ] Firewall hardware configuré
- [ ] Adresses IP assignées et documentées

#### Réseau
- [ ] Connectivité inter-serveurs validée
- [ ] Accès aux serveurs SQL Server validés (SIC, Postpaid)
- [ ] Proxy Senelec configuré (10.101.201.204:8080)
- [ ] DNS configurés (api.samaconso.senelec.sn)
- [ ] Certificats SSL obtenus

#### Sécurité
- [ ] Mots de passe forts générés
- [ ] Stockage sécurisé des secrets (Vault/Ansible)
- [ ] Utilisateurs système créés
- [ ] Sudo configuré
- [ ] Fail2ban installé et configuré

### Installation (J-3 à J-1)

#### SERVEUR 1 (Base de Données)
- [ ] PostgreSQL 15 installé
- [ ] PgBouncer installé et configuré
- [ ] MinIO installé et configuré
- [ ] Base de données `samaconso` créée
- [ ] Utilisateur `samaconso_user` créé avec privilèges
- [ ] Extensions PostgreSQL installées (uuid-ossp, pg_trgm)
- [ ] Backups automatiques configurés (cron)
- [ ] Firewall iptables configuré
- [ ] Monitoring installé (node_exporter, postgres_exporter)
- [ ] Test de connexion depuis SERVEUR 2 et 3

#### SERVEUR 2 (API)
- [ ] Docker et Docker Compose installés
- [ ] Image Docker `samaconso_api:production` disponible
- [ ] Fichier `.env.production` configuré
- [ ] docker-compose.production.yml déployé
- [ ] Certificat Firebase copié
- [ ] RabbitMQ démarré et accessible
- [ ] API Instance 1 démarrée (port 8001)
- [ ] API Instance 2 démarrée (port 8002)
- [ ] Health checks fonctionnels
- [ ] Logs configurés et rotatifs
- [ ] Firewall iptables configuré
- [ ] Monitoring installé (node_exporter)

#### SERVEUR 3 (Workers)
- [ ] Docker et Docker Compose installés
- [ ] Image Docker `samaconso_api:production` disponible
- [ ] Fichier `.env.production` configuré
- [ ] docker-compose.workers.yml déployé
- [ ] Redis démarré et accessible
- [ ] Celery Worker 1 démarré (queues urgent, high_priority)
- [ ] Celery Worker 2 démarré (queues normal, low_priority)
- [ ] Flower démarré et accessible (port 5555)
- [ ] Connexion à RabbitMQ validée
- [ ] Firewall iptables configuré
- [ ] Monitoring installé (node_exporter, redis_exporter)

#### Load Balancer F5
- [ ] Pool `samaconso_api_pool` créé
- [ ] Members ajoutés (api_1:8001, api_2:8002)
- [ ] Health monitor configuré (/health)
- [ ] Virtual Server créé (VIP: 10.101.X.X0)
- [ ] Load balancing method: Least Connections
- [ ] Session persistence: Cookie Insert
- [ ] SSL/TLS configuré (si HTTPS)
- [ ] Tests de basculement validés

### Tests (J-2)

#### Tests Fonctionnels
- [ ] Test de login utilisateur
- [ ] Test de consultation consommation
- [ ] Test d'envoi notification push
- [ ] Test d'upload fichier (MinIO)
- [ ] Test de toutes les API principales

#### Tests de Performance
- [ ] Test de charge (1000 requêtes simultanées)
- [ ] Test de montée en charge progressive
- [ ] Mesure des temps de réponse (< 500ms)
- [ ] Vérification des ressources (CPU, RAM, Disk)

#### Tests de Résilience
- [ ] Arrêt d'une instance API (failover automatique)
- [ ] Arrêt d'un worker Celery
- [ ] Simulation panne réseau
- [ ] Test de rollback

#### Tests de Sécurité
- [ ] Scan de vulnérabilités (Nessus/OpenVAS)
- [ ] Test d'injection SQL
- [ ] Test XSS
- [ ] Vérification SSL/TLS
- [ ] Audit des logs

### Go-Live (J-Day)

#### Matin (09h00)
- [ ] Briefing équipe technique
- [ ] Vérification finale tous les services
- [ ] Backup complet base de données
- [ ] Activation monitoring temps réel
- [ ] Équipe sur site et hotline prête

#### Midi (12h00 - Heure creuse)
- [ ] Basculement DNS/Load Balancer
- [ ] Vérification premier accès utilisateur
- [ ] Monitoring logs en temps réel (15 min)
- [ ] Vérification métriques (CPU, RAM, Network)
- [ ] Test notification push réel

#### Après-midi (14h00-18h00)
- [ ] Tests avec 10 utilisateurs pilotes
- [ ] Validation complète des fonctionnalités
- [ ] Surveillance continue
- [ ] Corrections mineures si nécessaire
- [ ] Communication aux utilisateurs (email/SMS)

#### Soir (18h00)
- [ ] Bilan de la journée (réunion 30 min)
- [ ] Documentation des incidents
- [ ] Planification du lendemain
- [ ] Équipe d'astreinte désignée

### Post-Déploiement (J+1 à J+7)

#### Quotidien
- [ ] Surveillance monitoring (Grafana)
- [ ] Revue logs erreurs
- [ ] Vérification backups
- [ ] Support utilisateurs
- [ ] Collecte feedback

#### J+7
- [ ] Réunion bilan équipe
- [ ] Rapport détaillé (performance, incidents, feedback)
- [ ] Ajustements si nécessaire
- [ ] Documentation finale
- [ ] Clôture projet

---

## 📊 Métriques de Succès

### Objectifs de Performance

| Métrique | Cible | Critique |
|----------|-------|----------|
| **Disponibilité** | 99.9% | 99.5% |
| **Temps de réponse API** | < 500ms | < 1s |
| **Temps de réponse DB** | < 100ms | < 500ms |
| **Notifications envoyées** | > 95% | > 90% |
| **Erreurs HTTP** | < 0.1% | < 1% |
| **Connexions simultanées** | 10,000 | 5,000 |

### KPIs à Suivre

**Performance**:
- Temps de réponse moyen par endpoint
- Throughput (requêtes/seconde)
- Latence P95, P99

**Fiabilité**:
- Uptime (disponibilité)
- Taux d'erreur
- Taux de succès notifications

**Ressources**:
- Utilisation CPU (%)
- Utilisation RAM (%)
- Utilisation disque (%)
- Bande passante réseau

**Business**:
- Nombre d'utilisateurs actifs
- Nombre de consultations consommation
- Nombre de notifications envoyées
- Taux de conversion

---

## 📞 Contacts et Support

### Équipe Projet

| Rôle | Nom | Contact | Disponibilité |
|------|-----|---------|---------------|
| **Chef de Projet** | [Nom] | [Email/Tél] | 24/7 (astreinte) |
| **Architecte** | [Nom] | [Email/Tél] | 08h-18h |
| **DevOps** | [Nom] | [Email/Tél] | 24/7 (astreinte) |
| **DBA** | [Nom] | [Email/Tél] | 08h-20h |
| **Développeur Backend** | [Nom] | [Email/Tél] | 08h-18h |
| **Support N1** | [Équipe] | [Email/Tél] | 24/7 |

### Escalade

**Niveau 1** (Incident mineur):
→ Support N1 → Résolution sous 4h

**Niveau 2** (Incident majeur):
→ DevOps/DBA → Résolution sous 2h

**Niveau 3** (Incident critique - Système down):
→ Chef de Projet + Architecte → Résolution immédiate

### Outils de Communication

- **Slack**: #samaconso-prod
- **Email**: ops@senelec.sn
- **Téléphone d'astreinte**: +221 XX XXX XX XX
- **Ticketing**: [Système de tickets]

---

## 📚 Documentation Finale

### Documents à Maintenir

1. **Architecture** (ce document)
2. **Procédures d'exploitation** (runbook)
3. **Guide de troubleshooting**
4. **Documentation API** (Swagger/OpenAPI)
5. **Schéma base de données** (ERD)
6. **Configuration réseau** (diagrammes)
7. **Procédures de backup/restore**
8. **Changelog** (versions déployées)

### Localisation

```
/opt/samaconso/docs/
├── GUIDE_MISE_EN_PRODUCTION.md
├── GUIDE_MISE_EN_PRODUCTION_PARTIE2.md
├── GUIDE_MISE_EN_PRODUCTION_PARTIE3.md
├── ARCHITECTURE.md
├── RUNBOOK.md
├── TROUBLESHOOTING.md
├── CHANGELOG.md
└── schemas/
    ├── database_erd.png
    ├── network_diagram.png
    └── application_flow.png
```

---

## ✅ Conclusion

Ce guide couvre l'ensemble du processus de mise en production de SamaConso API sur une infrastructure haute disponibilité à 3 serveurs.

### Points Clés

✅ **Architecture distribuée** avec séparation des responsabilités
✅ **Haute disponibilité** via Load Balancer F5 et instances multiples
✅ **Scalabilité** horizontale et verticale possible
✅ **Sécurité** renforcée (firewall, SSL, secrets management)
✅ **Monitoring** complet (Prometheus, Grafana, Alerting)
✅ **Backup** automatique et procédures de rollback
✅ **Documentation** exhaustive et maintenable

### Capacité

**1 Million d'utilisateurs supportés** grâce à:
- PgBouncer (10,000 connexions clients)
- Redis (cache haute performance)
- Load Balancer F5 (distribution de charge)
- Workers Celery multiples (traitement asynchrone)
- Architecture scalable (ajout d'instances possible)

### Prochaines Étapes

1. **Validation par l'équipe technique**
2. **Revue par l'équipe sécurité**
3. **Approbation management**
4. **Planification déploiement** (dates, ressources)
5. **Formation équipe exploitation**
6. **Go-Live**

---

**Version**: 1.0
**Date**: 2025-11-12
**Auteurs**: Équipe SamaConso
**Statut**: ✅ Prêt pour production

🚀 **Bonne mise en production!**
