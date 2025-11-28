# 🚀 Tests Refresh Token - Prêt à Exécuter

## ⚠️ Docker Desktop doit être démarré

Docker Desktop n'est pas actuellement en cours d'exécution. Voici les étapes à suivre :

## 📋 Étapes de Test

### 1. Démarrer Docker Desktop
   - Lancez Docker Desktop sur votre machine
   - Attendez que Docker soit complètement démarré (icône Docker dans la barre des tâches)

### 2. Une fois Docker démarré, exécutez :

#### Option A : Script automatique (recommandé)
```bash
docker_test_refresh_token.bat
```

#### Option B : Commandes manuelles

```bash
# 1. Démarrer les services
docker-compose up -d

# 2. Attendre que les services soient prêts (30 secondes)
timeout /t 30

# 3. Exécuter la migration Alembic
docker exec samaconso_api alembic upgrade head

# 4. Vérifier que l'API répond
curl http://localhost:8000/

# 5. Copier le script de test dans le conteneur
docker cp test_refresh_token.py samaconso_api:/app/test_refresh_token.py

# 6. Modifier les identifiants dans test_refresh_token.py (optionnel)
# Éditez test_refresh_token.py et changez les lignes 21-22 avec un utilisateur valide

# 7. Exécuter les tests
docker exec -it samaconso_api python /app/test_refresh_token.py
```

### 3. Tests rapides avec cURL

Une fois Docker démarré et l'API accessible, testez manuellement :

#### Test 1 : Login
```bash
curl -X POST http://localhost:8000/auth/token-json ^
  -H "Content-Type: application/json" ^
  -d "{\"username\": \"votre_username\", \"password\": \"votre_password\"}"
```

**Vérification :** La réponse doit contenir `access_token` ET `refresh_token`

#### Test 2 : Refresh (remplacez YOUR_REFRESH_TOKEN)
```bash
curl -X POST http://localhost:8000/auth/refresh ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\": \"YOUR_REFRESH_TOKEN\"}"
```

**Vérification :** Nouveaux `access_token` et `refresh_token` retournés

#### Test 3 : Logout (remplacez les tokens)
```bash
curl -X POST http://localhost:8000/auth/logout ^
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"refresh_token\": \"YOUR_REFRESH_TOKEN\"}"
```

**Vérification :** `tokens_revoked: true`

## 📊 Vérification de la Migration

Après l'exécution de la migration, vérifiez dans la base de données :

```bash
docker exec samaconso_api psql -h 10.101.1.171 -U postgres -d samaconso -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'user_session' AND column_name LIKE '%refresh%';"
```

**Résultat attendu :**
```
     column_name          | data_type
--------------------------+-----------
 refresh_token_hash       | character varying
 refresh_token_expires_at | timestamp with time zone
```

## 🔍 Vérification des Logs

```bash
docker logs samaconso_api --tail 50 | findstr /i "refresh login logout"
```

## ✅ Checklist de Validation

- [ ] Docker Desktop démarré
- [ ] Services Docker en cours d'exécution (`docker-compose ps`)
- [ ] Migration Alembic exécutée avec succès
- [ ] API accessible sur http://localhost:8000
- [ ] Login retourne `access_token` ET `refresh_token`
- [ ] Refresh token fonctionne
- [ ] Logout révoque le refresh token

## 📚 Documentation Complète

Consultez `INSTRUCTIONS_TEST_REFRESH_TOKEN.md` pour :
- Guide détaillé des tests
- Résolution de problèmes
- Vérifications de base de données
- Checklist de validation complète

## 🆘 Problèmes Fréquents

### "Docker n'est pas accessible"
→ Démarrez Docker Desktop et attendez qu'il soit complètement lancé

### "Column refresh_token_hash does not exist"
→ Exécutez : `docker exec samaconso_api alembic upgrade head`

### "API non accessible sur localhost:8000"
→ Vérifiez que le conteneur est démarré : `docker ps --filter "name=samaconso_api"`

### "Invalid credentials"
→ Vérifiez que vous utilisez un utilisateur valide de votre base de données

---

**Tous les fichiers sont prêts !** Démarrrez Docker Desktop puis exécutez `docker_test_refresh_token.bat` 🚀


