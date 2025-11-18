"""
Configuration centralisée des logs pour SamaConso API
Système de logs professionnel avec rotation, filtrage et formatage
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Optional

# Configuration des logs
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Niveaux de logs par environnement
LOG_LEVELS = {
    "development": logging.DEBUG,
    "staging": logging.INFO,
    "production": logging.WARNING
}

# Format des logs
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configuration par module
MODULE_LOG_LEVELS = {
    "app.routers.notification_routers": logging.INFO,
    "app.routers.auth_routers": logging.INFO,
    "app.routers.user_routers": logging.INFO,
    "app.routers.websocket_routers": logging.INFO,
    "app.tasks.notification_tasks": logging.INFO,
    "app.tasks.batch_tasks": logging.INFO,
    "app.auth": logging.WARNING,
    "app.cache": logging.INFO,
    "app.database": logging.WARNING,
    "sqlalchemy.engine": logging.WARNING,  # Éviter trop de logs SQL
    "uvicorn": logging.INFO,
    "fastapi": logging.INFO,
}

class ColoredFormatter(logging.Formatter):
    """Formateur avec couleurs pour la console"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Vert
        'WARNING': '\033[33m',   # Jaune
        'ERROR': '\033[31m',     # Rouge
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']
        
        # Colorer le nom du module
        if hasattr(record, 'name') and 'routers' in record.name:
            module_name = f"{log_color}{record.name.split('.')[-1]}{reset_color}"
        else:
            module_name = record.name
            
        # Format avec couleurs
        record.name = module_name
        formatted = super().format(record)
        
        return f"{log_color}{record.levelname:<8}{reset_color} | {formatted.split(' | ', 1)[1] if ' | ' in formatted else formatted}"

class SamaConsoLogger:
    """Gestionnaire centralisé des logs pour SamaConso"""
    
    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.log_level = LOG_LEVELS.get(environment, logging.INFO)
        self._loggers: Dict[str, logging.Logger] = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """Configuration du logger racine"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Nettoyer les handlers existants
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Handler console avec couleurs (development)
        if self.environment == "development":
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_formatter = ColoredFormatter(LOG_FORMAT, LOG_DATE_FORMAT)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # Handler fichier principal (tous les environnements)
        main_file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "samaconso.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
        main_file_handler.setFormatter(file_formatter)
        root_logger.addHandler(main_file_handler)
        
        # Handler erreurs séparé
        error_file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "samaconso_errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_file_handler)
        
        # Handler notifications séparé (haute fréquence)
        notifications_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "notifications.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=7,
            encoding='utf-8'
        )
        notifications_handler.setLevel(logging.INFO)
        notifications_handler.setFormatter(file_formatter)
        
        # Filtre pour les logs de notifications uniquement
        class NotificationFilter(logging.Filter):
            def filter(self, record):
                return 'notification' in record.name.lower() or 'fcm' in getattr(record, 'msg', '').lower()
        
        notifications_handler.addFilter(NotificationFilter())
        root_logger.addHandler(notifications_handler)
        
        # Configuration spécifique par module
        for module_name, level in MODULE_LOG_LEVELS.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Récupérer un logger configuré pour un module"""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            
            # Niveau spécifique au module si défini
            if name in MODULE_LOG_LEVELS:
                logger.setLevel(MODULE_LOG_LEVELS[name])
            else:
                logger.setLevel(self.log_level)
            
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def log_request(self, logger: logging.Logger, method: str, endpoint: str, 
                   user_id: Optional[int] = None, duration_ms: Optional[float] = None):
        """Log standardisé pour les requêtes API"""
        user_info = f" | User:{user_id}" if user_id else ""
        duration_info = f" | {duration_ms:.2f}ms" if duration_ms else ""
        logger.info(f"🌐 {method} {endpoint}{user_info}{duration_info}")
    
    def log_notification_sent(self, logger: logging.Logger, user_id: int, 
                            title: str, token_count: int, method: str = "FCM"):
        """Log standardisé pour les notifications envoyées"""
        logger.info(f"📨 {method} notification sent | User:{user_id} | Tokens:{token_count} | Title:'{title[:50]}'")
    
    def log_cache_operation(self, logger: logging.Logger, operation: str, 
                          key: str, hit: bool = None, ttl: int = None):
        """Log standardisé pour les opérations cache"""
        hit_info = f" | {'HIT' if hit else 'MISS'}" if hit is not None else ""
        ttl_info = f" | TTL:{ttl}s" if ttl else ""
        logger.debug(f"🗂️ Cache {operation.upper()} | {key}{hit_info}{ttl_info}")
    
    def log_database_operation(self, logger: logging.Logger, operation: str, 
                             table: str, count: int = None, duration_ms: float = None):
        """Log standardisé pour les opérations base de données"""
        count_info = f" | Count:{count}" if count is not None else ""
        duration_info = f" | {duration_ms:.2f}ms" if duration_ms else ""
        logger.debug(f"🗄️ DB {operation.upper()} | {table}{count_info}{duration_info}")
    
    def log_celery_task(self, logger: logging.Logger, task_name: str, 
                       task_id: str, status: str, duration_ms: float = None):
        """Log standardisé pour les tâches Celery"""
        duration_info = f" | {duration_ms:.2f}ms" if duration_ms else ""
        status_emoji = {"SUCCESS": "✅", "FAILURE": "❌", "PENDING": "⏳", "RETRY": "🔄"}.get(status, "📝")
        logger.info(f"{status_emoji} Celery {task_name} | {task_id} | {status}{duration_info}")
    
    def log_security_event(self, logger: logging.Logger, event: str, 
                          user_id: int = None, ip_address: str = None, details: str = None):
        """Log standardisé pour les événements de sécurité"""
        user_info = f" | User:{user_id}" if user_id else ""
        ip_info = f" | IP:{ip_address}" if ip_address else ""
        details_info = f" | {details}" if details else ""
        logger.warning(f"🔒 Security: {event}{user_info}{ip_info}{details_info}")

# Instance globale du gestionnaire de logs
_log_manager: Optional[SamaConsoLogger] = None

def init_logging(environment: str = "development") -> SamaConsoLogger:
    """Initialiser le système de logs"""
    global _log_manager
    if _log_manager is None:
        _log_manager = SamaConsoLogger(environment)
        
        # Log d'initialisation
        init_logger = _log_manager.get_logger("app.logging_config")
        init_logger.info(f"🚀 SamaConso logging system initialized | Environment: {environment}")
        init_logger.info(f"📁 Log directory: {LOG_DIR.absolute()}")
    
    return _log_manager

def get_logger(name: str) -> logging.Logger:
    """Récupérer un logger configuré"""
    global _log_manager
    if _log_manager is None:
        _log_manager = init_logging()
    return _log_manager.get_logger(name)

def get_log_manager() -> SamaConsoLogger:
    """Récupérer le gestionnaire de logs"""
    global _log_manager
    if _log_manager is None:
        _log_manager = init_logging()
    return _log_manager

# Helpers pour les logs fréquents
def log_api_request(endpoint: str, method: str = "GET", user_id: int = None, duration_ms: float = None):
    """Helper pour logger les requêtes API"""
    logger = get_logger("app.api.requests")
    get_log_manager().log_request(logger, method, endpoint, user_id, duration_ms)

def log_notification(user_id: int, title: str, token_count: int, method: str = "FCM"):
    """Helper pour logger les notifications"""
    logger = get_logger("app.notifications")
    get_log_manager().log_notification_sent(logger, user_id, title, token_count, method)

def log_cache(operation: str, key: str, hit: bool = None, ttl: int = None):
    """Helper pour logger les opérations cache"""
    logger = get_logger("app.cache")
    get_log_manager().log_cache_operation(logger, operation, key, hit, ttl)

def log_database(operation: str, table: str, count: int = None, duration_ms: float = None):
    """Helper pour logger les opérations DB"""
    logger = get_logger("app.database")
    get_log_manager().log_database_operation(logger, operation, table, count, duration_ms)

def log_security(event: str, user_id: int = None, ip_address: str = None, details: str = None):
    """Helper pour logger les événements de sécurité"""
    logger = get_logger("app.security")
    get_log_manager().log_security_event(logger, event, user_id, ip_address, details)

# Export des principales fonctions
__all__ = [
    'init_logging', 'get_logger', 'get_log_manager',
    'log_api_request', 'log_notification', 'log_cache', 
    'log_database', 'log_security'
]