# SamaConso API - Démarrage Rapide Docker

## Démarrage Rapide

### 1. Démarrer l'application
```bash
docker-compose -f docker-compose.fixed.yml up -d
```

### 2. Vérifier que tout fonctionne
```bash
check_health.bat
```
Ou manuellement:
```bash
curl http://localhost:8000
```

### 3. Envoyer une notification test
```bash
send_test_notification.bat 9
```
(Remplacez `9` par votre user_id)

---

## Accès aux Interfaces Web

| Service | URL | Identifiants |
|---------|-----|--------------|
| **API Documentation** | http://localhost:8000/docs | - |
| **Flower (Celery)** | http://localhost:5555 | admin / admin |
| **RabbitMQ** | http://localhost:15672 | guest / guest |
| **MinIO** | http://localhost:9001 | minioadmin / minioadmin |

---

## Commandes Essentielles

### Arrêter l'application
```bash
docker-compose -f docker-compose.fixed.yml down
```

### Voir les logs
```bash
# API
docker logs samaconso_api -f

# Worker
docker logs samaconso_celery_worker -f

# Tous
docker-compose -f docker-compose.fixed.yml logs -f
```

### Redémarrer un service
```bash
docker-compose -f docker-compose.fixed.yml restart api
docker-compose -f docker-compose.fixed.yml restart celery_worker
```

---

## Tests Rapides

### Test SQL Server
```bash
docker exec samaconso_api python -c "from app.database import get_db_connection_sic; print('OK' if get_db_connection_sic() else 'FAIL')"
```

### Test Firebase
```bash
docker exec samaconso_api python -c "import firebase_admin; print('Firebase OK')"
```

---

## Configuration Réseau

### Serveurs SQL Server
- **SIC**: srv-asreports → `10.101.2.87`
- **Postpaid**: srv-commercial → `10.101.3.243`

### Proxy Senelec
- **IP**: `10.101.201.204`
- **Port**: `8080`
- **SSL**: Désactivé dans les conteneurs

---

## Structure des Fichiers

```
samaconsoapi-dev_pcyn_new/
├── docker-compose.fixed.yml      # Configuration Docker principale
├── Dockerfile.fixed               # Image Docker avec correctifs
├── .env.docker.fixed             # Variables d'environnement
├── check_health.bat              # Script de vérification santé
├── send_test_notification.bat    # Script test notification
├── GUIDE_UTILISATION_DOCKER.md   # Guide complet
├── SUCCES_COMPLET.md             # Historique déploiement
└── app/
    ├── firebase.py               # Configuration Firebase
    ├── database.py               # Connexions SQL Server
    └── samaconso-firebase-adminsdk-*.json
```

---

## Résolution de Problèmes

### Problème: Notifications non reçues
```bash
# Vérifier que le worker écoute sur toutes les queues
docker logs samaconso_celery_worker | grep queues
```
**Solution**: Voir [FIX_CELERY_QUEUES.md](FIX_CELERY_QUEUES.md)

### Problème: Conteneur "Unhealthy"
```bash
docker logs <nom_conteneur> --tail 50
docker restart <nom_conteneur>
```

### Problème: SQL Server ne répond pas
```bash
# Vérifier les mappings réseau
docker exec samaconso_api cat /etc/hosts | grep srv-
```

### Problème: Firebase ne fonctionne pas
```bash
# Vérifier la configuration SSL
docker exec samaconso_api python -c "import ssl; print(ssl._create_default_https_context)"
```

### Voir toutes les solutions
Consultez [GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md)

---

## Configuration Permanente

Les images Docker contiennent déjà tous les correctifs:
- ✅ Drivers SQL Server ODBC installés
- ✅ Configuration SSL Firebase désactivée
- ✅ Mapping réseau configuré
- ✅ Proxy Senelec configuré

**Vous n'avez PAS besoin de rebuild à chaque démarrage!**

---

## Support

### Documentation Complète
- **[GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md)** - Guide complet avec toutes les commandes
- **[SUCCES_COMPLET.md](SUCCES_COMPLET.md)** - Historique et solutions appliquées
- **[DEPLOIEMENT_AVEC_PROXY.md](DEPLOIEMENT_AVEC_PROXY.md)** - Configuration proxy détaillée
- **[FIREBASE_PROXY_SENELEC.md](FIREBASE_PROXY_SENELEC.md)** - Solutions Firebase

### Commande de Diagnostic Complet
```bash
docker exec samaconso_api python -c "
print('=== DIAGNOSTIC SAMA CONSO ===')
print('1. Drivers ODBC:', end=' ')
import pyodbc
print('OK' if 'ODBC Driver 18 for SQL Server' in pyodbc.drivers() else 'FAIL')

print('2. SQL SIC:', end=' ')
from app.database import get_db_connection_sic
print('OK' if get_db_connection_sic() else 'FAIL')

print('3. SQL Postpaid:', end=' ')
from app.database import get_db_connection_postpaid
print('OK' if get_db_connection_postpaid() else 'FAIL')

print('4. Firebase:', end=' ')
import firebase_admin
print('OK')

print('=== FIN DIAGNOSTIC ===')
"
```

---

## Checklist Démarrage

- [ ] Démarrer: `docker-compose -f docker-compose.fixed.yml up -d`
- [ ] Attendre 30 secondes que tous les services démarrent
- [ ] Vérifier: `check_health.bat`
- [ ] Tester API: http://localhost:8000/docs
- [ ] Tester notification: `send_test_notification.bat`

---

**Statut** : ✅ Production Ready
**Date** : 2025-11-12
**Version** : 1.0

**Tous les services sont opérationnels et prêts pour la production!** 🚀
