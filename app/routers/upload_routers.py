from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.minio_service import get_minio_service
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

upload_router = APIRouter(prefix="/upload", tags=["Upload"])


@upload_router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload un fichier vers MinIO

    Args:
        file: Fichier à uploader

    Returns:
        dict: Informations sur le fichier uploadé incluant l'URL d'accès
    """
    try:
        # Récupérer le service MinIO
        minio_service = get_minio_service()

        # Générer un nom de fichier unique pour éviter les collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{timestamp}_{unique_id}_{file.filename}"

        # Déterminer le type MIME
        content_type = file.content_type or "application/octet-stream"

        logger.info(f"Uploading file: {unique_filename} (type: {content_type})")

        # Upload vers MinIO
        result = minio_service.upload_file(
            file_data=file.file,
            file_name=unique_filename,
            content_type=content_type
        )

        logger.info(f"File uploaded successfully: {unique_filename}")

        return {
            "filename": file.filename,
            "stored_filename": unique_filename,
            "bucket": result["bucket"],
            "size": result["size"],
            "content_type": result["content_type"],
            "url": result["url"],
            "message": "Fichier enregistré avec succès dans MinIO"
        }

    except RuntimeError as e:
        logger.error(f"MinIO service not initialized: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service de stockage non disponible. MinIO n'est pas configuré."
        )
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'upload du fichier: {str(e)}"
        )


@upload_router.get("/file/{filename}")
async def get_file_url(filename: str):
    """
    Récupère l'URL présignée d'un fichier

    Args:
        filename: Nom du fichier dans MinIO

    Returns:
        dict: URL présignée pour accéder au fichier
    """
    try:
        minio_service = get_minio_service()
        url = minio_service.get_file_url(filename)

        return {
            "filename": filename,
            "url": url,
            "message": "URL générée avec succès"
        }

    except RuntimeError as e:
        logger.error(f"MinIO service not initialized: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service de stockage non disponible"
        )
    except Exception as e:
        logger.error(f"Error getting file URL: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Fichier non trouvé: {str(e)}"
        )


@upload_router.delete("/file/{filename}")
async def delete_file(filename: str):
    """
    Supprime un fichier de MinIO

    Args:
        filename: Nom du fichier dans MinIO

    Returns:
        dict: Confirmation de suppression
    """
    try:
        minio_service = get_minio_service()
        minio_service.delete_file(filename)

        logger.info(f"File deleted successfully: {filename}")

        return {
            "filename": filename,
            "message": "Fichier supprimé avec succès"
        }

    except RuntimeError as e:
        logger.error(f"MinIO service not initialized: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service de stockage non disponible"
        )
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la suppression du fichier: {str(e)}"
        )


@upload_router.get("/files")
async def list_files(prefix: str = ""):
    """
    Liste les fichiers dans MinIO

    Args:
        prefix: Préfixe pour filtrer les fichiers (optionnel)

    Returns:
        dict: Liste des fichiers
    """
    try:
        minio_service = get_minio_service()
        files = minio_service.list_files(prefix=prefix)

        return {
            "count": len(files),
            "files": files,
            "message": "Liste des fichiers récupérée avec succès"
        }

    except RuntimeError as e:
        logger.error(f"MinIO service not initialized: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service de stockage non disponible"
        )
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération de la liste des fichiers: {str(e)}"
        )
