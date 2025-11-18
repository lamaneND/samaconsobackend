"""
Configuration optimisée immédiate pour réduire l'overhead de logging
Garde les bénéfices essentiels tout en optimisant les performances
"""
import os
from app.logging_config import get_logger

# Détection automatique de l'environnement
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Configuration optimisée par défaut
OPTIMIZED_CONFIG = {
    # Performance tracking seulement en development
    "enable_performance_logs": ENVIRONMENT == "development",
    
    # Cache détails seulement en development/staging  
    "enable_cache_details": ENVIRONMENT in ["development", "staging"],
    
    # Logs DEBUG seulement en development
    "enable_debug_logs": ENVIRONMENT == "development", 
    
    # Sampling des logs INFO selon environnement
    "log_sampling_rate": {
        "development": 1.0,    # 100% des logs
        "staging": 0.5,        # 50% des logs
        "production": 0.1,     # 10% des logs seulement
        "critical": 0.01       # 1% des logs (urgence)
    }.get(ENVIRONMENT, 0.1),
    
    # Niveaux de logs par environnement
    "log_levels": {
        "development": "DEBUG", 
        "staging": "INFO",
        "production": "WARNING",  # Seulement erreurs/warnings
        "critical": "ERROR"       # Seulement erreurs
    }.get(ENVIRONMENT, "WARNING")
}

def should_log_performance() -> bool:
    """Vérifie si on doit faire le performance tracking"""
    return OPTIMIZED_CONFIG["enable_performance_logs"]

def should_log_cache_details() -> bool:
    """Vérifie si on doit logger les détails cache"""  
    return OPTIMIZED_CONFIG["enable_cache_details"]

def should_log_info() -> bool:
    """Vérifie si on doit logger cette requête INFO (sampling)"""
    import random
    return random.random() < OPTIMIZED_CONFIG["log_sampling_rate"]

# Versions optimisées des fonctions logging
class OptimizedLogging:
    """Versions optimisées pour réduire overhead"""
    
    @staticmethod
    def log_performance_conditional(logger, operation: str, start_time: float):
        """Log performance seulement si activé"""
        if should_log_performance():
            import time
            execution_time = (time.time() - start_time) * 1000
            logger.debug(f"⏱️ {operation} | Time: {execution_time:.2f}ms")
    
    @staticmethod  
    def log_info_sampled(logger, message: str):
        """Log INFO avec sampling selon environnement"""
        if should_log_info():
            logger.info(message)
    
    @staticmethod
    def log_cache_conditional(operation: str, key: str, **kwargs):
        """Log cache seulement si détails activés"""
        if should_log_cache_details():
            from app.logging_config import log_cache
            log_cache(operation, key, **kwargs)
        elif operation == "ERROR":  # Toujours logger les erreurs
            from app.logging_config import log_cache  
            log_cache(operation, key)
    
    @staticmethod
    def log_security_always(event: str, user_id=None, ip=None, details=None):
        """Logs de sécurité toujours actifs (critiques)"""
        from app.logging_config import log_security
        log_security(event, user_id, ip, details)

# Instance optimisée
optimized = OptimizedLogging()

# Context manager pour performance conditionnelle
class ConditionalPerformanceTracker:
    """Performance tracker qui ne mesure que si nécessaire"""
    
    def __init__(self, logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.should_track = should_log_performance()
        self.start_time = None
    
    def __enter__(self):
        if self.should_track:
            import time
            self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.should_track and self.start_time:
            optimized.log_performance_conditional(
                self.logger, self.operation, self.start_time
            )

# Exemple d'utilisation optimisée
def optimized_user_function_example():
    """Exemple de fonction optimisée"""
    logger = get_logger(__name__)
    
    # Performance tracking conditionnel (0ms overhead en production)
    with ConditionalPerformanceTracker(logger, "Get user operation"):
        
        # Log INFO avec sampling (90% de réduction en production)
        optimized.log_info_sampled(logger, "🆔 User request started")
        
        # ... logique métier ...
        
        # Cache logs conditionnels
        optimized.log_cache_conditional("HIT", "user:123")
        
        # Sécurité toujours loggée (important !)
        optimized.log_security_always("User access", 123, "192.168.1.1")
        
        # Succès avec sampling
        optimized.log_info_sampled(logger, "✅ User retrieved successfully")

# Export des outils optimisés
__all__ = [
    'OPTIMIZED_CONFIG', 'optimized', 'ConditionalPerformanceTracker',
    'should_log_performance', 'should_log_cache_details', 'should_log_info'
]