# 🚀 SamaConso API

API de notification pour la gestion de consommation électrique Senelec.

---

## ⚡ Démarrage Rapide (30 secondes)

```bash
# 1. Démarrer
docker-compose -f docker-compose.fixed.yml up -d

# 2. Vérifier
check_health.bat
```

**C'est tout!** L'application est maintenant accessible sur http://localhost:8000

---

## 📚 Documentation

**📋 Vue d'Ensemble Complète**: [DOCUMENTATION_COMPLETE.md](DOCUMENTATION_COMPLETE.md) - Toute la documentation en un coup d'œil

### 🎯 Pour Commencer
- **[QUICKSTART.md](QUICKSTART.md)** - Démarrage en 30 secondes
- **[README_DOCKER.md](README_DOCKER.md)** - Guide essentiel (5 min)

### 📖 Pour Comprendre
- **[RECAPITULATIF_FINAL.md](RECAPITULATIF_FINAL.md)** - Vue d'ensemble complète
- **[PROBLEMES_RESOLUS_FINAL.md](PROBLEMES_RESOLUS_FINAL.md)** - Historique des solutions

### 🔧 Pour Utiliser
- **[GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md)** - Guide complet avec toutes les commandes
- **[INDEX_DOCUMENTATION.md](INDEX_DOCUMENTATION.md)** - Navigation dans la documentation

### 🆘 Pour Résoudre des Problèmes
- **[FIX_CELERY_QUEUES.md](FIX_CELERY_QUEUES.md)** - Fix notifications non reçues
- **[FIREBASE_PROXY_SENELEC.md](FIREBASE_PROXY_SENELEC.md)** - Fix Firebase avec proxy
- **[DEPLOIEMENT_AVEC_PROXY.md](DEPLOIEMENT_AVEC_PROXY.md)** - Configuration proxy Senelec

### 🚀 Pour la Production
- **[PRODUCTION_README.md](PRODUCTION_README.md)** - Guide de mise en production (Vue d'ensemble)
- **[INDEX_PRODUCTION.md](INDEX_PRODUCTION.md)** - Navigation complète de la documentation production
- **[GUIDE_MISE_EN_PRODUCTION.md](GUIDE_MISE_EN_PRODUCTION.md)** - Partie 1: Infrastructure & Installation
- **[GUIDE_MISE_EN_PRODUCTION_PARTIE2.md](GUIDE_MISE_EN_PRODUCTION_PARTIE2.md)** - Partie 2: Sécurité & Monitoring
- **[GUIDE_MISE_EN_PRODUCTION_PARTIE3.md](GUIDE_MISE_EN_PRODUCTION_PARTIE3.md)** - Partie 3: Maintenance & Troubleshooting
- **[ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)** - Diagrammes & Spécifications

---

## 🎯 Fonctionnalités

- ✅ **API FastAPI** - API REST moderne et performante
- ✅ **Notifications Push Firebase** - Envoi de notifications aux utilisateurs
- ✅ **Traitement Asynchrone Celery** - Gestion des tâches en arrière-plan
- ✅ **Multi-Queues Prioritaires** - urgent, high_priority, normal, low_priority
- ✅ **Connexions SQL Server** - SIC et Postpaid
- ✅ **Cache Redis** - Performance optimale
- ✅ **Message Broker RabbitMQ** - Gestion des files de messages
- ✅ **Stockage MinIO** - Stockage de fichiers S3-compatible
- ✅ **Monitoring Flower** - Surveillance des tâches Celery

---

## 🌐 Services

| Service | URL | Identifiants |
|---------|-----|--------------|
| **API Documentation** | http://localhost:8000/docs | - |
| **Flower (Celery)** | http://localhost:5555 | admin / admin |
| **RabbitMQ Management** | http://localhost:15672 | guest / guest |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |

---

## 🧪 Tests

### Test de Santé
```bash
check_health.bat
```

### Test de Notification
```bash
send_test_notification.bat 9
```
(Remplacez `9` par votre user_id)

### Test API
```bash
curl http://localhost:8000
```

---

## 🛠️ Configuration

### Réseau Senelec
- **Proxy**: 10.101.201.204:8080
- **SQL SIC**: 10.101.2.87 (srv-asreports)
- **SQL Postpaid**: 10.101.3.243 (srv-commercial)

### Ports Exposés
```
8000  → API FastAPI
5555  → Flower (Monitoring Celery)
5672  → RabbitMQ AMQP
15672 → RabbitMQ Management
9000  → MinIO API
9001  → MinIO Console
6379  → Redis
```

---

## 📊 Architecture

```
┌─────────────┐
│   Client    │
│  (Mobile)   │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────────────┐
│         API FastAPI (Port 8000)         │
│  ┌───────────┐  ┌──────────────────┐  │
│  │  Routers  │  │  Notifications   │  │
│  └───────────┘  └──────────────────┘  │
└────┬──────────────────┬─────────────┬──┘
     │                  │             │
     ↓                  ↓             ↓
┌─────────┐      ┌──────────┐   ┌────────┐
│ SQL     │      │ Firebase │   │ Celery │
│ Server  │      │   FCM    │   │ Worker │
└─────────┘      └──────────┘   └───┬────┘
                                     │
                    ┌────────────────┼────────────┐
                    ↓                ↓            ↓
              ┌─────────┐     ┌──────────┐  ┌────────┐
              │  Redis  │     │ RabbitMQ │  │ MinIO  │
              │ (Cache) │     │ (Broker) │  │ (S3)   │
              └─────────┘     └──────────┘  └────────┘
```

---

## 🔧 Commandes Essentielles

### Démarrer
```bash
docker-compose -f docker-compose.fixed.yml up -d
```

### Arrêter
```bash
docker-compose -f docker-compose.fixed.yml down
```

### Voir les Logs
```bash
# API
docker logs samaconso_api -f

# Worker Celery
docker logs samaconso_celery_worker -f

# Tous
docker-compose -f docker-compose.fixed.yml logs -f
```

### Redémarrer un Service
```bash
docker-compose -f docker-compose.fixed.yml restart api
docker-compose -f docker-compose.fixed.yml restart celery_worker
```

---

## 📋 Prérequis

- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **Accès réseau Senelec** (proxy configuré)
- **Connexion aux serveurs SQL Server** (SIC et Postpaid)

---

## ✅ État du Système

- ✅ **API FastAPI** - Opérationnelle
- ✅ **SQL Server SIC** - Connecté (10.101.2.87)
- ✅ **SQL Server Postpaid** - Connecté (10.101.3.243)
- ✅ **Firebase Push** - Fonctionnel (notifications envoyées et reçues)
- ✅ **Celery Workers** - 4 queues actives
- ✅ **Infrastructure** - Redis, RabbitMQ, MinIO opérationnels
- ✅ **Proxy Senelec** - Configuré et fonctionnel

---

## 🎓 Parcours d'Apprentissage

### Niveau 1: Débutant (15 minutes)
1. Lire [QUICKSTART.md](QUICKSTART.md)
2. Exécuter `check_health.bat`
3. Tester les interfaces web

### Niveau 2: Utilisateur (45 minutes)
1. Lire [README_DOCKER.md](README_DOCKER.md)
2. Envoyer une notification test
3. Consulter les logs

### Niveau 3: Administrateur (2 heures)
1. Lire [GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md)
2. Comprendre l'architecture
3. Maîtriser le troubleshooting

---

## 🆘 Support

### Problèmes Fréquents
- **Notifications non reçues** → [FIX_CELERY_QUEUES.md](FIX_CELERY_QUEUES.md)
- **Erreur SSL Firebase** → [FIREBASE_PROXY_SENELEC.md](FIREBASE_PROXY_SENELEC.md)
- **SQL Server non accessible** → [GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md#résolution-de-problèmes)

### Documentation Complète
Voir [INDEX_DOCUMENTATION.md](INDEX_DOCUMENTATION.md) pour toute la documentation disponible.

---

## 📝 Changelog

### Version 2.0.0 (2025-11-12)
- ✅ Dockerisation complète de l'application
- ✅ Résolution problème SQL Server (drivers ODBC)
- ✅ Résolution problème Firebase (SSL avec proxy Senelec)
- ✅ Résolution problème Celery (configuration multi-queues)
- ✅ Notifications push fonctionnelles (testées et confirmées)
- ✅ Documentation complète et nettoyée
- ✅ Scripts d'utilisation (check_health, send_test_notification)

---

## 📄 Licence

Propriétaire - Senelec

---

## 👥 Équipe

Développement et maintenance par l'équipe IT Senelec

---

**Version**: 2.0.0
**Statut**: ✅ Production Ready
**Dernière mise à jour**: 2025-11-12

**Prêt pour la production !** 🚀
