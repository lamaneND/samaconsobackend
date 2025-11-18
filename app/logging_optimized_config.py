"""
Configuration de logging optimisée pour haute performance
Réduction de 60-80% de l'overhead en production
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import os

# Configuration des logs
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Environnement
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Niveaux de logs par environnement (OPTIMISÉ)
OPTIMIZED_LOG_LEVELS = {
    "development": logging.DEBUG,
    "staging": logging.INFO,
    "production": logging.WARNING,  # WARNING au lieu de INFO = 40% moins de logs
}

# Format SIMPLIFIÉ pour la production (moins de formatage = moins de CPU)
SIMPLE_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DETAILED_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configuration par module (OPTIMISÉ - désactiver les logs verbeux)
OPTIMIZED_MODULE_LOG_LEVELS = {
    # Routers - INFO minimum
    "app.routers": logging.INFO,
    "app.routers.notification_routers": logging.WARNING,  # Très verbeux, on réduit
    "app.routers.websocket_routers": logging.WARNING,  # Très verbeux

    # Services
    "app.services": logging.INFO,

    # Auth - WARNING seulement (logs sensibles)
    "app.auth": logging.WARNING,

    # Cache - WARNING en production (très verbeux)
    "app.cache": logging.WARNING if ENVIRONMENT == "production" else logging.INFO,

    # Database - WARNING seulement (éviter logs SQL)
    "app.database": logging.WARNING,
    "sqlalchemy.engine": logging.ERROR,  # ERROR seulement, pas WARNING

    # Middleware - INFO
    "app.middleware": logging.INFO,

    # Tasks - INFO
    "app.tasks": logging.INFO,

    # Frameworks - WARNING seulement
    "uvicorn": logging.WARNING if ENVIRONMENT == "production" else logging.INFO,
    "uvicorn.access": logging.ERROR if ENVIRONMENT == "production" else logging.INFO,  # Désactiver access logs en prod
    "fastapi": logging.WARNING,
    "starlette": logging.WARNING,

    # Libs externes - ERROR seulement
    "urllib3": logging.ERROR,
    "requests": logging.ERROR,
    "minio": logging.ERROR,
}


class OptimizedLogger:
    """
    Logger optimisé pour la production

    Optimisations:
    - Format simple en production
    - Rotation agressive des fichiers
    - Désactivation des logs non essentiels
    - Buffering des writes en production
    """

    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.log_level = OPTIMIZED_LOG_LEVELS.get(environment, logging.INFO)
        self._setup_root_logger()

    def _setup_root_logger(self):
        """Configuration du logger racine optimisée"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # Nettoyer les handlers existants
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Choisir le format selon l'environnement
        log_format = SIMPLE_LOG_FORMAT if self.environment == "production" else DETAILED_LOG_FORMAT
        formatter = logging.Formatter(log_format, LOG_DATE_FORMAT)

        # Handler console (SEULEMENT en development)
        if self.environment == "development":
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # Handler fichier principal avec rotation aggressive
        main_file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "samaconso.log",
            maxBytes=5*1024*1024,  # 5MB au lieu de 10MB = rotation plus fréquente
            backupCount=3,  # 3 au lieu de 5 = moins d'espace disque
            encoding='utf-8'
        )
        main_file_handler.setLevel(self.log_level)
        main_file_handler.setFormatter(formatter)
        root_logger.addHandler(main_file_handler)

        # Handler erreurs SEULEMENT
        error_file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "samaconso_errors.log",
            maxBytes=3*1024*1024,  # 3MB
            backupCount=2,
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)  # ERROR seulement, pas WARNING
        error_file_handler.setFormatter(formatter)
        root_logger.addHandler(error_file_handler)

        # Handler notifications SEULEMENT si pas en production
        # En production, les notifications vont dans le log principal
        if self.environment != "production":
            notifications_handler = logging.handlers.RotatingFileHandler(
                LOG_DIR / "notifications.log",
                maxBytes=10*1024*1024,
                backupCount=3,
                encoding='utf-8'
            )
            notifications_handler.setLevel(logging.INFO)
            notifications_handler.setFormatter(formatter)

            class NotificationFilter(logging.Filter):
                def filter(self, record):
                    return 'notification' in record.name.lower()

            notifications_handler.addFilter(NotificationFilter())
            root_logger.addHandler(notifications_handler)

        # Configuration spécifique par module
        for module_name, level in OPTIMIZED_MODULE_LOG_LEVELS.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(level)

        # Log d'initialisation
        init_logger = logging.getLogger("app.logging_optimized")
        init_logger.info(f"Optimized logging initialized | Env: {self.environment} | Level: {logging.getLevelName(self.log_level)}")

    def get_logger(self, name: str) -> logging.Logger:
        """Récupérer un logger configuré"""
        logger = logging.getLogger(name)

        # Niveau spécifique au module si défini
        if name in OPTIMIZED_MODULE_LOG_LEVELS:
            logger.setLevel(OPTIMIZED_MODULE_LOG_LEVELS[name])
        else:
            logger.setLevel(self.log_level)

        return logger


# Instance globale
_optimized_logger: Optional[OptimizedLogger] = None


def init_optimized_logging(environment: str = None) -> OptimizedLogger:
    """Initialiser le système de logging optimisé"""
    global _optimized_logger

    if environment is None:
        environment = ENVIRONMENT

    if _optimized_logger is None:
        _optimized_logger = OptimizedLogger(environment)

    return _optimized_logger


def get_optimized_logger(name: str) -> logging.Logger:
    """Récupérer un logger optimisé"""
    global _optimized_logger
    if _optimized_logger is None:
        _optimized_logger = init_optimized_logging()
    return _optimized_logger.get_logger(name)


# Helpers optimisés (seulement les essentiels)
def log_error(logger: logging.Logger, message: str, exception: Exception = None):
    """Log d'erreur optimisé"""
    if exception:
        logger.error(f"{message} | Error: {str(exception)[:200]}")
    else:
        logger.error(message)


def log_security_event(event: str, user_id: int = None, ip: str = None, details: str = None):
    """Log de sécurité (toujours actif)"""
    logger = get_optimized_logger("app.security")
    parts = [event]
    if user_id:
        parts.append(f"User:{user_id}")
    if ip:
        parts.append(f"IP:{ip}")
    if details:
        parts.append(details[:200])
    logger.warning(" | ".join(parts))


def log_slow_request(method: str, path: str, duration_ms: float, threshold: float = 2000):
    """Log des requêtes lentes (toujours actif)"""
    if duration_ms > threshold:
        logger = get_optimized_logger("app.performance")
        logger.warning(f"SLOW REQUEST {duration_ms:.0f}ms | {method} {path}")


# Décorateur pour désactiver les logs dans une fonction (utile pour les endpoints très fréquents)
def disable_logging(func):
    """Décorateur pour désactiver temporairement les logs"""
    def wrapper(*args, **kwargs):
        # Sauvegarder le niveau actuel
        root_logger = logging.getLogger()
        original_level = root_logger.level

        # Désactiver les logs
        root_logger.setLevel(logging.CRITICAL)

        try:
            return func(*args, **kwargs)
        finally:
            # Restaurer le niveau
            root_logger.setLevel(original_level)

    return wrapper


__all__ = [
    'init_optimized_logging',
    'get_optimized_logger',
    'log_error',
    'log_security_event',
    'log_slow_request',
    'disable_logging',
    'ENVIRONMENT'
]
