---
name: Patterns d'analyse QA SamaConso
description: Approches et cas de test qui révèlent des défauts spécifiques à SamaConso
type: project
---

## Pattern 1 — Toujours lire le fichier config.py en intégralité
- Des secrets en dur (SECRET_KEY, LDAP_SEARCH_PASSWORD) y cohabitent avec les variables d'environnement
- Les valeurs par défaut `os.getenv("X", "valeur_par_defaut")` révèlent les vraies valeurs en production si les env vars ne sont pas injectées

## Pattern 2 — Vérifier la cohérence entre les fichiers docker-compose et CORRECTIONS_DEPLOIEMENT.md
- Les corrections listées dans CORRECTIONS_DEPLOIEMENT.md peuvent elles-mêmes introduire des secrets en clair (CORR-003 ligne 103)
- Toujours relire les docs après correction pour détecter les fuites résiduelles

## Pattern 3 — Toujours comparer les noms de queues Celery entre celery_app.py et docker-compose
- Les noms de queues définis dans `task_routes` doivent correspondre EXACTEMENT aux `-Q` des commandes workers
- Un nom de queue incorrect → tâches jamais consommées sans erreur visible

## Pattern 4 — Vérifier la direction de lecture Redis dans une config master/replica
- Redis replica est en lecture seule → broker Celery NE PEUT PAS être la replica
- Tous les services (API + workers des deux serveurs) doivent pointer vers le MASTER pour les écritures
- La distinction cache (lecture replica OK) vs broker (écriture → master obligatoire) est souvent manquée

## Pattern 5 — Vérifier que depends_on ne donne pas une fausse confiance
- `depends_on: condition: service_healthy` vérifie que `redis-cli ping` retourne PONG
- Cela ne garantit pas que la réplication Redis est établie, ni que la BDD PostgreSQL est accessible
- Pour les workers Celery, le health check Redis ne suffit pas si la BDD est indisponible

## Pattern 6 — Vérifier les commentaires obsolètes dans le code applicatif
- Après migration RabbitMQ → Redis, `celery_app.py` garde des commentaires "RabbitMQ" et des paramètres RabbitMQ-natifs
- Ces commentaires créent de la confusion pour l'équipe et peuvent masquer des paramètres mal adaptés

## Pattern 7 — Chercher les endpoints sans authentification dans les routers utils
- `/utils/*` contiennent souvent des endpoints de debug non protégés
- Toujours vérifier `Depends(get_current_user)` absent = endpoint public
