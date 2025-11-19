# Guide de Déploiement Optimisé (Architecture Distribuée)

Ce guide implémente l'architecture "Option 3" validée, enrichie avec Keepalived pour la haute disponibilité.

## Architecture Finale

*   **SRV-MOBAPPBD (10.101.1.212)**
    *   PostgreSQL 15 (Master) + PgBouncer
    *   MinIO Node 1 (Distribué)
*   **SRV-MOBAPP1 (10.101.1.210)**
    *   API (Gunicorn) + Celery Worker (High Priority)
    *   Redis (Master)
    *   RabbitMQ (Node 1)
    *   MinIO Node 2 (Distribué)
    *   Nginx + Keepalived (Master VIP)
*   **SRV-MOBAPP2 (10.101.1.211)**
    *   API (Gunicorn) + Celery Worker (Low Priority)
    *   Redis (Replica)
    *   RabbitMQ (Node 2)
    *   MinIO Node 3 (Distribué)
    *   Nginx + Keepalived (Backup VIP)

---

## Étape 0 : Préparation des Utilisateurs (Best Practice)

Pour éviter d'utiliser votre compte personnel (`admin.pcyn`), nous allons créer un utilisateur de service `samaconso` et un groupe pour les ingénieurs.

**Sur les 3 serveurs :**

1.  Créez l'utilisateur de service et le groupe :
    ```bash
    # Créer l'utilisateur système (sans login)
    sudo useradd -r -s /bin/false samaconso
    
    # Créer le groupe d'administration (si pas créé automatiquement)
    sudo groupadd samaconso-admins
    
    # Ajouter l'utilisateur de service au groupe docker (pour lancer les conteneurs)
    sudo usermod -aG docker samaconso
    ```

2.  Ajoutez-vous (et vos collègues) au groupe `samaconso-admins` et `docker` :
    ```bash
    # Remplacez admin.pcyn par votre user
    sudo usermod -aG samaconso-admins,docker admin.pcyn
    
    # Pour vos collègues :
    # sudo usermod -aG samaconso-admins,docker autre.ingenieur
    ```
    *Déconnectez-vous et reconnectez-vous pour que les groupes soient pris en compte.*

---

## Étape 1 : MinIO Distribué (Sur les 3 serveurs)

MinIO doit être installé nativement sur les 3 machines pour créer un cluster de stockage résilient.

**IMPORTANT:** Le script installe MinIO en mode standalone sur chaque serveur. Pour créer un cluster distribué:

1.  Copiez le script `install_minio_distributed.sh` sur les 3 serveurs.
2.  Exécutez-le sur chaque serveur (dans l'ordre: BD, SRV1, SRV2) :
    ```bash
    sudo bash install_minio_distributed.sh
    ```
3.  **Après le premier démarrage sur tous les serveurs**, modifiez `/etc/default/minio` sur chaque serveur pour activer le mode distribué:
    ```bash
    MINIO_VOLUMES="http://10.101.1.212:9000/data/minio http://10.101.1.210:9000/data/minio http://10.101.1.211:9000/data/minio"
    ```
4.  Redémarrez MinIO sur tous les serveurs:
    ```bash
    sudo systemctl restart minio
    ```

---

## Étape 2 : Base de Données (SRV-MOBAPPBD)

1.  Utilisez le dossier `database_server`.
2.  Installez Postgres :
    ```bash
    cd database_server
    sudo bash install_postgres.sh
    ```
    *(Note : Le fichier docker-compose.services.yml n'est plus nécessaire ici car Redis/RabbitMQ sont déplacés)*

---

## Étape 3 : Serveurs Applicatifs

### Sur SRV-MOBAPP1 (10.101.1.210)
1.  Utilisez le fichier `app_servers/docker-compose.srv1.yml` (renommez-le en `docker-compose.yml`).
2.  **Permissions :** Assurez-vous que les dossiers de logs appartiennent au groupe :
    ```bash
    mkdir -p logs uploaded_files
    sudo chown -R samaconso:samaconso-admins logs uploaded_files
    sudo chmod -R 775 logs uploaded_files
    ```
3.  Lancez : `docker-compose up -d`
3.  Installez Nginx et Keepalived (voir dossier `app_servers`).

### Sur SRV-MOBAPP2 (10.101.1.211)
1.  Utilisez le fichier `app_servers/docker-compose.srv2.yml` (renommez-le en `docker-compose.yml`).
2.  **Permissions :**
    ```bash
    mkdir -p logs uploaded_files
    sudo chown -R samaconso:samaconso-admins logs uploaded_files
    sudo chmod -R 775 logs uploaded_files
    ```
3.  Lancez : `docker-compose up -d`
3.  **Cluster RabbitMQ :** Une fois lancé, rejoignez le cluster :
    ```bash
    docker exec -it samaconso_rabbitmq rabbitmqctl stop_app
    docker exec -it samaconso_rabbitmq rabbitmqctl join_cluster rabbit@rabbitmq1
    docker exec -it samaconso_rabbitmq rabbitmqctl start_app
    ```
4.  Installez Nginx et Keepalived.

---

## Étape 4 : Vérification

1.  **API :** `http://10.101.1.250/health` (VIP Keepalived)
2.  **MinIO :** `http://10.101.1.212:9001` (Console) - Vous devriez voir 3 drives en ligne après configuration du cluster.
3.  **Redis :** Connectez-vous au Redis Master sur 10.101.1.210.
4.  **RabbitMQ :** Vérifiez le cluster via `http://10.101.1.210:15672` (admin/Senelec2024!)

## Notes Importantes

- **Keepalived:** Assure le failover automatique. Seul le serveur MASTER répond sur la VIP (10.101.1.250).
- **Nginx:** Configure pour pointer vers localhost:8000 sur chaque serveur. Pour un vrai load balancing distribué, voir `ANALYSE_ET_CORRECTIONS.md`.
- **Mots de passe:** Tous les mots de passe par défaut sont `Senelec2024!`. Changez-les en production!
- **IP Base de données:** Vérifiez que l'IP 10.101.1.212 est correcte (peut être 10.101.1.57 selon votre infrastructure).
