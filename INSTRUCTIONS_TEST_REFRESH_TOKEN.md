# Instructions de Test - Refresh Token JWT

## 📋 Prérequis

1. **Docker Desktop** doit être démarré
2. Les services Docker doivent être accessibles
3. Un utilisateur valide dans la base de données pour les tests

## 🚀 Étapes de Test

### 1. Reconstruire l'image Docker (si nécessaire)

Si vous avez modifié le code, reconstruisez l'image :

```bash
docker-compose build
```

### 2. Démarrer les services Docker

```bash
docker-compose up -d
```

Vérifier que tous les services sont en cours d'exécution :

```bash
docker-compose ps
```

### 3. Exécuter la migration Alembic

La migration ajoute les champs `refresh_token_hash` et `refresh_token_expires_at` à la table `user_session` :

```bash
docker exec samaconso_api alembic upgrade head
```

**Résultat attendu :**
```
INFO  [alembic.runtime.migration] Running upgrade 6f541bba54f8 -> refresh_token_user_session, add refresh token fields to user_session
```

### 4. Vérifier la santé de l'API

```bash
curl http://localhost:8000/
```

**Résultat attendu :**
```json
{"message":"SAMA CONSO", "version": "2.0.0", "status": "running"}
```

### 5. Exécuter les tests

#### Option A : Script automatique (Windows)

```bash
docker_test_refresh_token.bat
```

#### Option B : Script automatique (Linux/Mac)

```bash
chmod +x docker_test_refresh_token.sh
./docker_test_refresh_token.sh
```

#### Option C : Tests manuels

Copiez le fichier de test dans le conteneur :

```bash
docker cp test_refresh_token.py samaconso_api:/app/test_refresh_token.py
```

Exécutez les tests :

```bash
docker exec -it samaconso_api python /app/test_refresh_token.py
```

**⚠️ Important :** Modifiez les identifiants dans `test_refresh_token.py` (lignes 21-22) avec un utilisateur valide de votre base de données.

## 📝 Tests Manuels avec cURL

### Test 1 : Login

```bash
curl -X POST http://localhost:8000/auth/token-json \
  -H "Content-Type: application/json" \
  -d '{
    "username": "votre_username",
    "password": "votre_password"
  }'
```

**Résultat attendu :**
```json
{
  "status_code": 200,
  "user": {...},
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "xYz123abc...",
  "token_type": "bearer"
}
```

✅ **Vérification :** Le champ `refresh_token` doit être présent dans la réponse.

### Test 2 : Refresh Token

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "votre_refresh_token_ici"
  }'
```

**Résultat attendu :**
```json
{
  "access_token": "nouveau_access_token...",
  "refresh_token": "nouveau_refresh_token...",
  "token_type": "bearer"
}
```

✅ **Vérification :** De nouveaux `access_token` et `refresh_token` doivent être retournés.

### Test 3 : Refresh avec Token Invalide

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "token_invalide_12345"
  }'
```

**Résultat attendu :**
```json
{
  "detail": "Invalid or expired refresh token"
}
```

✅ **Vérification :** Le code de statut doit être `401 Unauthorized`.

### Test 4 : Logout

```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer votre_access_token_ici" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "votre_refresh_token_ici"
  }'
```

**Résultat attendu :**
```json
{
  "status_code": 200,
  "message": "Logout successful",
  "tokens_revoked": true
}
```

✅ **Vérification :** Le code de statut doit être `200 OK` et `tokens_revoked` doit être `true`.

### Test 5 : Vérifier que le Refresh Token est Révoqué

Après le logout, essayez de rafraîchir avec le même refresh token :

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "refresh_token_révoqué"
  }'
```

**Résultat attendu :**
```json
{
  "detail": "Invalid or expired refresh token"
}
```

✅ **Vérification :** Le refresh token doit être rejeté (code `401`).

## 📊 Vérification dans la Base de Données

Vérifiez que les champs sont bien ajoutés :

```sql
SELECT 
    id, 
    user_id, 
    refresh_token_hash IS NOT NULL as has_refresh_token,
    refresh_token_expires_at,
    is_active,
    last_login
FROM user_session
ORDER BY last_login DESC
LIMIT 10;
```

**Vérifications :**
- ✅ Les champs `refresh_token_hash` et `refresh_token_expires_at` existent
- ✅ `refresh_token_hash` est rempli après un login réussi
- ✅ `refresh_token_expires_at` est une date future (7 jours après le login)
- ✅ `is_active` est `false` après un logout

## 🔍 Vérification des Logs

Vérifiez les logs de l'API pour les opérations d'authentification :

```bash
docker logs samaconso_api | grep -i "refresh\|login\|logout"
```

**Résultat attendu :**
```
✅ Login successful | User ID: X | Username: ...
🔄 Refresh token request
✅ Token refreshed successfully | User ID: X
🚪 Logout request | User ID: X
✅ Logout successful | User ID: X
```

## 🐛 Résolution de Problèmes

### Erreur : "column refresh_token_hash does not exist"

**Solution :** La migration n'a pas été exécutée. Exécutez :
```bash
docker exec samaconso_api alembic upgrade head
```

### Erreur : "Invalid or expired refresh token"

**Vérifications :**
1. Le refresh token est correctement copié (pas de caractères manquants)
2. Le refresh token n'a pas été révoqué
3. Le refresh token n'a pas expiré (7 jours maximum)

### Erreur : "User not found or inactive"

**Vérifications :**
1. L'utilisateur existe dans la base de données
2. Le champ `is_activate` est `True` dans la table `user`

### L'API ne démarre pas

**Vérifications :**
```bash
# Vérifier les logs
docker logs samaconso_api

# Vérifier les services dépendants
docker-compose ps

# Redémarrer les services
docker-compose restart
```

## ✅ Checklist de Validation

- [ ] Migration Alembic exécutée avec succès
- [ ] Champs `refresh_token_hash` et `refresh_token_expires_at` ajoutés à `user_session`
- [ ] Login retourne `access_token` ET `refresh_token`
- [ ] Refresh token fonctionne et retourne de nouveaux tokens
- [ ] Refresh avec token invalide est rejeté (401)
- [ ] Logout révoque le refresh token
- [ ] Refresh token révoqué ne fonctionne plus
- [ ] Logs montrent les opérations de login/refresh/logout

## 📚 Documentation

Pour plus d'informations sur l'utilisation du refresh token dans votre application client, consultez :
- La documentation OAuth2 JWT
- Les endpoints dans `/docs` (Swagger UI) : http://localhost:8000/docs

---

**Date de création :** 2025-01-15  
**Version :** 1.0.0

