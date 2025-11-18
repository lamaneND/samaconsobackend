# 🚀 Guide de Déploiement avec Proxy Senelec

## 📋 Informations Proxy

- **IP** : `10.101.201.204`
- **Port** : `8080`
- **URL complète** : `http://10.101.201.204:8080`

---

## ✅ DÉPLOIEMENT EN 3 ÉTAPES

### Étape 1: Configurer le Proxy (1 fois seulement)

```cmd
configure_proxy_senelec.bat
```

**Ce script va** :
- ✅ Configurer les variables d'environnement Windows
- ✅ Créer `~/.docker/config.json` avec le proxy
- ✅ Configurer `daemon.json` pour Docker Desktop
- ✅ Configurer npm et pip également

**Après exécution** :
1. **Redémarrer Docker Desktop** :
   - Clic droit sur l'icône Docker → "Quit Docker Desktop"
   - Relancer Docker Desktop
   - Attendre qu'il soit complètement démarré (icône verte)

---

### Étape 2: Tester la Configuration

```cmd
test_proxy.bat
```

**Tests effectués** :
- Variables d'environnement
- Fichiers de configuration
- Connectivité via proxy (Google, Docker Hub, PyPI)
- Tentative de pull d'une image test

**Résultat attendu** :
```
✅ HTTP Code: 200 ou 401 (Docker Hub)
✅ docker pull hello-world réussit
```

---

### Étape 3: Déployer l'Application

```cmd
deploy_fix.bat
```

**Ce script va** :
1. Arrêter les anciens conteneurs
2. **Construire les nouvelles images** (avec drivers SQL Server)
3. Démarrer tous les services
4. Exécuter les tests de validation

⏱️ **Temps estimé** : 5-7 minutes

---

## 🎯 Procédure Complète

```cmd
REM 1. Configurer le proxy (1 fois)
configure_proxy_senelec.bat

REM 2. Redémarrer Docker Desktop
REM    (Manuellement via l'interface)

REM 3. Tester la configuration
test_proxy.bat

REM 4. Si les tests passent, déployer
deploy_fix.bat
```

---

## 🔍 Vérifications Post-Déploiement

### 1. État des Conteneurs

```cmd
docker ps
```

**Attendu** :
```
✅ samaconso_api           - HEALTHY
✅ samaconso_celery_worker - HEALTHY
✅ samaconso_redis         - HEALTHY
✅ samaconso_rabbitmq      - HEALTHY
✅ samaconso_minio         - HEALTHY
✅ samaconso_flower        - HEALTHY
```

### 2. Test des Drivers SQL Server

```cmd
docker exec samaconso_api python -c "import pyodbc; print('Drivers:', pyodbc.drivers())"
```

**Attendu** : `['ODBC Driver 18 for SQL Server']`

### 3. Test Connexion SQL Server SIC

```cmd
docker exec samaconso_api python -c "from app.database import get_db_connection_sic; conn = get_db_connection_sic(); print('✅ Connexion OK' if conn else '❌ Échec'); conn.close() if conn else None"
```

### 4. Test Connexion SQL Server Postpaid

```cmd
docker exec samaconso_api python -c "from app.database import get_db_connection_postpaid; conn = get_db_connection_postpaid(); print('✅ Connexion OK' if conn else '❌ Échec'); conn.close() if conn else None"
```

### 5. Test Firebase

```cmd
docker exec samaconso_api python -c "import firebase_admin; app = firebase_admin.get_app(); print('✅ Firebase OK:', app.name)"
```

### 6. Test Complet

```cmd
docker exec samaconso_api python test_docker_connectivity.py
```

**Attendu** : `Score: 7/7 tests réussis (100%)`

---

## 🌐 Services Disponibles

| Service | URL | Identifiants |
|---------|-----|--------------|
| **API FastAPI** | http://localhost:8000 | - |
| **API Documentation** | http://localhost:8000/docs | - |
| **Flower (Celery)** | http://localhost:5555 | admin / admin |
| **RabbitMQ Management** | http://localhost:15672 | guest / guest |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |

---

## 🔧 Dépannage

### Problème 1: "docker pull" échoue toujours

**Solution** :

1. Vérifier que Docker Desktop est bien redémarré
2. Vérifier la connectivité du proxy :
   ```cmd
   curl -x http://10.101.201.204:8080 https://www.google.com
   ```
3. Si le proxy ne répond pas, vérifier avec l'IT

### Problème 2: Build échoue avec erreur réseau

**Diagnostic** :
```cmd
REM Vérifier les logs Docker
docker-compose -f docker-compose.fixed.yml build --progress=plain
```

**Solutions** :
- Augmenter le timeout : `DOCKER_CLIENT_TIMEOUT=300 docker-compose build`
- Vérifier NO_PROXY pour les serveurs internes

### Problème 3: Conteneurs ne démarrent pas

**Diagnostic** :
```cmd
docker logs samaconso_api
docker logs samaconso_celery_worker
```

**Solutions courantes** :
- Fichier Firebase manquant → Vérifier `app/samaconso-firebase-*.json`
- Serveurs SQL non accessibles → Vérifier `extra_hosts` dans docker-compose
- Permissions → Vérifier les volumes montés

---

## 📊 Configuration Réseau Complète

### Proxy Senelec
```
http://10.101.201.204:8080
```

### Serveurs SQL
```
srv-asreports:  10.101.2.87   (SIC)
srv-commercial: 10.101.3.243  (Postpaid)
```

### NO_PROXY (exclusions)
```
localhost,127.0.0.1,.local,.electricite.sn,10.101.2.87,10.101.3.243
```

---

## 🆘 Si Ça Ne Marche Toujours Pas

### Option Alternative: Utiliser les Images Existantes

Si le build échoue encore malgré le proxy configuré :

```cmd
REM Utiliser les images déjà construites
deploy_sans_rebuild.bat

REM Puis patcher manuellement pour les drivers SQL
patch_conteneurs_actuels.bat
```

**Note** : Cette méthode utilise les images existantes sans les reconstruire.

---

## ✅ Checklist Finale

Avant de déployer :
- [ ] Proxy configuré avec `configure_proxy_senelec.bat`
- [ ] Docker Desktop redémarré
- [ ] Test proxy réussi avec `test_proxy.bat`
- [ ] Fichier Firebase présent dans `app/`

Après déploiement :
- [ ] Tous les conteneurs `HEALTHY`
- [ ] Drivers SQL Server présents
- [ ] Connexions SQL SIC et Postpaid OK
- [ ] Firebase initialisé
- [ ] API accessible sur http://localhost:8000
- [ ] Flower accessible sur http://localhost:5555

---

## 📞 Support

**Configuration fonctionnelle** :
- Proxy : `10.101.201.204:8080` ✅
- IPs SQL : `10.101.2.87` et `10.101.3.243` ✅
- Firebase : Fichier présent ✅

**Scripts disponibles** :
- `configure_proxy_senelec.bat` - Configuration proxy
- `test_proxy.bat` - Tests de connectivité
- `deploy_fix.bat` - Déploiement complet
- `deploy_sans_rebuild.bat` - Alternative sans rebuild
- `patch_conteneurs_actuels.bat` - Patch manuel

**Documentation** :
- `GUIDE_PROBLEME_SSL.md` - Guide détaillé proxy/SSL
- `DEPLOYMENT_READY.md` - Guide de déploiement
- `SOLUTIONS_DOCKER.md` - Analyse technique

---

**Date** : 2025-11-12
**Proxy** : 10.101.201.204:8080
**Status** : ✅ Configuration prête
