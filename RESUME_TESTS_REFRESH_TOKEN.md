# ✅ Résumé des Tests - Refresh Token JWT

## 📊 État Actuel

### ✅ Validations Effectuées

1. **Syntaxe Python** : ✅ **CORRECTE**
   - `app/auth.py` - ✅ Compilé sans erreur
   - `app/routers/auth_routers.py` - ✅ Compilé sans erreur
   - `app/models/models.py` - ✅ Compilé sans erreur
   - `app/config.py` - ✅ Compilé sans erreur
   - `app/schemas/user_schemas.py` - ✅ Compilé sans erreur

2. **Migration Alembic** : ✅ **SYNTAXE CORRECTE**
   - `alembic/versions/add_refresh_token_to_user_session.py` - ✅ Compilé sans erreur
   - `down_revision` pointant vers `6f541bba54f8` (dernière migration) - ✅ **CORRECT**

3. **Docker** : ⚠️ **EN COURS**
   - Conteneurs démarrés
   - Problème de connexion à la base de données PostgreSQL (`10.101.1.171:5432`)
   - L'API ne peut pas démarrer complètement sans connexion à la base

### ⚠️ Problème Actuel

**Erreur de connexion à la base de données :**
```
connection to server at "10.101.1.171", port 5432 failed: Connection refused
```

**Cause possible :**
- Le serveur PostgreSQL n'est pas accessible depuis le conteneur Docker
- Problème de réseau/routing entre Docker et le serveur PostgreSQL
- Le serveur PostgreSQL n'est pas démarré

## 📋 Tests à Effectuer (Une fois la Base Accessible)

### 1. Vérifier la Connexion à la Base de Données

```bash
docker exec samaconso_api python -c "from app.database import engine; engine.connect(); print('✅ Connexion DB OK')"
```

### 2. Exécuter la Migration Alembic

```bash
docker exec samaconso_api alembic upgrade head
```

**Résultat attendu :**
```
INFO  [alembic.runtime.migration] Running upgrade 6f541bba54f8 -> refresh_token_user_session, add refresh token fields to user_session
```

### 3. Vérifier les Champs dans la Base

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_session' 
AND column_name LIKE '%refresh%';
```

**Résultat attendu :**
```
     column_name          | data_type
--------------------------+-----------
 refresh_token_hash       | character varying
 refresh_token_expires_at | timestamp with time zone
```

### 4. Tester l'API

#### A. Vérifier que l'API répond

```bash
curl http://localhost:8000/
```

**Résultat attendu :**
```json
{"message":"SAMA CONSO", "version": "2.0.0", "status": "running"}
```

#### B. Tester le Login

```bash
curl -X POST http://localhost:8000/auth/token-json \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"votre_username\", \"password\": \"votre_password\"}"
```

**Vérifications :**
- ✅ Status code : `200`
- ✅ Réponse contient `access_token`
- ✅ **Réponse contient `refresh_token`** ← **NOUVEAU**
- ✅ Réponse contient `token_type: "bearer"`

#### C. Tester le Refresh Token

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"VOTRE_REFRESH_TOKEN_ICI\"}"
```

**Vérifications :**
- ✅ Status code : `200`
- ✅ Nouveau `access_token` retourné
- ✅ Nouveau `refresh_token` retourné (rotation)

#### D. Tester le Refresh avec Token Invalide

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"token_invalide_12345\"}"
```

**Vérifications :**
- ✅ Status code : `401`
- ✅ Message : `"Invalid or expired refresh token"`

#### E. Tester le Logout

```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"VOTRE_REFRESH_TOKEN\"}"
```

**Vérifications :**
- ✅ Status code : `200`
- ✅ `tokens_revoked: true`

#### F. Vérifier que le Refresh Token est Révoqué

Après le logout, essayez de rafraîchir avec le même refresh token :

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"REFRESH_TOKEN_REVOKE\"}"
```

**Vérifications :**
- ✅ Status code : `401`
- ✅ Message : `"Invalid or expired refresh token"`

### 5. Exécuter les Tests Automatisés

#### A. Copier le script de test dans le conteneur

```bash
docker cp test_refresh_token.py samaconso_api:/app/test_refresh_token.py
```

#### B. Modifier les identifiants dans le script

Éditez `test_refresh_token.py` lignes 29-30 avec un utilisateur valide :

```python
login_data = {
    "username": "votre_username",  # Remplacez
    "password": "votre_password"    # Remplacez
}
```

#### C. Exécuter les tests

```bash
docker exec -it samaconso_api python /app/test_refresh_token.py
```

**Résultats attendus :**
- ✅ TEST 0: Santé de l'API - SUCCESS
- ✅ TEST 1: Login - SUCCESS (access_token + refresh_token)
- ✅ TEST 2: Accès avec access token - SUCCESS
- ✅ TEST 3: Refresh token - SUCCESS
- ✅ TEST 4: Refresh avec token invalide - SUCCESS (rejeté)
- ✅ TEST 5: Logout - SUCCESS (token révoqué)

## 🔧 Résolution du Problème de Connexion DB

### Option 1 : Vérifier que le Serveur PostgreSQL est Accessible

```bash
# Depuis l'hôte
telnet 10.101.1.171 5432

# Depuis le conteneur
docker exec samaconso_api telnet 10.101.1.171 5432
```

### Option 2 : Vérifier les Extra Hosts dans docker-compose.yml

Assurez-vous que le fichier `docker-compose.yml` contient bien :
```yaml
extra_hosts:
  - "srv-asreports:10.101.2.87"
  - "srv-commercial:10.101.3.243"
```

### Option 3 : Utiliser un Réseau Docker Custom

Si nécessaire, configurez un réseau Docker pour accéder au serveur PostgreSQL.

## 📊 Résumé des Modifications

### Fichiers Modifiés

1. **app/config.py**
   - ✅ Ajout `REFRESH_TOKEN_EXPIRE_DAYS = 7`

2. **app/models/models.py**
   - ✅ Ajout `refresh_token_hash` (String)
   - ✅ Ajout `refresh_token_expires_at` (DateTime)

3. **app/auth.py**
   - ✅ `create_refresh_token()` - Génère un token sécurisé
   - ✅ `hash_refresh_token()` - Hash le token
   - ✅ `verify_refresh_token()` - Vérifie le token
   - ✅ `create_token_pair()` - Crée access + refresh
   - ✅ `save_refresh_token()` - Sauvegarde en DB
   - ✅ `verify_refresh_token_in_db()` - Vérifie en DB
   - ✅ `revoke_refresh_token()` - Révoque les tokens

4. **app/routers/auth_routers.py**
   - ✅ Modifié `/auth/token` - Retourne refresh_token
   - ✅ Modifié `/auth/token-json` - Retourne refresh_token
   - ✅ Modifié `/auth/token-json-v2` - Retourne refresh_token
   - ✅ Modifié `/auth/ldap-json` - Retourne refresh_token
   - ✅ Nouveau `/auth/refresh` - Rafraîchit les tokens
   - ✅ Nouveau `/auth/logout` - Révoque les tokens

5. **app/schemas/user_schemas.py**
   - ✅ Modifié `Token` - Inclut `refresh_token`
   - ✅ Nouveau `RefreshTokenSchema`
   - ✅ Nouveau `RefreshTokenOptionalSchema`

6. **alembic/versions/add_refresh_token_to_user_session.py**
   - ✅ Nouvelle migration pour ajouter les champs refresh token

### Nouveaux Fichiers

1. **test_refresh_token.py** - Script de test complet
2. **docker_test_refresh_token.bat** - Script Windows automatique
3. **docker_test_refresh_token.sh** - Script Linux/Mac automatique
4. **INSTRUCTIONS_TEST_REFRESH_TOKEN.md** - Documentation complète
5. **TEST_READY.md** - Guide rapide
6. **RESUME_TESTS_REFRESH_TOKEN.md** - Ce fichier

## ✅ Checklist Finale

### Code
- [x] Syntaxe Python correcte
- [x] Migration Alembic syntaxiquement correcte
- [x] Tous les imports fonctionnent
- [x] Pas d'erreurs de linting

### Migration
- [ ] Connexion à la base de données fonctionnelle
- [ ] Migration Alembic exécutée avec succès
- [ ] Champs `refresh_token_hash` et `refresh_token_expires_at` ajoutés

### Tests API
- [ ] API accessible sur http://localhost:8000
- [ ] Login retourne `access_token` ET `refresh_token`
- [ ] Refresh token fonctionne
- [ ] Refresh avec token invalide est rejeté (401)
- [ ] Logout révoque le refresh token
- [ ] Refresh token révoqué ne fonctionne plus

## 🎯 Prochaines Étapes

1. **Résoudre la connexion à la base de données**
   - Vérifier que PostgreSQL est accessible depuis Docker
   - Configurer le réseau si nécessaire

2. **Exécuter la migration**
   ```bash
   docker exec samaconso_api alembic upgrade head
   ```

3. **Tester l'API**
   - Utiliser `docker_test_refresh_token.bat` ou
   - Tester manuellement avec cURL

4. **Valider les résultats**
   - Vérifier que tous les tests passent
   - Vérifier que les tokens sont bien stockés en base

---

**Date :** 2025-01-15  
**Statut :** ✅ Code prêt - ⚠️ En attente de connexion DB

