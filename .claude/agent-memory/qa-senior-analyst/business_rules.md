---
name: Règles métier critiques SamaConso
description: Règles de gestion authentification, sessions, compteurs, notifications découvertes en analyse QA
type: project
---

## Authentification

### Deux modes de login coexistent
- Login par `username` (login Senelec) + `password` → hashé bcrypt
- Login par `phoneNumber` + `codePin` → hashé bcrypt
- Agents LDAP : login + password via LDAP Active Directory (`ldaps://electricite.sn:636`)
- L'endpoint `/auth/token-json-v2` est le seul à gérer LDAP + local + téléphone
- L'endpoint `/auth/token-json` (corrigé BUG-001) gère login + téléphone SANS LDAP

### Sessions et refresh tokens
- Access token : JWT HS256, durée 30 minutes
- Refresh token : random string 32 bytes (`secrets.token_urlsafe`), hashé bcrypt, durée 7 jours
- Une session par device_model actif par utilisateur (si device_model fourni)
- Si device_model=None (OAuth2 /auth/token) : une nouvelle session créée à chaque login → accumulation possible
- Rotation des tokens : le refresh invalide l'ancien et en génère un nouveau
- Logout sans refresh_token = révocation de TOUTES les sessions de l'utilisateur

### Risque important : scan linéaire des sessions pour verify_refresh_token
- `/auth/refresh` charge TOUTES les sessions actives non expirées d'un utilisateur pour trouver le bon token
- Si un utilisateur a beaucoup de sessions (device_model=None répété), cela devient lent
- Pas d'index sur `refresh_token_hash` → full table scan possible en production

## Compteurs

### Association user-compteur
- `UserCompteur` : un user peut avoir plusieurs compteurs
- `est_proprietaire` : boolean — le propriétaire légal
- `est_active` : boolean — peut être désactivé
- `id_client` : identifiant client Senelec dans SIC/Postpaid
- TODO non implémenté dans `POST /user_compteur/` : vérification du téléphone dans SIC avant activation

## Sécurité

### SECRET_KEY et credentials en dur dans config.py
- `SECRET_KEY = "$3?N2LEC123"` → en clair dans le code source
- `LDAP_SEARCH_PASSWORD = "!!=++PT25@--ZmA"` → en clair dans le code source
- `FCM_SERVER_KEY = "AAAA...."` → valeur tronquée, valeur réelle probablement dans .env
- Ces valeurs sont dans le repo Git → risque si le repo est exposé

### CORS ouvert
- `allow_origins=["*"]` + `allow_credentials=False` → combinaison acceptée mais à restreindre en prod
- Tout domaine peut appeler l'API

### Endpoints non authentifiés critiques
- `/utils/publish` : publie un message dans la queue Redis → aucune auth requise
- `/utils/cache` (GET et POST) : lecture/écriture cache Redis → aucune auth requise
- `/utils/cache/flush` : suppression de clés Redis → protégé uniquement par un check sur `*`
- Ces endpoints doivent être protégés ou supprimés en production
