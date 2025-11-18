"""
Service MinIO pour la gestion du stockage de fichiers
"""
from minio import Minio
from minio.error import S3Error
from typing import BinaryIO, Optional
import io
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class MinioService:
    """Service pour gérer les opérations MinIO"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        bucket_name: str = "samaconso-uploads"
    ):
        """
        Initialise le client MinIO

        Args:
            endpoint: URL du serveur MinIO (ex: localhost:9000)
            access_key: Clé d'accès MinIO
            secret_key: Clé secrète MinIO
            secure: Utiliser HTTPS (True) ou HTTP (False)
            bucket_name: Nom du bucket par défaut
        """
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Crée le bucket s'il n'existe pas"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' créé avec succès")
            else:
                logger.info(f"Bucket '{self.bucket_name}' existe déjà")
        except S3Error as e:
            logger.error(f"Erreur lors de la création du bucket: {e}")
            raise

    def upload_file(
        self,
        file_data: BinaryIO,
        file_name: str,
        content_type: str = "application/octet-stream",
        bucket_name: Optional[str] = None
    ) -> dict:
        """
        Upload un fichier vers MinIO

        Args:
            file_data: Données du fichier (BinaryIO)
            file_name: Nom du fichier dans MinIO
            content_type: Type MIME du fichier
            bucket_name: Nom du bucket (utilise le bucket par défaut si None)

        Returns:
            dict: Informations sur le fichier uploadé
        """
        bucket = bucket_name or self.bucket_name

        try:
            # Lire les données du fichier
            file_data.seek(0, io.SEEK_END)
            file_size = file_data.tell()
            file_data.seek(0)

            # Upload le fichier
            result = self.client.put_object(
                bucket_name=bucket,
                object_name=file_name,
                data=file_data,
                length=file_size,
                content_type=content_type
            )

            logger.info(f"Fichier '{file_name}' uploadé avec succès dans '{bucket}'")

            return {
                "bucket": bucket,
                "object_name": file_name,
                "etag": result.etag,
                "size": file_size,
                "content_type": content_type,
                "url": self.get_file_url(file_name, bucket)
            }

        except S3Error as e:
            logger.error(f"Erreur lors de l'upload du fichier '{file_name}': {e}")
            raise

    def get_file(
        self,
        file_name: str,
        bucket_name: Optional[str] = None
    ) -> bytes:
        """
        Récupère un fichier depuis MinIO

        Args:
            file_name: Nom du fichier dans MinIO
            bucket_name: Nom du bucket (utilise le bucket par défaut si None)

        Returns:
            bytes: Contenu du fichier
        """
        bucket = bucket_name or self.bucket_name

        try:
            response = self.client.get_object(bucket, file_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data

        except S3Error as e:
            logger.error(f"Erreur lors de la récupération du fichier '{file_name}': {e}")
            raise

    def delete_file(
        self,
        file_name: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """
        Supprime un fichier de MinIO

        Args:
            file_name: Nom du fichier dans MinIO
            bucket_name: Nom du bucket (utilise le bucket par défaut si None)

        Returns:
            bool: True si suppression réussie
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.client.remove_object(bucket, file_name)
            logger.info(f"Fichier '{file_name}' supprimé avec succès de '{bucket}'")
            return True

        except S3Error as e:
            logger.error(f"Erreur lors de la suppression du fichier '{file_name}': {e}")
            raise

    def get_file_url(
        self,
        file_name: str,
        bucket_name: Optional[str] = None,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Génère une URL présignée pour accéder au fichier

        Args:
            file_name: Nom du fichier dans MinIO
            bucket_name: Nom du bucket (utilise le bucket par défaut si None)
            expires: Durée de validité de l'URL

        Returns:
            str: URL présignée
        """
        bucket = bucket_name or self.bucket_name

        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=file_name,
                expires=expires
            )
            return url

        except S3Error as e:
            logger.error(f"Erreur lors de la génération de l'URL pour '{file_name}': {e}")
            raise

    def list_files(
        self,
        prefix: str = "",
        bucket_name: Optional[str] = None
    ) -> list:
        """
        Liste les fichiers dans un bucket

        Args:
            prefix: Préfixe pour filtrer les fichiers
            bucket_name: Nom du bucket (utilise le bucket par défaut si None)

        Returns:
            list: Liste des fichiers
        """
        bucket = bucket_name or self.bucket_name

        try:
            objects = self.client.list_objects(bucket, prefix=prefix)
            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                })
            return files

        except S3Error as e:
            logger.error(f"Erreur lors de la liste des fichiers: {e}")
            raise

    def file_exists(
        self,
        file_name: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """
        Vérifie si un fichier existe dans MinIO

        Args:
            file_name: Nom du fichier dans MinIO
            bucket_name: Nom du bucket (utilise le bucket par défaut si None)

        Returns:
            bool: True si le fichier existe
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.client.stat_object(bucket, file_name)
            return True
        except S3Error:
            return False


# Instance globale du service MinIO (sera initialisée dans main.py)
minio_service: Optional[MinioService] = None


def get_minio_service() -> MinioService:
    """
    Récupère l'instance du service MinIO

    Returns:
        MinioService: Instance du service MinIO

    Raises:
        RuntimeError: Si le service n'est pas initialisé
    """
    if minio_service is None:
        raise RuntimeError("Service MinIO non initialisé. Appelez init_minio_service() d'abord.")
    return minio_service


def init_minio_service(
    endpoint: str,
    access_key: str,
    secret_key: str,
    secure: bool = False,
    bucket_name: str = "samaconso-uploads"
) -> MinioService:
    """
    Initialise le service MinIO

    Args:
        endpoint: URL du serveur MinIO
        access_key: Clé d'accès MinIO
        secret_key: Clé secrète MinIO
        secure: Utiliser HTTPS
        bucket_name: Nom du bucket par défaut

    Returns:
        MinioService: Instance du service MinIO
    """
    global minio_service
    minio_service = MinioService(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        bucket_name=bucket_name
    )
    logger.info("Service MinIO initialisé avec succès")
    return minio_service
