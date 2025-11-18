### JWT Keys
SECRET_KEY = "$3?N2LEC123"  
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

### Firebase Cloud Messaging

FCM_SERVER_KEY = "AAAA...."

#LDAP
LDAP_SERVER ="ldaps://electricite.sn"
# LDAP_SERVER='10.101.2.30'
LDAP_PORT =636
LDAP_BASE_DN ="DC=electricite,DC=sn"
LDAP_USER_DN="DC=electricite,DC=sn"
LDAP_DOMAIN=""
#LDAP_SEARCH_USER ="CN=service.samaconso,CN=Users,DC=electricite,DC=sn"
LDAP_SEARCH_USER ="CN=Service Sama Conso,CN=Users,DC=electricite,DC=sn"
#LDAP_SEARCH_USER ="service.samaconso"
LDAP_SEARCH_PASSWORD ="!!=++PT25@--ZmA"
# LDAP_SEARCH_USER = "CN=Service Appli ODM,CN=Users,DC=electricite,DC=sn"
# LDAP_SEARCH_PASSWORD = "PwD@0dM221!!svC"

# Cache & Messaging configuration
import os

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_DEFAULT_TTL_SECONDS = int(os.getenv("REDIS_DEFAULT_TTL_SECONDS", "300"))
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
REDIS_HEALTH_CHECK_INTERVAL = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))

# Cache Keys Patterns
CACHE_KEYS = {
    # Agences - données quasi-statiques
    "AGENCES_ALL": "agences:all",
    "AGENCE_BY_NAME": "agence:name:{name}",
    "AGENCE_BY_ID": "agence:id:{id}",
    
    # Users - données sensibles avec TTL modéré
    "USERS_ALL": "users:all",
    "USER_BY_PHONE": "user:phone:{phone}",
    "USER_BY_ID": "user:id:{id}",
    "USER_BY_LOGIN": "user:login:{login}",
    "USER_SESSIONS_ALL": "user_sessions:all",
    "USER_SESSION_BY_ID": "user_session:id:{id}",
    
    # Roles - données très statiques
    "ROLES_ALL": "roles:all",
    "ROLE_BY_LABEL": "role:label:{label}",
    "ROLE_BY_ID": "role:id:{id}",
    
    # Compteurs - données fréquemment consultées
    "COMPTEURS_ALL": "compteurs:all",
    "COMPTEUR_BY_NUMERO": "compteur:numero:{numero}",
    "COMPTEUR_BY_ID": "compteur:id:{id}",
    "USER_COMPTEURS": "user_compteurs:user:{user_id}",
    
    # Etats Compteur - données de référence
    "ETAT_COMPTEUR_ALL": "etat_compteur:all",
    "ETAT_COMPTEUR_BY_LABEL": "etat_compteur:label:{label}",
    
    # Types (données de référence - très statiques)
    "TYPE_COMPTEUR_ALL": "type_compteur:all",
    "TYPE_COMPTEUR_BY_LABEL": "type_compteur:label:{label}",
    "TYPE_NOTIFICATION_ALL": "type_notification:all",
    "TYPE_NOTIFICATION_BY_LABEL": "type_notification:label:{label}",
    "TYPE_DEMANDE_ALL": "type_demande:all",
    "TYPE_DEMANDE_BY_LABEL": "type_demande:label:{label}",
    
    # Demandes - données dynamiques
    "DEMANDES_ALL": "demandes:all",
    "DEMANDE_BY_ID": "demande:id:{id}",
    "DEMANDES_BY_USER": "demandes:user:{user_id}",
    "DEMANDES_BY_STATUS": "demandes:status:{status}",
    
    # Notifications - données très dynamiques
    "NOTIFICATIONS_ALL": "notifications:all",
    "NOTIFICATIONS_BY_USER": "notifications:user:{user_id}",
    "NOTIFICATIONS_UNREAD": "notifications:unread:user:{user_id}",
    
    # Postpaid & SIC - données externes
    "POSTPAID_TOP6_BILLS": "postpaid:top6bills:{numCC}",
    "POSTPAID_BILLS_BY_METER": "postpaid:bills:meter:{meter}",
    "SIC_CUSTOMER_BY_METER": "sic:customer:meter:{meter}",
    "SIC_CUSTOMER_BY_PHONE": "sic:customer:phone:{phone}",
    
    # Seuils & Tarifs - données de configuration
    "SEUIL_TARIF_ALL": "seuil_tarif:all",
    "SEUIL_TARIF_BY_TYPE": "seuil_tarif:type:{type}",
    
    # Dashboard - données agrégées
    "DASHBOARD_STATS": "dashboard:stats",
    "DASHBOARD_USER_STATS": "dashboard:stats:user:{user_id}",
}

# Cache TTL Configuration (en secondes)
CACHE_TTL = {
    # Données de référence (très statiques) - 2 heures
    "TYPE_ENTITIES": 7200,      # type_compteur, type_demande, type_notification
    "ROLES": 7200,              # roles
    "SEUIL_TARIF": 7200,        # seuils et tarifs
    
    # Données quasi-statiques - 1 heure
    "AGENCES": 3600,            # agences
    "ETAT_COMPTEUR": 3600,      # états compteurs
    
    # Données modérément dynamiques - 15 minutes
    "COMPTEURS": 900,           # compteurs
    "USERS": 900,               # utilisateurs (sécurité)
    
    # Données dynamiques - 5 minutes
    "DEMANDES": 300,            # demandes
    "USER_SESSIONS": 300,       # sessions utilisateurs
    "DASHBOARD": 300,           # statistiques dashboard
    
    # Données très dynamiques - 1 minute
    "NOTIFICATIONS": 60,        # notifications
    
    # Données externes - 30 secondes
    "EXTERNAL_APIs": 30,        # SIC, Postpaid
}

# RabbitMQ Configuration
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
RABBITMQ_DEFAULT_EXCHANGE = os.getenv("RABBITMQ_DEFAULT_EXCHANGE", "")  # default direct exchange
RABBITMQ_DEFAULT_QUEUE = os.getenv("RABBITMQ_DEFAULT_QUEUE", "samaconso.queue")

# Celery Configuration
# RabbitMQ as broker (message queue) - Redis as result backend (cache)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", RABBITMQ_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() in ("true", "1", "yes")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "samaconso-uploads")