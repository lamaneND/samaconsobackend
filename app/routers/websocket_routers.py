"""
WebSocket Router pour les notifications en temps réel
Gestionnaire dédié aux connexions WebSocket pour l'API Samaconso
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import logging
from datetime import datetime

from app.database import get_db_samaconso
from app.models.models import Notification, User, UserSession
from app.auth import decode_access_token
from app.cache import cache_delete
from app.config import CACHE_KEYS

logger = logging.getLogger(__name__)

websocket_router = APIRouter(prefix="/ws", tags=["websockets"])


class ConnectionManager:
    """Gestionnaire des connexions WebSocket"""
    
    def __init__(self):
        # Dictionnaire: user_id -> liste de connexions WebSocket
        self.active_connections: Dict[int, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accepter une nouvelle connexion WebSocket pour un utilisateur"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket. Total connections: {len(self.active_connections[user_id])}")
        
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Déconnecter un WebSocket d'un utilisateur"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                logger.info(f"User {user_id} disconnected. Remaining connections: {len(self.active_connections[user_id])}")
                
                # Supprimer la liste si elle est vide
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    
    async def send_personal_message(self, message: dict, user_id: int):
        """Envoyer un message à toutes les connexions d'un utilisateur spécifique"""
        if user_id in self.active_connections:
            # Copier la liste pour éviter les modifications concurrentes
            connections = self.active_connections[user_id].copy()
            disconnected_sockets = []
            
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send message to user {user_id}: {str(e)}")
                    disconnected_sockets.append(websocket)
                    
            # Nettoyer les connexions fermées
            for websocket in disconnected_sockets:
                self.disconnect(websocket, user_id)
                
    async def send_broadcast_message(self, message: dict):
        """Envoyer un message à tous les utilisateurs connectés"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)
            
    def get_user_connections_count(self, user_id: int) -> int:
        """Obtenir le nombre de connexions actives pour un utilisateur"""
        return len(self.active_connections.get(user_id, []))
        
    def get_total_connections(self) -> int:
        """Obtenir le nombre total de connexions actives"""
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_connected_users(self) -> List[int]:
        """Obtenir la liste des utilisateurs connectés"""
        return list(self.active_connections.keys())


# Instance globale du gestionnaire
manager = ConnectionManager()


async def authenticate_websocket(token: str, db: Session) -> User:
    """Authentifier un utilisateur via le token JWT pour WebSocket"""
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Token invalide")
            
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="User ID non trouvé dans le token")
            
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Utilisateur non trouvé")
            
        return user
    except Exception as e:
        logger.error(f"Erreur d'authentification WebSocket: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentification échouée")


async def send_initial_notifications(websocket: WebSocket, user_id: int, db: Session):
    """Envoyer les notifications récentes à la connexion"""
    try:
        # Récupérer les 50 dernières notifications non lues
        unread_notifs = db.query(Notification).filter(
            and_(
                Notification.for_user_id == user_id,
                Notification.is_read == False
            )
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        if unread_notifs:
            notifications_data = []
            for notif in unread_notifs:
                notifications_data.append({
                    "id": notif.id,
                    "type_notification_id": notif.type_notification_id,
                    "event_id": notif.event_id,
                    "by_user_id": notif.by_user_id,
                    "for_user_id": notif.for_user_id,
                    "title": notif.title,
                    "body": notif.body,
                    "is_read": notif.is_read,
                    "created_at": notif.created_at.strftime("%d/%m/%Y %H:%M:%S") if notif.created_at else None,
                })
            
            await websocket.send_json({
                "type": "initial_notifications",
                "notifications": notifications_data,
                "count": len(notifications_data),
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            await websocket.send_json({
                "type": "no_notifications",
                "message": "Aucune notification non lue",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des notifications initiales: {str(e)}")


async def mark_notification_read_ws(notif_id: int, user_id: int, db: Session, websocket: WebSocket):
    """Marquer une notification comme lue via WebSocket"""
    try:
        notif = db.query(Notification).filter(
            and_(
                Notification.id == notif_id,
                Notification.for_user_id == user_id
            )
        ).first()
        
        if notif:
            notif.is_read = True
            db.commit()
            
            # Invalider le cache
            try:
                await cache_delete(CACHE_KEYS["NOTIFICATIONS_ALL"])
                await cache_delete(CACHE_KEYS["NOTIFICATIONS_BY_USER"].format(user_id=user_id))
                await cache_delete(CACHE_KEYS["NOTIFICATIONS_UNREAD"].format(user_id=user_id))
            except Exception:
                pass
            
            await websocket.send_json({
                "type": "notification_marked_read",
                "notification_id": notif_id,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Notification non trouvée ou non autorisée",
                "notification_id": notif_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Erreur lors du marquage de la notification: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Erreur: {str(e)}",
            "notification_id": notif_id,
            "timestamp": datetime.utcnow().isoformat()
        })


@websocket_router.websocket("/notifications/{user_id}")
async def websocket_notifications_endpoint(websocket: WebSocket, user_id: int):
    """
    Endpoint WebSocket pour recevoir les notifications en temps réel
    Usage: ws://localhost:8000/ws/notifications/{user_id}?token=your_jwt_token
    """
    # Récupérer le token depuis les query parameters
    query_params = websocket.query_params
    token = query_params.get("token")
    
    if not token:
        await websocket.close(code=4001, reason="Token requis")
        return
    
    # Obtenir la session de base de données
    db = next(get_db_samaconso())
    
    # Authentification
    try:
        user = await authenticate_websocket(token, db)
        
        # Vérifier que l'user_id correspond au token
        if user.id != user_id:
            await websocket.close(code=4003, reason="User ID ne correspond pas au token")
            return
            
    except Exception as e:
        await websocket.close(code=4002, reason=f"Authentification échouée: {str(e)}")
        return
    
    # Connexion réussie
    await manager.connect(websocket, user_id)
    
    try:
        # Envoyer les notifications existantes non lues
        await send_initial_notifications(websocket, user_id, db)
        
        # Envoyer un message de confirmation de connexion
        await websocket.send_json({
            "type": "connection_confirmed",
            "message": f"Connecté aux notifications pour l'utilisateur {user_id}",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Boucle de maintien de la connexion
        while True:
            try:
                # Attendre les messages du client (ping/pong, commandes...)
                message = await websocket.receive_json()
                
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                elif message.get("type") == "request_notifications":
                    # Re-envoyer les notifications récentes
                    await send_initial_notifications(websocket, user_id, db)
                    
                elif message.get("type") == "mark_read":
                    # Marquer une notification comme lue
                    notif_id = message.get("notification_id")
                    if notif_id:
                        await mark_notification_read_ws(notif_id, user_id, db, websocket)
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Erreur lors de la réception du message WebSocket: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Erreur WebSocket pour user {user_id}: {str(e)}")
    finally:
        manager.disconnect(websocket, user_id)
        db.close()


@websocket_router.get("/status")
async def websocket_status():
    """Obtenir le statut des connexions WebSocket"""
    return {
        "status": "active",
        "total_connections": manager.get_total_connections(),
        "connected_users": len(manager.active_connections),
        "connected_user_ids": manager.get_connected_users(),
        "connections_per_user": {
            user_id: len(connections) 
            for user_id, connections in manager.active_connections.items()
        }
    }


async def notify_user_via_websocket(user_id: int, title: str, body: str, notification_id: int = None, event_id: int = None):
    """
    Fonction utilitaire pour envoyer une notification via WebSocket
    À appeler depuis les autres endpoints de création de notifications
    """
    try:
        notification_data = {
            "id": notification_id,
            "title": title,
            "body": body,
            "event_id": event_id,
            "created_at": datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S")
        }

        message = {
            "type": "new_notification",
            "notification": notification_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await manager.send_personal_message(message, user_id)
        logger.info(f"Notification WebSocket envoyée à l'utilisateur {user_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification WebSocket pour user {user_id}: {str(e)}")
        return False


async def broadcast_notification_via_websocket(notification_data: dict, user_ids: List[int] = None):
    """
    Diffuser une notification à plusieurs utilisateurs ou tous les utilisateurs connectés
    """
    try:
        message = {
            "type": "broadcast_notification", 
            "notification": notification_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if user_ids:
            # Envoyer à des utilisateurs spécifiques
            for user_id in user_ids:
                await manager.send_personal_message(message, user_id)
        else:
            # Diffusion générale
            await manager.send_broadcast_message(message)
            
        logger.info(f"Notification diffusée via WebSocket à {len(user_ids) if user_ids else 'tous les'} utilisateurs")
        return True
    except Exception as e:
        logger.error(f"Erreur diffusion notification WebSocket: {str(e)}")
        return False


# Fonction pour obtenir le manager depuis d'autres modules
def get_websocket_manager():
    """Obtenir l'instance du gestionnaire WebSocket"""
    return manager