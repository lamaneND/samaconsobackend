---
name: Patterns de défauts récurrents SamaConso
description: Bugs et anti-patterns découverts en code review et tests sur le projet SamaConso
type: project
---

## BUG-001 — Mauvais schéma Pydantic, champs silencieusement ignorés
- `UserLoginSchema` vs `UserLoginRequestSchema` sur `/auth/token-json`
- `device_model` et `fcm_token` étaient toujours `None` en base → notifications push impossibles
- Signal d'alarme : `getattr(pydantic_obj, 'champ', None)` = champ absent du schéma
- **Règle** : vérifier que le schéma couvre TOUS les champs envoyés par le client mobile

## BUG-002 — `Base.metadata.create_all(engine)` au niveau module
- S'exécutait à chaque import Gunicorn → crash worker si BDD indisponible au boot
- **Règle** : aucun effet de bord réseau au niveau module dans un fichier importé par FastAPI/Gunicorn

## BUG-003 — RabbitMQ broker Celery inutile + Redis déjà présent
- Cookie Erlang absent → cluster RabbitMQ ne se formait pas
- Redis suffisant pour 4 queues prioritaires Celery sans routing complexe
- **Règle** : éviter les services additionnels si Redis couvre le besoin

## Résidu post-correction — celery_app.py commentaires obsolètes
- Les commentaires dans `app/celery_app.py` mentionnent encore "RabbitMQ" alors que Redis est le broker
- `broker_heartbeat=30` et `broker_pool_limit=10` sont des paramètres RabbitMQ-natifs, potentiellement ignorés ou mal interprétés avec Redis comme broker

## Risque résiduel — CORR-003 partiellement appliquée
- Les workers ont bien `extra_hosts` et `environment` (REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND)
- Mais `DATABASE_URL` absent du bloc `environment:` des workers (présent uniquement en commentaire)
- Dépend entièrement de `.env.production` pour la BDD → point de défaillance silencieux si le fichier est incomplet

## Risque résiduel — CORR-007 partiellement appliquée
- `DATABASE_URL` retiré du bloc `environment:` des compose files (correct)
- Mais `CORRECTIONS_DEPLOIEMENT.md` contient encore le mot de passe `S3N3l3c2025!` en clair (ligne 103 et 122) → fichier de documentation dans le repo Git
- `.gitignore` protège `deployment_by_copilot/app_servers/.env.production` mais PAS `deployment/app_servers/.env.production`
