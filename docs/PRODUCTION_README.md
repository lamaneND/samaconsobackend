# 🚀 SamaConso API - Guide de Mise en Production

**Infrastructure**: 3 Serveurs Linux + Load Balancer F5
**Capacité**: 1 Million d'utilisateurs
**Haute Disponibilité**: 99.9%

---

## 📋 Documentation Complète

Ce guide est divisé en 3 parties pour faciliter la navigation:

### 📖 Partie 1: Architecture & Configuration Infrastructure
**[GUIDE_MISE_EN_PRODUCTION.md](GUIDE_MISE_EN_PRODUCTION.md)**

Contient:
1. Vue d'ensemble de l'architecture (3 serveurs)
2. Prérequis système et réseau
3. **SERVEUR 1**: Installation PostgreSQL + PgBouncer + MinIO
4. **SERVEUR 2**: Déploiement API (2 instances) + RabbitMQ
5. **SERVEUR 3**: Déploiement Workers Celery + Redis
6. Configuration Load Balancer F5

### 📖 Partie 2: Sécurité & Monitoring
**[GUIDE_MISE_EN_PRODUCTION_PARTIE2.md](GUIDE_MISE_EN_PRODUCTION_PARTIE2.md)**

Contient:
5. Sécurité (Firewall, SSH, Fail2Ban, SSL/TLS)
6. Monitoring & Logs (Prometheus, Grafana, ELK, Alerting)
7. Procédures de déploiement (Initial, Mises à jour, Maintenance)
8. Procédures de rollback

### 📖 Partie 3: Maintenance & Troubleshooting
**[GUIDE_MISE_EN_PRODUCTION_PARTIE3.md](GUIDE_MISE_EN_PRODUCTION_PARTIE3.md)**

Contient:
9. Maintenance (Quotidienne, Hebdomadaire, Mensuelle, Optimisation)
10. Troubleshooting (Problèmes courants et solutions)
11. ✅ **Checklist complète de mise en production**
12. Métriques de succès et KPIs
13. Contacts et support

---

## ⚡ Démarrage Rapide

### Étape 1: Préparation (J-7)

```bash
# Sur chaque serveur
sudo apt update && sudo apt upgrade -y
```

### Étape 2: Installation (J-3)

**SERVEUR 1**:
```bash
# PostgreSQL + PgBouncer + MinIO
bash /scripts/install_serveur1.sh
```

**SERVEUR 2**:
```bash
# Docker + API + RabbitMQ
cd /opt/samaconso
docker compose -f docker-compose.production.yml up -d
```

**SERVEUR 3**:
```bash
# Docker + Workers + Redis
cd /opt/samaconso
docker compose -f docker-compose.workers.yml up -d
```

### Étape 3: Vérification

```bash
# Script de diagnostic complet
bash /usr/local/bin/health_check_complet.sh
```

### Étape 4: Go-Live (J-Day)

1. Basculer le Load Balancer
2. Surveiller les logs
3. Valider avec utilisateurs pilotes

---

## 🏗️ Architecture Résumée

```
              Load Balancer F5 (10.101.X.X0)
                        |
        ┌───────────────┼───────────────┐
        |               |               |
   SERVEUR 1        SERVEUR 2       SERVEUR 3
   (Database)          (API)        (Workers)
        |               |               |
  ┌─────────┐    ┌──────────┐    ┌─────────┐
  │PostgreSQL│    │ API x2   │    │Workers  │
  │PgBouncer │    │RabbitMQ  │    │Redis    │
  │ MinIO   │    │          │    │Flower   │
  └─────────┘    └──────────┘    └─────────┘
```

### Répartition des Rôles

| Serveur | Composants | Rôle Principal |
|---------|-----------|----------------|
| **SERVEUR 1** | PostgreSQL + PgBouncer + MinIO | Données & Stockage |
| **SERVEUR 2** | 2x API + RabbitMQ | Traitement Requêtes |
| **SERVEUR 3** | 2x Workers + Redis + Flower | Tâches Asynchrones |

---

## 🔑 Informations Essentielles

### Ports Exposés

| Service | Serveur | Port | Accès |
|---------|---------|------|-------|
| **API 1** | SERVEUR 2 | 8001 | Load Balancer |
| **API 2** | SERVEUR 2 | 8002 | Load Balancer |
| **PostgreSQL (PgBouncer)** | SERVEUR 1 | 6432 | Interne |
| **MinIO API** | SERVEUR 1 | 9000 | Interne |
| **MinIO Console** | SERVEUR 1 | 9001 | Admin |
| **RabbitMQ AMQP** | SERVEUR 2 | 5672 | Interne |
| **RabbitMQ Management** | SERVEUR 2 | 15672 | Admin |
| **Redis** | SERVEUR 3 | 6379 | Interne |
| **Flower** | SERVEUR 3 | 5555 | Admin |

### Adresses IP (À définir)

```
SERVEUR 1 (DB):      10.101.X.X1
SERVEUR 2 (API):     10.101.X.X2
SERVEUR 3 (Workers): 10.101.X.X3
Load Balancer F5:    10.101.X.X0 (VIP)

Proxy Senelec:       10.101.201.204:8080
SQL Server SIC:      10.101.2.87
SQL Server Postpaid: 10.101.3.243
```

---

## 🔒 Sécurité

### Firewall

**Tous serveurs**:
- SSH (22) uniquement depuis réseau admin
- Ping (ICMP) autorisé
- Tout le reste bloqué par défaut

**Communication inter-serveurs**:
- SERVEUR 2 → SERVEUR 1 (ports 6432, 9000)
- SERVEUR 2 → SERVEUR 3 (port 6379)
- SERVEUR 3 → SERVEUR 2 (port 5672)

### Authentification

**SSH**: Clés uniquement (pas de mot de passe)
**PostgreSQL**: SCRAM-SHA-256
**API**: JWT tokens
**Services Management**: Basic Auth

### Secrets

**Ne JAMAIS commiter**:
- `.env.production`
- Mots de passe
- Clés API Firebase
- Certificats

**Utiliser**: Ansible Vault ou HashiCorp Vault

---

## 📊 Monitoring

### Prometheus + Grafana

**URL**: http://10.101.X.X3:3000

**Dashboards**:
- Vue d'ensemble système
- PostgreSQL
- Redis
- RabbitMQ
- Celery Workers
- API Performance

### Alerting

**Email**: ops@senelec.sn

**Alertes critiques**:
- API down (> 2 min)
- Database inaccessible
- Workers Celery down
- CPU > 90% (> 5 min)
- Disque > 90%

---

## 🔧 Commandes Utiles

### Vérification Santé

```bash
# Diagnostic complet
bash /usr/local/bin/health_check_complet.sh

# Services individuels
curl http://10.101.X.X2:8001/health
curl http://10.101.X.X2:8002/health
psql -h 10.101.X.X1 -p 6432 -U samaconso_user -d samaconso -c "SELECT 1;"
redis-cli -h 10.101.X.X3 ping
```

### Redémarrage Services

```bash
# SERVEUR 2 (API)
docker restart samaconso_api_1 samaconso_api_2

# SERVEUR 3 (Workers)
docker restart samaconso_celery_worker_1 samaconso_celery_worker_2
```

### Logs

```bash
# API
docker logs samaconso_api_1 -f --tail 100

# Workers
docker logs samaconso_celery_worker_1 -f --tail 100

# PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-*.log

# Système
journalctl -u docker -f
```

### Backup

```bash
# Manuel
pg_dump -h 10.101.X.X1 -p 6432 -U samaconso_user -F c -f backup_$(date +%Y%m%d).backup samaconso

# Automatique (via cron)
# Déjà configuré à 02h00 quotidiennement
```

---

## 🚨 Troubleshooting Rapide

### API ne répond pas
```bash
# Vérifier et redémarrer
docker ps
docker restart samaconso_api_1 samaconso_api_2
```

### Notifications non envoyées
```bash
# Vérifier workers et queues
docker logs samaconso_celery_worker_1
curl http://10.101.X.X3:5555 --user admin:admin
```

### Base de données lente
```bash
# Terminer requêtes longues
psql -h 10.101.X.X1 -p 6432 -U postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE age(clock_timestamp(), query_start) > interval '5 minutes';
"
```

### Espace disque plein
```bash
# Nettoyer
docker system prune -af
find /var/log -name "*.gz" -mtime +7 -delete
```

**Voir**: [GUIDE_MISE_EN_PRODUCTION_PARTIE3.md](GUIDE_MISE_EN_PRODUCTION_PARTIE3.md#troubleshooting) pour plus de détails

---

## ✅ Checklist Rapide

### Avant Go-Live

- [ ] 3 serveurs provisionnés et configurés
- [ ] PostgreSQL + PgBouncer installés (SERVEUR 1)
- [ ] MinIO installé (SERVEUR 1)
- [ ] 2 instances API déployées (SERVEUR 2)
- [ ] RabbitMQ démarré (SERVEUR 2)
- [ ] 2 workers Celery démarrés (SERVEUR 3)
- [ ] Redis démarré (SERVEUR 3)
- [ ] Load Balancer F5 configuré
- [ ] Firewall configuré sur tous les serveurs
- [ ] Monitoring actif (Prometheus + Grafana)
- [ ] Alerting configuré
- [ ] Backups automatiques configurés
- [ ] Tests de bout en bout validés
- [ ] Équipe sur site et en astreinte

**Checklist complète**: [GUIDE_MISE_EN_PRODUCTION_PARTIE3.md](GUIDE_MISE_EN_PRODUCTION_PARTIE3.md#checklist-de-mise-en-production)

---

## 📞 Support

### Contacts

| Rôle | Contact |
|------|---------|
| **Chef de Projet** | [Nom] - [Tél] |
| **DevOps** | [Nom] - [Tél] |
| **DBA** | [Nom] - [Tél] |
| **Support 24/7** | ops@senelec.sn |

### Escalade

1. **Incident mineur** → Support N1 (4h)
2. **Incident majeur** → DevOps/DBA (2h)
3. **Incident critique** → Chef Projet + Équipe (immédiat)

---

## 📚 Documentation Complète

| Document | Description |
|----------|-------------|
| **[GUIDE_MISE_EN_PRODUCTION.md](GUIDE_MISE_EN_PRODUCTION.md)** | Architecture & Infrastructure |
| **[GUIDE_MISE_EN_PRODUCTION_PARTIE2.md](GUIDE_MISE_EN_PRODUCTION_PARTIE2.md)** | Sécurité & Monitoring |
| **[GUIDE_MISE_EN_PRODUCTION_PARTIE3.md](GUIDE_MISE_EN_PRODUCTION_PARTIE3.md)** | Maintenance & Troubleshooting |
| **[PRODUCTION_README.md](PRODUCTION_README.md)** | Ce document (résumé) |

---

## 🎯 Métriques de Succès

| Métrique | Cible |
|----------|-------|
| **Disponibilité** | 99.9% |
| **Temps de réponse API** | < 500ms |
| **Notifications envoyées** | > 95% |
| **Erreurs HTTP** | < 0.1% |
| **Connexions simultanées** | 10,000 |

---

## 🎉 Conclusion

Cette documentation couvre l'ensemble du processus de mise en production de SamaConso API sur une infrastructure professionnelle haute disponibilité.

**Capacité**: 1 Million d'utilisateurs
**Architecture**: Distribuée sur 3 serveurs + Load Balancer
**Fiabilité**: 99.9% de disponibilité
**Sécurité**: Renforcée (firewall, SSL, monitoring)
**Scalabilité**: Horizontale et verticale possible

---

**Version**: 1.0
**Date**: 2025-11-12
**Statut**: ✅ Prêt pour production

🚀 **Bonne mise en production!**
