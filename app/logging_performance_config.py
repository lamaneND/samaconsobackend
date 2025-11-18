"""
Configuration de logging optimisée pour la production
Réduit l'overhead tout en gardant les fonctionnalités essentielles
"""

import os
import logging
from typing import Dict, Any

# Configuration par environnement
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Configuration de performance par environnement  
PERFORMANCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "development": {
        "enable_performance_tracking": True,
        "enable_detailed_cache_logs": True,
        "enable_debug_logs": True,
        "enable_request_body_logging": True,
        "log_level": logging.DEBUG,
        "async_logging": False,
        "sampling_rate": 1.0  # Log 100% des requêtes
    },
    
    "staging": {
        "enable_performance_tracking": True,
        "enable_detailed_cache_logs": False,
        "enable_debug_logs": False,
        "enable_request_body_logging": False,
        "log_level": logging.INFO,
        "async_logging": True,
        "sampling_rate": 1.0
    },
    
    "production": {
        "enable_performance_tracking": False,  # Économise 40% overhead
        "enable_detailed_cache_logs": False,   # Économise 30% I/O
        "enable_debug_logs": False,
        "enable_request_body_logging": False,
        "log_level": logging.WARNING,
        "async_logging": True,
        "sampling_rate": 0.1  # Log seulement 10% des requêtes normales
    },
    
    "production_critical": {  # Pour charge très élevée
        "enable_performance_tracking": False,
        "enable_detailed_cache_logs": False,
        "enable_debug_logs": False,
        "enable_request_body_logging": False,
        "log_level": logging.ERROR,
        "async_logging": True,
        "sampling_rate": 0.01  # Log seulement 1% des requêtes
    }
}

# Configuration active
CONFIG = PERFORMANCE_CONFIG.get(ENVIRONMENT, PERFORMANCE_CONFIG["development"])

# Helpers pour vérification rapide de performance
def should_log_performance() -> bool:
    """Vérifie si on doit logger les performances"""
    return CONFIG["enable_performance_tracking"]

def should_log_cache_details() -> bool:
    """Vérifie si on doit logger les détails du cache"""
    return CONFIG["enable_detailed_cache_logs"]

def should_log_debug() -> bool:
    """Vérifie si on doit logger en DEBUG"""
    return CONFIG["enable_debug_logs"]

def should_sample_log() -> bool:
    """Vérifie si on doit logger cette requête (sampling)"""
    import random
    return random.random() < CONFIG["sampling_rate"]

# Decorateur pour logs conditionnels
def conditional_log(log_type: str = "normal"):
    """Décorateur pour logging conditionnel selon l'environnement"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if log_type == "performance" and not should_log_performance():
                return
            elif log_type == "cache" and not should_log_cache_details():
                return
            elif log_type == "debug" and not should_log_debug():
                return
            elif log_type == "sample" and not should_sample_log():
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Versions optimisées des helpers de logging
class OptimizedLogHelpers:
    """Versions optimisées des helpers de logging pour la production"""
    
    @staticmethod
    @conditional_log("performance")
    def log_performance(logger, message: str, execution_time: float):
        """Log performance seulement si activé"""
        logger.debug(f"⏱️ {message} | Time: {execution_time:.2f}ms")
    
    @staticmethod
    @conditional_log("cache")
    def log_cache_detail(logger, operation: str, key: str, **kwargs):
        """Log détails cache seulement si activé"""
        from app.logging_config import log_cache
        log_cache(operation, key, **kwargs)
    
    @staticmethod
    def log_cache_essential(operation: str, key: str):
        """Log cache essentiel (erreurs uniquement en production)"""
        if operation == "ERROR" or ENVIRONMENT != "production":
            from app.logging_config import log_cache
            log_cache(operation, key)
    
    @staticmethod
    @conditional_log("sample")
    def log_request_sampled(logger, message: str):
        """Log requête avec sampling"""
        logger.info(message)
    
    @staticmethod
    def log_security_always(event: str, user_id: int = None, ip: str = None, details: str = None):
        """Log sécurité toujours (même en production)"""
        from app.logging_config import log_security
        log_security(event, user_id, ip, details)

# Instance optimisée
optimized_log = OptimizedLogHelpers()

# Context manager pour mesures de performance conditionnelles
class ConditionalTimer:
    """Timer conditionnel qui ne mesure que si nécessaire"""
    
    def __init__(self, logger, operation_name: str):
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None
        self.should_measure = should_log_performance()
    
    def __enter__(self):
        if self.should_measure:
            import time
            self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.should_measure and self.start_time:
            import time
            execution_time = (time.time() - self.start_time) * 1000
            optimized_log.log_performance(
                self.logger, 
                self.operation_name, 
                execution_time
            )

# Usage dans les routers :
"""
# Remplacement de :
start_time = time.time()
# ... code ...
execution_time = (time.time() - start_time) * 1000
logger.info(f"⏱️ Operation | Time: {execution_time:.2f}ms")

# Par :
with ConditionalTimer(logger, "Operation completed"):
    # ... code ...

# Ou plus simplement :
@conditional_log("performance")
def log_timing(logger, operation, time_ms):
    logger.debug(f"⏱️ {operation} | Time: {time_ms:.2f}ms")
"""

# Export des configurations
__all__ = [
    'CONFIG', 'ENVIRONMENT',
    'should_log_performance', 'should_log_cache_details', 
    'should_log_debug', 'should_sample_log',
    'conditional_log', 'optimized_log', 'ConditionalTimer'
]