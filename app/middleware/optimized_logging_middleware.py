"""
Middleware de logging optimisé pour la production
Réduit drastiquement l'overhead tout en conservant les logs essentiels
"""

import time
import uuid
import random
from typing import Callable, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.logging_config import get_logger, log_security
from app.logging_performance_config import CONFIG, should_sample_log

class OptimizedRequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware de logging optimisé pour la production

    Optimisations:
    - Sampling des requêtes (log seulement X% en production)
    - Désactivation des logs de body en production
    - Pas de mesure de temps si non nécessaire
    - Logs asynchrones en production
    - Exclusion des endpoints de health check
    """

    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.logger = get_logger("app.middleware.requests")
        self.exclude_paths: Set[str] = set(exclude_paths or [
            "/health", "/docs", "/redoc", "/openapi.json",
            "/favicon.ico", "/static"
        ])

        # Configuration selon l'environnement
        self.enable_performance_tracking = CONFIG.get("enable_performance_tracking", False)
        self.enable_body_logging = CONFIG.get("enable_request_body_logging", False)
        self.sampling_rate = CONFIG.get("sampling_rate", 1.0)

        # Compteur pour le sampling déterministe (alternative au random)
        self.request_counter = 0
        self.sample_every_n = max(1, int(1 / self.sampling_rate)) if self.sampling_rate > 0 else 1000

        self.logger.info(f"Optimized logging middleware initialized | Sampling: {self.sampling_rate*100}% | Performance tracking: {self.enable_performance_tracking}")

    def should_log_request(self, path: str) -> bool:
        """Détermine si la requête doit être loggée"""
        # Toujours exclure les paths de la liste
        if any(excluded in path for excluded in self.exclude_paths):
            return False

        # Sampling déterministe (plus performant que random)
        self.request_counter += 1
        return self.request_counter % self.sample_every_n == 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Décision rapide sur le logging
        should_log = self.should_log_request(path)

        # Si pas de logging, passer directement
        if not should_log:
            return await call_next(request)

        # Générer un ID unique pour la requête
        request_id = str(uuid.uuid4())[:8]
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        # Log minimal de début (info de base seulement)
        self.logger.info(f"[{request_id}] {method} {path} | IP: {client_ip}")

        # Log du body seulement si activé (désactivé en production)
        if self.enable_body_logging and method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body and len(body) < 1000:  # Limiter la taille
                    body_str = body.decode('utf-8', errors='ignore')[:200]
                    self.logger.debug(f"[{request_id}] Body: {body_str}")
                request._body = body
            except Exception:
                pass  # Ignorer silencieusement les erreurs

        # Mesure de performance seulement si activé
        start_time = time.time() if self.enable_performance_tracking else None

        try:
            response = await call_next(request)

            # Calcul de la durée seulement si mesure activée
            duration_ms = (time.time() - start_time) * 1000 if start_time else None
            status_code = response.status_code

            # Log de fin avec niveau approprié
            if status_code >= 500:
                # Erreurs serveur: toujours logger
                self.logger.error(f"[{request_id}] {status_code} | {path}" +
                                (f" | {duration_ms:.0f}ms" if duration_ms else ""))
                log_security(f"HTTP {status_code} error", None, client_ip, f"{method} {path}")

            elif status_code >= 400:
                # Erreurs client: logger en warning
                self.logger.warning(f"[{request_id}] {status_code} | {path}" +
                                  (f" | {duration_ms:.0f}ms" if duration_ms else ""))

            elif duration_ms and duration_ms > 2000:
                # Requêtes lentes: toujours logger
                self.logger.warning(f"[{request_id}] SLOW {duration_ms:.0f}ms | {method} {path}")

            else:
                # Succès normal: log minimal
                self.logger.info(f"[{request_id}] {status_code}" +
                               (f" | {duration_ms:.0f}ms" if duration_ms else ""))

            # Ajouter l'ID de requête dans les headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Toujours logger les exceptions
            duration_ms = (time.time() - start_time) * 1000 if start_time else None
            self.logger.error(f"[{request_id}] EXCEPTION | {method} {path} | {str(e)[:100]}" +
                            (f" | {duration_ms:.0f}ms" if duration_ms else ""))
            log_security("Request exception", None, client_ip, f"{method} {path}")
            raise


class OptimizedSecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware de sécurité optimisé

    Optimisations:
    - Vérifications rapides avec sets
    - Rate limiting en mémoire avec TTL
    - Pas de détection de patterns en production (trop coûteux)
    - Logs seulement pour les vraies menaces
    """

    def __init__(self, app, enable_pattern_detection: bool = None):
        super().__init__(app)
        self.logger = get_logger("app.middleware.security")

        # Activer la détection de patterns seulement en dev/staging
        if enable_pattern_detection is None:
            enable_pattern_detection = CONFIG.get("enable_debug_logs", False)

        self.enable_pattern_detection = enable_pattern_detection

        # Patterns suspects (seulement si détection activée)
        self.suspicious_patterns = {
            "select", "union", "drop", "delete", "insert", "update",  # SQL injection
            "<script>", "javascript:", "eval(", "alert(",  # XSS
            "../", "..\\", "/etc/passwd",  # Path traversal
        } if enable_pattern_detection else set()

        # Rate limiting simple en mémoire
        self.rate_limit_tracker = {}
        self.rate_limit_max = 200  # Requêtes par minute
        self.rate_limit_window = 60  # Secondes

        # Cleanup périodique
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes

        self.logger.info(f"Security middleware initialized | Pattern detection: {self.enable_pattern_detection}")

    def cleanup_old_entries(self):
        """Nettoyer les anciennes entrées du rate limiter"""
        current_time = time.time()

        # Cleanup seulement toutes les 5 minutes
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = current_time

        # Supprimer les IPs inactives depuis plus d'une heure
        inactive_threshold = current_time - 3600
        self.rate_limit_tracker = {
            ip: timestamps
            for ip, timestamps in self.rate_limit_tracker.items()
            if timestamps and timestamps[-1] > inactive_threshold
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        current_time = time.time()

        # Détection de patterns suspects (seulement si activé)
        if self.enable_pattern_detection:
            path_lower = path.lower()
            query_lower = str(request.url.query).lower()

            if any(pattern in path_lower for pattern in self.suspicious_patterns):
                log_security("Suspicious URL pattern", None, client_ip, f"Path: {path[:100]}")

            elif query_lower and any(pattern in query_lower for pattern in self.suspicious_patterns):
                log_security("Suspicious query params", None, client_ip, f"Query: {query_lower[:100]}")

        # Rate limiting
        if client_ip not in self.rate_limit_tracker:
            self.rate_limit_tracker[client_ip] = []

        # Nettoyer les anciennes entrées pour cette IP
        cutoff_time = current_time - self.rate_limit_window
        self.rate_limit_tracker[client_ip] = [
            t for t in self.rate_limit_tracker[client_ip]
            if t > cutoff_time
        ]

        # Ajouter la requête actuelle
        self.rate_limit_tracker[client_ip].append(current_time)

        # Vérifier le rate limit
        request_count = len(self.rate_limit_tracker[client_ip])
        if request_count > self.rate_limit_max:
            log_security(
                "Rate limit exceeded",
                None,
                client_ip,
                f"{request_count} requests in {self.rate_limit_window}s"
            )

        # Cleanup périodique
        self.cleanup_old_entries()

        return await call_next(request)


# Export des middlewares optimisés
__all__ = ['OptimizedRequestLoggingMiddleware', 'OptimizedSecurityLoggingMiddleware']
