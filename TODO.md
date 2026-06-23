# TODO — SamaConso API

## 1. Renouvellement du certificat mTLS XMLVend

**Priorité : BLOQUANT** — Le simulateur ne fonctionne plus depuis le 4 juin 2026.

- [ ] Contacter l'administrateur PKI Senelec pour renouveler le certificat `CN=487`
  - CA émettrice : `Senelec-SRV-SIEGECD2-CA` (domaine `electricite.sn`)
  - Certificat expiré le : **2026-06-04**
- [ ] Remplacer `app/routers/487.pfx` par le nouveau PFX
- [ ] Copier le nouveau PFX sur les serveurs de production :
  - SRV-MOBAPP1 (`10.101.1.210`) : `/app/app/routers/487.pfx`
  - SRV-MOBAPP2 (`10.101.1.211`) : `/app/app/routers/487.pfx`
- [ ] Redémarrer le container API sur chaque serveur :
  ```bash
  docker compose restart api
  ```
- [ ] Vérifier via `GET /simulateur/cert-info` que le nouveau cert est valide
- [ ] Tester `POST /simulateur/trial-credit-vend-request` avec un compteur réel

---

## 2. Protection des routes simulateur par JWT

- [ ] Ajouter la dépendance `get_current_user` sur les endpoints `/simulateur/*`
  - `POST /simulateur/trial-credit-vend-request`
  - `GET /simulateur/cert-info`
  - `GET /simulateur/` (optionnel, peut rester public)
- [ ] Importer et injecter dans `simulateur_routers.py` :
  ```python
  from app.auth import get_current_user
  from app.models.models import User
  from fastapi import Depends

  @simulateur_router.post("/trial-credit-vend-request")
  async def trial_credit_vend_request(
      request: _ReqModel,
      current_user: User = Depends(get_current_user)
  ):
      ...
  ```
- [ ] Vérifier que les rôles autorisés sont restreints si nécessaire (ex : agents Senelec uniquement)

---

## 3. Sécurité générale (simulateur)

- [ ] Déplacer le mot de passe du PFX (`CERTIFICATE_PASSWORD`) dans les variables d'environnement (`.env`) — il ne doit pas être en dur dans le code
- [ ] Déplacer `CERTIFICATE_PATH` dans la config `.env` / `config.py` pour faciliter la rotation
- [ ] Retirer les credentials SOAP en dur dans `create_soap_request` (`opName`, `password`) — les mettre en variables d'environnement
