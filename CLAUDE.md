# SamaConso API — Guide de développement

## Vue d'ensemble

Backend FastAPI (v2.0.0) de l'application mobile **SamaConso** de la Senelec (Société Nationale d'Électricité du Sénégal). Permet aux clients de suivre leur consommation électrique, consulter leurs factures, recevoir des notifications et interagir avec les services Senelec.

**Branche principale :** `main` — **Branche de développement :** `dev`

---

## Stack technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Framework | FastAPI | 0.117.1 |
| ORM | SQLAlchemy | 2.0.44 |
| Migrations | Alembic | 1.17.0 |
| Validation | Pydantic | 2.11.9 |
| Serveur ASGI | Uvicorn + Gunicorn | 0.36.1 / 21.2.0 |
| Cache | Redis | 7.4.4 |
| File d'attente | Redis + Celery | 5.5.3 |
| Stockage fichiers | MinIO | 7.2.16 |
| Push notifications | Firebase Admin SDK | 7.1.0 |
| BDD principale | PostgreSQL | — |
| BDD métier | SQL Server (SIC + Postpaid) | — |
| Auth | JWT (HS256) + LDAP | PyJWT 2.10.1 |

---

## Structure du projet

```
app/
├── main.py               # Point d'entrée FastAPI, enregistrement des routers
├── config.py             # Variables d'environnement et configuration
├── database.py           # Connexions PostgreSQL + SQL Server (SIC, Postpaid, BI_ODS)
├── auth.py               # Logique JWT + OAuth2 + LDAP
├── cache.py              # Couche cache Redis
├── celery_app.py         # Configuration Celery (4 files de priorité)
├── firebase.py           # Intégration Firebase Cloud Messaging
├── rabbitmq.py           # Client AMQP async (aio-pika)
├── logging_config.py     # Système de logs centralisé
├── models/               # Modèles SQLAlchemy
├── routers/              # Endpoints FastAPI (1 fichier par domaine)
├── schemas/              # Schémas Pydantic (requêtes/réponses)
├── services/             # Logique métier
├── tasks/                # Tâches Celery asynchrones
└── middleware/           # RequestLoggingMiddleware, SecurityLoggingMiddleware
alembic/                  # Migrations de base de données
deployment/               # Guides et configs de déploiement production
docs/                     # Documentation et scripts utilitaires
```

---

## Modèles de données principaux

- **User** — Clients Senelec (login, phoneNumber, codePin, role_id, id_agence, ldap_flag)
- **UserSession** — Sessions actives avec FCM token par appareil
- **Compteur** — Compteurs électriques (numéro, type)
- **UserCompteur** — Association utilisateur ↔ compteur (est_proprietaire, est_active, tarif, id_client)
- **Notification** — Notifications push (type, titre, corps, is_read)
- **Demande** — Tickets/demandes clients
- **SeuilTarif** — Seuils de tarification électrique

---

## Authentification

Deux modes d'authentification coexistent :
1. **Login/password** via formulaire OAuth2 (`POST /auth/token`)
2. **Numéro de téléphone + code PIN** pour l'app mobile

**JWT** : access token (30 min) + refresh token (7 jours, hashé en BDD)
**LDAP** : authentification Active Directory via `ldaps://electricite.sn:636` (agents Senelec)

Dépendance FastAPI : `get_current_user()` dans `app/auth.py`

---

## Routers et préfixes d'URL

| Fichier router | Domaine |
|----------------|---------|
| `auth_routers.py` | `/auth/*` — Login, tokens |
| `user_routers.py` | `/user/*` — Gestion utilisateurs |
| `user_session_routers.py` | `/user-session/*` — Sessions, appareils |
| `user_compteur_routers.py` | `/user-compteur/*` — Associations user/compteur |
| `compteur_routers.py` | `/compteur/*` — Compteurs |
| `notification_routers.py` | `/notification/*` — Notifications FCM |
| `websocket_routers.py` | WebSocket — Notifications temps réel |
| `dashboard_routers.py` | `/dashboard/*` — Statistiques |
| `demande_routers.py` | `/demande/*` — Tickets clients |
| `sic_routers.py` | `/sic/*` — Intégration BDD SIC (SQL Server) |
| `postpaid_routers.py` | `/postpaid/*` — Facturation postpayée |
| `simulateur_routers.py` | `/simulateur/*` — Simulateur de consommation |
| `seuil_tarif_routers.py` | `/seuil-tarif/*` — Tarification |
| `agence_routers.py` | `/agence/*` — Agences Senelec |
| `upload_routers.py` | `/upload/*` — Téléversement fichiers (MinIO) |
| `logs_routers.py` | `/logs/*` — Diagnostics système |

---

## Connexions aux bases de données

```python
# PostgreSQL — BDD principale (app/database.py)
DATABASE_URL = "postgresql://user:password@host:5432/samaconso"

# SQL Server SIC — Données clients/compteurs
SIC_SERVER = "10.101.2.87"   # srv-asreports

# SQL Server Postpaid — Historique factures (HISTH2MC)
COMMERCIAL_SERVER = "10.101.3.243"   # srv-commercial

# SQL Server BI_ODS — Data warehouse
```

**Connexions SQL Server via pyodbc** — les drivers ODBC doivent être installés (inclus dans le Dockerfile).

---

## Cache Redis

Stratégie hiérarchique de TTL dans `app/config.py` :
- **2h** — Données de référence (types, rôles, agences)
- **1h** — Données quasi-statiques
- **15min** — Données modérément dynamiques
- **5min** — Données dynamiques
- **1min** — Données très dynamiques
- **30s** — APIs externes (SIC, Postpaid)

Pattern de clé : `{domaine}:{entité}:{id}` (ex: `user:profile:42`)

---

## Celery — Files de priorité

4 files configurées dans `app/celery_app.py` :
1. `urgent` — Notifications critiques
2. `high_priority` — Opérations importantes
3. `normal` — Traitement standard
4. `low_priority` — Tâches de fond

Broker : **Redis** | Backend résultat : **Redis**

> RabbitMQ a été retiré de l'architecture — Redis est utilisé à la fois comme broker Celery et comme backend de résultats. Voir BUG-003 dans `docs/ERREURS.md`.

---

## Endpoints de santé

```
GET  /               → Statut général
GET  /health         → Health check (load balancers)
GET  /health/redis   → Connectivité Redis
GET  /health/broker  → Connectivité broker Celery (Redis)
GET  /health/logs    → Système de logs
POST /test/logs      → Test de tous les niveaux de logs
```

---

## Démarrage local

```bash
# 1. Copier et configurer les variables d'environnement
cp .env.example .env

# 2. Démarrer les services dépendants
docker-compose up -d redis minio

# 3. Appliquer les migrations
alembic upgrade head

# 4. Lancer l'API en dev
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Documentation interactive
# http://localhost:8000/docs
```

---

## Docker Compose (développement)

```bash
docker-compose up -d          # Tous les services
docker-compose up -d api      # API uniquement
docker-compose logs -f api    # Logs de l'API
```

Services : `redis`, `minio` (:9000/:9001), `api` (:8000), `celery_worker`, `flower` (:5555)

---

## Architecture de déploiement production

| Serveur | IP | Rôle |
|---------|----|------|
| SRV-MOBAPPBD | 10.101.1.212 | PostgreSQL + MinIO node 1 |
| SRV-MOBAPP1 | 10.101.1.210 | API + Celery worker_high + Redis master + MinIO node 2 + Nginx |
| SRV-MOBAPP2 | 10.101.1.211 | API + Celery worker_low + Redis replica + MinIO node 3 + Nginx |
| VIP Keepalived | 10.101.1.250 | Failover haute disponibilité |

Nginx assure le reverse proxy et l'équilibrage de charge. Keepalived gère le basculement VRRP.

---

## Conventions de code

- **Langue des commentaires** : Français (aligné avec l'équipe)
- **Nommage** : snake_case pour les variables/fonctions, PascalCase pour les classes
- **Schémas** : toujours créer un schéma Pydantic dédié dans `app/schemas/` pour chaque entrée/sortie d'endpoint
- **Logs** : utiliser `get_logger("app.module")` — ne jamais utiliser `print()` en production
- **Cache** : invalider le cache lors de toute mutation (`CREATE`, `UPDATE`, `DELETE`)
- **Migrations** : toujours créer une migration Alembic pour les changements de schéma BDD
- **Sécurité** : ne jamais exposer les clés secrètes, tokens ou mots de passe dans les logs ou réponses API

---

## Variables d'environnement clés

```env
ENVIRONMENT=development|staging|production
DATABASE_URL=postgresql://...
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET_NAME=samaconso-uploads
MINIO_SECURE=false
LDAP_SERVER=ldaps://electricite.sn
LDAP_PORT=636
```

---

## Points d'attention

- **SSL désactivé** (`ssl._create_default_https_context = ssl._create_unverified_context`) dans `main.py` — nécessaire pour les connexions internes Senelec avec certificats legacy
- **CORS ouvert** (`allow_origins=["*"]`) — à restreindre pour la production
- **Connexions SQL Server** via IP fixes internes — non accessibles hors réseau Senelec
- **Firebase credentials** : fichier JSON de service account monté en volume dans Docker
- **Tests** : suite pytest dans `tests/` (unitaires + intégration) — SQLite en mémoire + mocks pour les services externes

---

## Erreurs connues et leçons apprises

Voir **[docs/ERREURS.md](docs/ERREURS.md)** — journal de tous les bugs rencontrés, leurs causes et les règles à appliquer pour ne pas les reproduire.

## Corrections de déploiement en attente

Voir **[docs/CORRECTIONS_DEPLOIEMENT.md](docs/CORRECTIONS_DEPLOIEMENT.md)** — liste détaillée des corrections à apporter sur `docker-compose.srv1.yml` et `docker-compose.srv2.yml` avant tout déploiement en production (MinIO, Celery queues, workers, health checks).

## Documentation complète du projet

Voir **[docs/DOCUMENTATION_COMPLETE.md](docs/DOCUMENTATION_COMPLETE.md)** — index de toute la documentation disponible : guides de démarrage, utilisation Docker, mise en production (3 parties), architecture, résolution de problèmes et scripts utilitaires.
