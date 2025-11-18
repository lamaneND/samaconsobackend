# ⚡ SamaConso API - Quickstart

## 🚀 Démarrer en 30 Secondes

```bash
# 1. Démarrer
docker-compose -f docker-compose.fixed.yml up -d

# 2. Attendre (30 secondes)
timeout /t 30 /nobreak

# 3. Vérifier
curl http://localhost:8000
```

**Résultat attendu**: `{"message":"SAMA CONSO","version":"2.0.0","status":"running"}`

---

## 🎯 Interfaces Web

| Service | URL | Login |
|---------|-----|-------|
| **API Docs** | http://localhost:8000/docs | - |
| **Flower** | http://localhost:5555 | admin/admin |
| **RabbitMQ** | http://localhost:15672 | guest/guest |
| **MinIO** | http://localhost:9001 | minioadmin/minioadmin |

---

## 🧪 Test Rapide

### Test Notification
```bash
send_test_notification.bat 9
```
(Remplacez `9` par votre user_id)

### Vérifier Santé
```bash
check_health.bat
```

---

## 📖 Documentation Complète

**Débutant?** → [README_DOCKER.md](README_DOCKER.md) (5 min)
**Problème?** → [PROBLEMES_RESOLUS_FINAL.md](PROBLEMES_RESOLUS_FINAL.md)
**Référence?** → [GUIDE_UTILISATION_DOCKER.md](GUIDE_UTILISATION_DOCKER.md)

---

## 🛑 Arrêter

```bash
docker-compose -f docker-compose.fixed.yml down
```

---

## ✅ Checklist

- [ ] Application démarrée
- [ ] API accessible (http://localhost:8000)
- [ ] Test santé OK (`check_health.bat`)
- [ ] Notification test reçue

**Tout est OK?** Vous êtes prêt! 🎉
