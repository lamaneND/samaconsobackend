"""
Middleware de logging pour SamaConso API
Logs automatiques des requêtes, réponses et performance
"""

import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.logging_config import get_logger, log_security

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware pour logger automatiquement toutes les requêtes API"""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.logger = get_logger("app.middleware.requests")
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json", "/favicon.ico"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Générer un ID unique pour la requête
        request_id = str(uuid.uuid4())[:8]
        
        # Informations de base de la requête
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Exclure certains endpoints du logging
        should_log = not any(excluded in path for excluded in self.exclude_paths)
        
        if should_log:
            # Extraire user_id si disponible dans les headers d'auth
            auth_header = request.headers.get("Authorization")
            if auth_header and "Bearer" in auth_header:
                # On pourrait décoder le JWT ici pour récupérer l'user_id
                # Mais pour l'instant, on log sans
                pass
            
            # Log de début de requête
            self.logger.info(f"🌐 [{request_id}] {method} {path} | IP: {client_ip} | User-Agent: {user_agent[:50]}...")
            
            # Log du body pour POST/PUT (première partie seulement)
            if method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.body()
                    if body:
                        body_str = body.decode('utf-8')[:200]
                        if len(body) > 200:
                            body_str += "..."
                        self.logger.debug(f"📝 [{request_id}] Request body: {body_str}")
                        
                        # Reconstruire la requête avec le body
                        request._body = body
                except Exception as e:
                    self.logger.warning(f"⚠️ [{request_id}] Could not read request body: {e}")
        
        # Traitement de la requête avec mesure de performance
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            if should_log:
                # Log de fin de requête
                status_code = response.status_code
                
                # Émoji selon le code de statut
                if 200 <= status_code < 300:
                    status_emoji = "✅"
                elif 300 <= status_code < 400:
                    status_emoji = "🔄"
                elif 400 <= status_code < 500:
                    status_emoji = "⚠️"
                else:
                    status_emoji = "❌"
                
                self.logger.info(f"{status_emoji} [{request_id}] {status_code} | {duration_ms:.2f}ms | {path}")
                
                # Log des requêtes lentes (> 2 secondes)
                if duration_ms > 2000:
                    self.logger.warning(f"🐌 [{request_id}] SLOW REQUEST | {duration_ms:.2f}ms | {method} {path}")
                
                # Log des erreurs 4xx/5xx
                if status_code >= 400:
                    log_security(f"HTTP {status_code} error", None, client_ip, f"{method} {path}")
                    
                    # Log du contenu de la réponse d'erreur
                    if hasattr(response, 'body'):
                        try:
                            response_body = getattr(response, 'body', b'')
                            if response_body:
                                body_str = response_body.decode('utf-8')[:300]
                                self.logger.error(f"📛 [{request_id}] Error response: {body_str}")
                        except Exception:
                            pass
            
            # Ajouter l'ID de requête dans les headers de réponse
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            if should_log:
                self.logger.error(f"💥 [{request_id}] EXCEPTION | {duration_ms:.2f}ms | {method} {path} | Error: {str(e)}")
                log_security("Request exception", None, client_ip, f"{method} {path} - {str(e)}")
            
            # Re-lever l'exception
            raise

class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware pour logger les événements de sécurité"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger("app.middleware.security")
        self.suspicious_patterns = [
            "SELECT", "UNION", "DROP", "DELETE", "INSERT", "UPDATE",  # SQL injection
            "<script>", "javascript:", "eval(", "alert(",  # XSS
            "../", "..\\", "/etc/passwd", "/windows/",  # Path traversal
            "admin", "root", "password", "123456"  # Brute force indicators
        ]
        self.rate_limit_tracker = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        # Détecter les patterns suspects dans l'URL
        if any(pattern.lower() in path.lower() for pattern in self.suspicious_patterns):
            log_security("Suspicious URL pattern detected", None, client_ip, f"Pattern in: {path}")
        
        # Détecter les patterns suspects dans les query parameters
        query_params = str(request.url.query)
        if query_params and any(pattern.lower() in query_params.lower() for pattern in self.suspicious_patterns):
            log_security("Suspicious query parameters", None, client_ip, f"Pattern in: {query_params[:100]}")
        
        # Rate limiting basique (tracking simple)
        current_time = time.time()
        if client_ip not in self.rate_limit_tracker:
            self.rate_limit_tracker[client_ip] = []
        
        # Nettoyer les anciennes entrées (plus de 1 minute)
        self.rate_limit_tracker[client_ip] = [
            t for t in self.rate_limit_tracker[client_ip] 
            if current_time - t < 60
        ]
        
        # Ajouter la requête actuelle
        self.rate_limit_tracker[client_ip].append(current_time)
        
        # Vérifier si trop de requêtes (> 100 par minute)
        if len(self.rate_limit_tracker[client_ip]) > 100:
            log_security("High request rate detected", None, client_ip, f"{len(self.rate_limit_tracker[client_ip])} requests/min")
        
        return await call_next(request)

# Export des middlewares
__all__ = ['RequestLoggingMiddleware', 'SecurityLoggingMiddleware']