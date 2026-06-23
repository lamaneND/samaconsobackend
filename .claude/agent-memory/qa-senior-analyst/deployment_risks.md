---
name: Risques déploiement SamaConso production
description: Risques spécifiques à l'architecture 2-serveurs SRV-MOBAPP1/SRV-MOBAPP2 avec Redis master/replica, Celery, MinIO, Nginx/Keepalived
type: project
---

## Architecture cible
- SRV-MOBAPP1 (10.101.1.210) : Redis MASTER, worker_high (urgent + high_priority)
- SRV-MOBAPP2 (10.101.1.211) : Redis REPLICA (lecture seule), worker_low (normal + low_priority)
- SRV-MOBAPPBD (10.101.1.212) : PostgreSQL + MinIO
- VIP Keepalived : 10.101.1.250

## Risque CRITIQUE — Redis Replica comme broker Celery
- `worker_low` sur SRV2 pointe vers Redis MASTER sur SRV1 (`redis://10.101.1.210:6379/0`)
- La REPLICA sur SRV2 est en lecture seule → Celery ne peut pas publier via la replica
- Correct dans la config actuelle : tous les services (API + workers des deux serveurs) pointent vers le MASTER 10.101.1.210
- **Mais** : si SRV1 tombe, le broker Celery tombe aussi (pas de promotion automatique de la replica)
- La replica Redis ne sert que de sauvegarde des données, pas de failover automatique broker

## Risque CRITIQUE — SPOF Redis Master
- Pas de Redis Sentinel ni de Redis Cluster dans la config actuelle
- Keepalived gère le VIP de l'API (failover HTTP) mais PAS le failover Redis
- Si SRV1 (Redis Master) tombe : toutes les requêtes API des 2 serveurs perdent le cache + le broker Celery
- La replica sur SRV2 contient les données mais ne peut pas promouvoir automatiquement

## Risque IMPORTANT — Dépendance `depends_on` sur redis_replica (SRV2)
- L'API sur SRV2 démarre seulement si `redis_replica` est healthy
- Or `redis_replica` fait un ping OK même si la réplication depuis SRV1 n'est pas encore établie
- L'API peut démarrer avec une replica non synchronisée → cache vide ou données périmées
- Le health check ne vérifie pas `REPLICATION_STATUS` (slave) ni `master_link_status:up`

## Risque IMPORTANT — Aucun health check sur l'API dans les compose production
- `docker-compose.srv1.yml` et `docker-compose.srv2.yml` n'ont pas de `healthcheck` sur le service `api`
- Contrairement à `docker-compose.yml` (dev) qui a un health check `curl localhost:8000/`
- En cas de crash silencieux de l'API, Docker ne sait pas que le container est mort → pas de restart automatique si `restart: unless-stopped` ne suffit pas

## Risque IMPORTANT — Fichier Firebase non vérifié au démarrage
- Le volume `./app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json` est monté en `:ro`
- Si le fichier est absent sur le serveur au moment du `docker-compose up`, le container démarre quand même (volume bind mount, pas de vérification)
- Les notifications FCM échoueront silencieusement à l'exécution des tâches Celery

## Risque MINEUR — Nginx rate limiting trop permissif
- `nginx.conf` : `rate=100r/s` par IP, `burst=20`
- Pour une API mobile bancaire, 100 req/s par IP est élevé → risque de scraping ou brute force PIN
- `limit_conn conn_limit 10` : 10 connexions simultanées par IP, acceptable

## Risque MINEUR — Nginx proxy_read_timeout 60s vs Gunicorn timeout 120s
- Gunicorn configuré avec `--timeout 120`
- Nginx `proxy_read_timeout 60s` → Nginx peut couper la connexion avant que Gunicorn termine
- Pour les requêtes SQL Server longues (SIC/Postpaid), un timeout Nginx peut masquer une réponse valide tardive

## Pattern récurrent — `.env.production` non couvert par .gitignore
- `.gitignore` couvre `.env.*` globalement (ligne 109)
- Exception explicite `deployment_by_copilot/app_servers/.env.production` (ligne 111) → suggère qu'un autre dossier `deployment/app_servers/` pourrait ne pas être couvert
- Vérifier qu'aucun fichier `.env.production` ne traîne dans le dossier `deployment/app_servers/` commité par erreur
