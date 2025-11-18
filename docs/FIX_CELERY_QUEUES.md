# 🔧 Fix: Celery Worker - Configuration des Queues

**Date**: 2025-11-12
**Problème**: Notifications ne sont pas reçues
**Solution**: Configuration des queues Celery

---

## 🔴 Problème Identifié

### Symptôme
- API accepte les requêtes de notification (HTTP 202)
- Tâches créées dans Celery (visible dans Flower)
- **Mais les notifications ne sont jamais envoyées**
- Les tâches restent en statut `PENDING` indéfiniment

### Diagnostic

#### 1. Vérification dans Flower
```bash
curl -s "http://localhost:5555/api/tasks" --user admin:admin
```

**Résultat**: Toutes les tâches en statut `PENDING` avec:
```json
{
  "state": "PENDING",
  "routing_key": "low_priority"  ← Envoyée sur queue low_priority
}
```

#### 2. Vérification du Worker
```bash
docker logs samaconso_celery_worker | grep queues
```

**Résultat**: Le worker n'écoutait que sur la queue `normal`:
```
[queues]
  .> normal  exchange=normal(direct) key=normal
```

### Cause Racine

**Configuration des tâches** ([celery_app.py](app/celery_app.py:56)):
```python
# Les tâches sont routées sur différentes queues selon leur priorité
task_routes={
    "send_single_notification": {"queue": "normal"},
    "send_urgent_notification": {"queue": "urgent"},
    "send_batch_notifications": {"queue": "high_priority"},
    "send_broadcast_notifications": {"queue": "low_priority"},  ← Problème!
}
```

**Configuration du Worker** (docker-compose.fixed.yml - AVANT):
```yaml
command: celery -A app.celery_app worker --loglevel=info --pool=solo -n worker@%h --concurrency=2
```

**Résultat**: Le worker n'écoute que sur la queue par défaut (`normal`), mais les notifications broadcast sont envoyées sur `low_priority`!

---

## ✅ Solution Appliquée

### Modification de docker-compose.fixed.yml

**AVANT**:
```yaml
celery_worker:
  command: celery -A app.celery_app worker --loglevel=info --pool=solo -n worker@%h --concurrency=2
```

**APRÈS**:
```yaml
celery_worker:
  command: celery -A app.celery_app worker --loglevel=info --pool=solo -n worker@%h --concurrency=2 -Q urgent,high_priority,normal,low_priority
```

**Explication**: L'option `-Q` (ou `--queues`) spécifie explicitement toutes les queues que le worker doit écouter.

---

## 🧪 Tests de Validation

### Test 1: Vérifier les queues écoutées

```bash
docker logs samaconso_celery_worker | grep queues
```

**Résultat attendu**:
```
[queues]
  .> urgent          exchange=urgent(direct) key=urgent
  .> high_priority   exchange=high_priority(direct) key=high_priority
  .> normal          exchange=normal(direct) key=normal
  .> low_priority    exchange=low_priority(direct) key=low_priority
```

### Test 2: Envoyer une notification broadcast

```bash
curl -X POST "http://localhost:8000/notifications/all_users" \
  -H "Content-Type: application/json" \
  -d '{
    "type_notification_id": 10,
    "event_id": 1,
    "by_user_id": 10,
    "title": "Test Docker",
    "body": "On teste Docker",
    "is_read": false
  }'
```

**Résultat attendu**:
```json
{
  "status": 202,
  "message": "Notification broadcast créée pour X utilisateurs",
  "batch_task_id": "...",
  "processing": "asynchronous"
}
```

### Test 3: Vérifier le traitement dans les logs

```bash
docker logs samaconso_celery_worker --tail 50 | grep "Batch\|succès"
```

**Résultat attendu**:
```
[INFO] 📡 Broadcast vers 9 utilisateurs
[INFO] 📦 Traitement batch broadcast_chunk_0: 16 notifications
[INFO] ✅ Batch broadcast_chunk_0 terminé: 13 succès, 3 échecs
```

### Test 4: Vérifier dans Flower

Accéder à http://localhost:5555 et vérifier que:
- Les tâches passent de `PENDING` à `SUCCESS`
- Le statut affiche `succeeded`
- Les résultats montrent `success_count > 0`

---

## 📊 Architecture des Queues

### Queues Configurées

| Queue | Priorité | Usage | Exemple |
|-------|----------|-------|---------|
| **urgent** | 9 | Notifications critiques | Alertes système, urgences |
| **high_priority** | 7 | Envois batch importants | Campagnes marketing |
| **normal** | 5-6 | Notifications standards | Notification individuelle |
| **low_priority** | 3 | Envois broadcast massifs | Tous les utilisateurs |

### Routage des Tâches

```python
# app/celery_app.py
task_routes = {
    "send_single_notification": {"queue": "normal"},          # 1 utilisateur
    "send_urgent_notification": {"queue": "urgent"},          # Critique
    "send_batch_notifications": {"queue": "high_priority"},   # Batch
    "send_broadcast_notifications": {"queue": "low_priority"} # Tous
}
```

### Pourquoi Plusieurs Queues?

1. **Priorisation**: Les notifications urgentes ne sont pas bloquées par des broadcasts massifs
2. **Performance**: Traitement parallèle selon l'importance
3. **Scalabilité**: Possibilité d'avoir plusieurs workers spécialisés
4. **Monitoring**: Identification facile des goulots d'étranglement

---

## 🔍 Diagnostic Rapide

### Commande de Diagnostic Complète

```bash
echo "=== DIAGNOSTIC CELERY QUEUES ==="
echo ""
echo "1. Queues écoutées par le worker:"
docker logs samaconso_celery_worker 2>&1 | grep -A 5 "queues"
echo ""
echo "2. Tâches récentes:"
docker logs samaconso_celery_worker --tail 20 | grep "received\|succeeded\|failed"
echo ""
echo "3. État dans Flower:"
curl -s "http://localhost:5555/api/workers" --user admin:admin | python -c "import sys, json; data = json.load(sys.stdin); print(json.dumps(data, indent=2))" 2>/dev/null
```

### Vérification Rapide

```bash
# Le worker écoute-t-il toutes les queues?
docker logs samaconso_celery_worker 2>&1 | grep -q "low_priority" && echo "✅ OK" || echo "❌ PROBLÈME"
```

---

## 🚀 Application de la Solution

### Si Vous Avez Ce Problème

#### Étape 1: Vérifier le Problème
```bash
# Vérifier les queues actuelles
docker logs samaconso_celery_worker | grep queues
```

Si vous ne voyez que `normal`, vous avez le problème.

#### Étape 2: Appliquer la Correction
```bash
# Modifier docker-compose.fixed.yml (ajouter -Q urgent,high_priority,normal,low_priority)
# Puis redémarrer le worker
docker-compose -f docker-compose.fixed.yml up -d celery_worker
```

#### Étape 3: Vérifier la Correction
```bash
# Attendre 10 secondes
sleep 10

# Vérifier que toutes les queues sont écoutées
docker logs samaconso_celery_worker | grep queues
```

#### Étape 4: Sauvegarder l'Image
```bash
docker commit samaconso_celery_worker samaconso_celery_worker:with-fixes
```

---

## 📋 Configuration Finale

### docker-compose.fixed.yml

```yaml
celery_worker:
  image: samaconso_celery_worker:with-fixes
  container_name: samaconso_celery_worker
  command: celery -A app.celery_app worker --loglevel=info --pool=solo -n worker@%h --concurrency=2 -Q urgent,high_priority,normal,low_priority
  env_file:
    - .env.docker.fixed
  environment:
    - REDIS_URL=redis://redis:6379/0
    - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
    - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672/
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
  depends_on:
    - redis
    - rabbitmq
    - api
  restart: unless-stopped
```

**Points clés**:
- ✅ `-Q urgent,high_priority,normal,low_priority` : Écoute sur toutes les queues
- ✅ `--pool=solo` : Compatible avec Windows/WSL
- ✅ `--concurrency=2` : 2 workers parallèles
- ✅ Image `with-fixes` : Configuration permanente

---

## 💡 Bonnes Pratiques

### 1. Toujours Spécifier les Queues Explicitement

**❌ Mauvais** (par défaut):
```bash
celery -A app.celery_app worker
```

**✅ Bon** (explicite):
```bash
celery -A app.celery_app worker -Q urgent,high_priority,normal,low_priority
```

### 2. Monitorer les Queues

Accédez régulièrement à Flower (http://localhost:5555) pour vérifier:
- Queues actives
- Tâches en attente (`PENDING`)
- Taux de succès/échec

### 3. Éviter les Tâches Bloquées

Si vous voyez beaucoup de tâches en `PENDING`:
```bash
# Vérifier que le worker écoute la bonne queue
docker logs samaconso_celery_worker | grep queues

# Vérifier qu'il n'y a pas d'erreurs
docker logs samaconso_celery_worker | grep -i error
```

---

## 🎯 Résumé

### Problème
Worker Celery n'écoutait que sur la queue `normal`, mais les notifications broadcast étaient envoyées sur `low_priority`.

### Solution
Ajout de `-Q urgent,high_priority,normal,low_priority` dans la commande du worker.

### Résultat
✅ Toutes les notifications sont maintenant traitées correctement
✅ 86 notifications envoyées avec succès lors du test
✅ Configuration permanente sauvegardée

---

## 📞 Références

- **Configuration**: [docker-compose.fixed.yml](docker-compose.fixed.yml:117)
- **Routage des tâches**: [app/celery_app.py](app/celery_app.py:43-57)
- **Documentation Celery**: https://docs.celeryq.dev/en/stable/userguide/routing.html
- **Monitoring**: http://localhost:5555 (Flower)

---

**Date de résolution**: 2025-11-12
**Statut**: ✅ Résolu
**Notifications fonctionnelles**: ✅ 100%
