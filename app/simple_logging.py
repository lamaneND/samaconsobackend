"""
Système de logging simplifié pour SamaConso
Garde seulement l'essentiel : erreurs, sécurité, et événements critiques
"""
import logging
from typing import Optional

def get_simple_logger(name: str) -> logging.Logger:
    """Récupère un logger simple configuré"""
    return logging.getLogger(name)

def log_error(logger: logging.Logger, message: str, error: Exception = None):
    """Log d'erreur simple"""
    if error:
        logger.error(f"❌ {message} | Error: {str(error)}")
    else:
        logger.error(f"❌ {message}")

def log_security(event: str, user_id: Optional[int] = None, details: str = None):
    """Log d'événement de sécurité critique"""
    logger = get_simple_logger("app.security")
    user_info = f" | User: {user_id}" if user_id else ""
    details_info = f" | {details}" if details else ""
    logger.warning(f"🔒 {event}{user_info}{details_info}")

def log_success(logger: logging.Logger, operation: str):
    """Log de succès simple (seulement si nécessaire)"""
    logger.info(f"✅ {operation}")

# Export des fonctions essentielles
__all__ = ['get_simple_logger', 'log_error', 'log_security', 'log_success']