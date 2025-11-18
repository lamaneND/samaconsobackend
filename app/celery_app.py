from celery import Celery
from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# Configuration Celery avec RabbitMQ comme broker et Redis comme backend
# RabbitMQ: Meilleure gestion des queues, priorités et routage
# Redis: Stockage rapide des résultats
celery_app = Celery(
    "samaconso_notifications",
    broker=CELERY_BROKER_URL,      # RabbitMQ comme broker principal
    backend=CELERY_RESULT_BACKEND,  # Redis pour les résultats
    include=[
        "app.tasks.test_tasks",          # Tâches de test basiques
        "app.tasks.simple_tasks",        # Tâches simplifiées sans DB
        "app.tasks.notification_tasks",  # 🔥 PRODUCTION: Firebase + DB
        "app.tasks.batch_tasks"          # 🔥 PRODUCTION: Batch processing
    ]
)

# Configuration optimisée pour les notifications avec RabbitMQ
celery_app.conf.update(
    # Performance
    worker_prefetch_multiplier=4,
    task_acks_late=True,
    worker_disable_rate_limits=False,

    # Sérialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # TTL et retry
    task_default_retry_delay=60,
    task_max_retries=3,
    result_expires=3600,

    # RabbitMQ spécifique
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_heartbeat=30,
    broker_pool_limit=10,
    
    # Routage PRODUCTION pour toutes les tâches
    task_routes={
        # Tâches de test
        "send_simple_notification_test": {"queue": "normal"},
        "send_batch_test": {"queue": "normal"},
        "health_check": {"queue": "urgent"},
        "test_notification_simple": {"queue": "normal"},
        "test_firebase_notification": {"queue": "normal"},
        "test_batch_simple": {"queue": "normal"},
        
        # 🔥 TÂCHES PRODUCTION Firebase
        "send_single_notification": {"queue": "normal"},
        "send_urgent_notification": {"queue": "urgent"},
        "send_batch_notifications": {"queue": "high_priority"},
        "send_broadcast_notifications": {"queue": "low_priority"},
    },
    
    # Configuration des queues avec priorités
    task_create_missing_queues=True,
    task_default_queue="normal",
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Configuration PRODUCTION avec toutes les queues et priorités
celery_app.conf.task_routes.update({
    # Tâches de test
    'send_simple_notification_test': {
        'queue': 'normal',
        'priority': 5
    },
    'send_batch_test': {
        'queue': 'normal', 
        'priority': 5
    },
    'health_check': {
        'queue': 'urgent',
        'priority': 9
    },
    'test_notification_simple': {
        'queue': 'normal',
        'priority': 5
    },
    'test_firebase_notification': {
        'queue': 'normal',
        'priority': 6
    },
    'test_batch_simple': {
        'queue': 'normal',
        'priority': 4
    },
    
    # 🔥 TÂCHES PRODUCTION avec priorités optimisées
    'send_single_notification': {
        'queue': 'normal',
        'priority': 6
    },
    'send_urgent_notification': {
        'queue': 'urgent',
        'priority': 9
    },
    'send_batch_notifications': {
        'queue': 'high_priority',
        'priority': 7
    },
    'send_broadcast_notifications': {
        'queue': 'low_priority',
        'priority': 3
    }
})