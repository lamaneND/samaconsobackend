"""
Router pour la gestion et consultation des logs
Endpoints pour consulter les logs, statistiques et diagnostic
"""

from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
import os
from datetime import datetime, timedelta
# Removed unused imports
import re
from app.logging_config import get_logger

logs_router = APIRouter(prefix="/logs", tags=["logs"])
logger = get_logger(__name__)

LOG_DIR = Path("logs")

@logs_router.get("/files")
async def list_log_files():
    """Lister tous les fichiers de logs disponibles"""
    try:
        if not LOG_DIR.exists():
            return {"status": "error", "message": "Répertoire de logs non trouvé"}
        
        files = []
        for file_path in LOG_DIR.glob("*.log"):
            stat = file_path.stat()
            files.append({
                "name": file_path.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(file_path.absolute())
            })
        
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "status": "success",
            "log_directory": str(LOG_DIR.absolute()),
            "total_files": len(files),
            "files": files
        }
        
    except Exception as e:
        logger.error(f"Error listing log files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/tail/{filename}")
async def tail_log_file(
    filename: str, 
    lines: int = Query(default=100, ge=1, le=1000, description="Nombre de lignes à récupérer")
):
    """Récupérer les dernières lignes d'un fichier de log (comme tail -n)"""
    try:
        file_path = LOG_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Fichier {filename} non trouvé")
        
        if not file_path.suffix == '.log':
            raise HTTPException(status_code=400, detail="Seuls les fichiers .log sont autorisés")
        
        # Lire les dernières lignes
        with open(file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Prendre les n dernières lignes
        tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "status": "success",
            "filename": filename,
            "total_lines": len(all_lines),
            "returned_lines": len(tail_lines),
            "lines": [line.rstrip() for line in tail_lines]
        }
        
    except Exception as e:
        logger.error(f"Error tailing log file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/search/{filename}")
async def search_in_log_file(
    filename: str,
    pattern: str = Query(..., description="Pattern à rechercher (regex supporté)"),
    max_results: int = Query(default=50, ge=1, le=500),
    case_sensitive: bool = Query(default=False),
    regex: bool = Query(default=False, description="Utiliser pattern comme regex")
):
    """Rechercher dans un fichier de log"""
    try:
        file_path = LOG_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Fichier {filename} non trouvé")
        
        if not file_path.suffix == '.log':
            raise HTTPException(status_code=400, detail="Seuls les fichiers .log sont autorisés")
        
        matches = []
        line_number = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_number += 1
                line_content = line.rstrip()
                
                # Recherche
                if regex:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    if re.search(pattern, line_content, flags):
                        matches.append({
                            "line_number": line_number,
                            "content": line_content
                        })
                else:
                    search_line = line_content if case_sensitive else line_content.lower()
                    search_pattern = pattern if case_sensitive else pattern.lower()
                    
                    if search_pattern in search_line:
                        matches.append({
                            "line_number": line_number,
                            "content": line_content
                        })
                
                # Limiter les résultats
                if len(matches) >= max_results:
                    break
        
        return {
            "status": "success",
            "filename": filename,
            "pattern": pattern,
            "total_matches": len(matches),
            "max_results": max_results,
            "matches": matches
        }
        
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Erreur regex: {e}")
    except Exception as e:
        logger.error(f"Error searching in log file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/stats/notifications")
async def get_notification_log_stats():
    """Statistiques des logs de notifications"""
    try:
        notifications_log = LOG_DIR / "notifications.log"
        
        if not notifications_log.exists():
            return {"status": "warning", "message": "Fichier de logs notifications non trouvé"}
        
        stats = {
            "total_lines": 0,
            "fcm_sent": 0,
            "websocket_sent": 0,
            "errors": 0,
            "today": 0,
            "last_hour": 0,
            "by_level": {"INFO": 0, "WARNING": 0, "ERROR": 0, "DEBUG": 0}
        }
        
        now = datetime.now()
        today = now.date()
        hour_ago = now - timedelta(hours=1)
        
        with open(notifications_log, 'r', encoding='utf-8') as f:
            for line in f:
                stats["total_lines"] += 1
                
                # Analyser le niveau de log
                for level in stats["by_level"].keys():
                    if f" {level} " in line:
                        stats["by_level"][level] += 1
                        break
                
                # Compter les types de notifications
                if "FCM notification sent" in line:
                    stats["fcm_sent"] += 1
                elif "WebSocket" in line:
                    stats["websocket_sent"] += 1
                
                if "ERROR" in line:
                    stats["errors"] += 1
                
                # Analyser la date (format: YYYY-MM-DD HH:MM:SS)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if date_match:
                    try:
                        log_datetime = datetime.strptime(date_match.group(1), '%Y-%m-%d %H:%M:%S')
                        
                        if log_datetime.date() == today:
                            stats["today"] += 1
                        
                        if log_datetime >= hour_ago:
                            stats["last_hour"] += 1
                            
                    except ValueError:
                        pass
        
        return {
            "status": "success",
            "file": "notifications.log",
            "generated_at": now.isoformat(),
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error generating notification stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/stats/errors")
async def get_error_log_stats():
    """Statistiques des logs d'erreurs"""
    try:
        errors_log = LOG_DIR / "samaconso_errors.log"
        
        if not errors_log.exists():
            return {"status": "warning", "message": "Fichier de logs d'erreurs non trouvé"}
        
        stats = {
            "total_errors": 0,
            "today": 0,
            "last_hour": 0,
            "by_component": {},
            "recent_errors": []
        }
        
        now = datetime.now()
        today = now.date()
        hour_ago = now - timedelta(hours=1)
        
        with open(errors_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Analyser les dernières erreurs
        for line in reversed(lines[-100:]):  # Dernières 100 lignes
            if "ERROR" in line or "CRITICAL" in line:
                stats["total_errors"] += 1
                
                # Extraire le composant (entre les pipes)
                parts = line.split(" | ")
                if len(parts) >= 3:
                    component = parts[2].strip()
                    if component not in stats["by_component"]:
                        stats["by_component"][component] = 0
                    stats["by_component"][component] += 1
                
                # Analyser la date
                date_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if date_match:
                    try:
                        log_datetime = datetime.strptime(date_match.group(1), '%Y-%m-%d %H:%M:%S')
                        
                        if log_datetime.date() == today:
                            stats["today"] += 1
                        
                        if log_datetime >= hour_ago:
                            stats["last_hour"] += 1
                        
                        # Garder les 5 erreurs les plus récentes
                        if len(stats["recent_errors"]) < 5:
                            stats["recent_errors"].append({
                                "timestamp": log_datetime.isoformat(),
                                "message": line.strip()[:200] + "..." if len(line) > 200 else line.strip()
                            })
                            
                    except ValueError:
                        pass
        
        return {
            "status": "success",
            "file": "samaconso_errors.log",
            "generated_at": now.isoformat(),
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error generating error stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.delete("/cleanup")
async def cleanup_old_logs(days_old: int = Query(default=30, ge=1, le=365)):
    """Nettoyer les anciens fichiers de logs"""
    try:
        if not LOG_DIR.exists():
            return {"status": "warning", "message": "Répertoire de logs non trouvé"}
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        deleted_files = []
        total_size_freed = 0
        
        for file_path in LOG_DIR.glob("*.log*"):
            stat = file_path.stat()
            file_date = datetime.fromtimestamp(stat.st_mtime)
            
            if file_date < cutoff_date:
                file_size = stat.st_size
                os.remove(file_path)
                
                deleted_files.append({
                    "name": file_path.name,
                    "size_mb": round(file_size / 1024 / 1024, 2),
                    "modified": file_date.isoformat()
                })
                total_size_freed += file_size
        
        logger.info(f"Log cleanup completed: {len(deleted_files)} files deleted, {round(total_size_freed / 1024 / 1024, 2)} MB freed")
        
        return {
            "status": "success",
            "message": f"Nettoyage terminé: {len(deleted_files)} fichiers supprimés",
            "deleted_files": deleted_files,
            "total_size_freed_mb": round(total_size_freed / 1024 / 1024, 2),
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/live")
async def get_live_logs(
    filename: str = Query(default="samaconso.log"),
    last_lines: int = Query(default=20, ge=1, le=100)
):
    """Récupérer les logs en temps réel (dernières lignes)"""
    try:
        file_path = LOG_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Fichier {filename} non trouvé")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        recent_lines = lines[-last_lines:] if len(lines) > last_lines else lines
        
        return {
            "status": "success",
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "total_lines": len(lines),
            "showing_last": len(recent_lines),
            "logs": [line.rstrip() for line in recent_lines]
        }
        
    except Exception as e:
        logger.error(f"Error getting live logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export du router
__all__ = ['logs_router']