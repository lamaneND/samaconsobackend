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
        try:
            self.client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            self.bucket_name = bucket_name
            self._ensure_bucket_exists()
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client with endpoint '{endpoint}': {e}")
            raise ValueError(f"MinIO initialization failed: {str(e)}") from e

    def _ensure_bucket_exists(self):
        """Crée le bucket s'il n'existe pas (avec gestion d'erreur non-bloquante)"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' créé avec succès")
            else:
                logger.info(f"Bucket '{self.bucket_name}' existe déjà")
        except S3Error as e:
            error_str = str(e)
            # Ne pas bloquer pour les erreurs de service indisponible
            if "503" in error_str or "Service Unavailable" in error_str:
                logger.warning(f"⚠️ MinIO service unavailable (503), continuing without bucket verification: {e}")
                logger.warning("⚠️ Application will continue without MinIO bucket verification")
            else:
                logger.error(f"Erreur S3 lors de la création du bucket: {e}")
                raise
        except Exception as e:
            # Pour les erreurs de connexion/timeout, ne pas bloquer le démarrage
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["503", "timeout", "connection", "unavailable", "refused"]):
                logger.warning(f"⚠️ MinIO connection issue (non-blocking): {e}")
                logger.warning("⚠️ Application will continue without MinIO bucket verification")
            else:
                logger.error(f"Erreur inattendue lors de la vérification du bucket: {e}")
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


def _clean_and_validate_endpoint(endpoint: str) -> str:
    """
    Nettoie et valide le format de l'endpoint MinIO
    
    Le client MinIO attend un format strict: "host:port" sans protocole.
    Pour les clusters distribués (endpoints séparés par des virgules),
    seul le premier endpoint sera utilisé car le client MinIO Python
    ne supporte qu'un seul endpoint à la fois.
    
    Args:
        endpoint: Endpoint brut (peut contenir http://, https://, ou plusieurs endpoints séparés par des virgules)
        
    Returns:
        str: Endpoint nettoyé au format host:port
        
    Raises:
        ValueError: Si l'endpoint n'est pas valide
    """
    if not endpoint or not isinstance(endpoint, str):
        raise ValueError("Endpoint MinIO ne peut pas être vide")
    
    # Nettoyer l'endpoint
    cleaned = endpoint.strip()
    
    # Retirer le protocole si présent
    if cleaned.startswith("http://"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("https://"):
        cleaned = cleaned[8:]
    
    # Retirer le slash final s'il existe
    cleaned = cleaned.rstrip("/")
    
    # Gérer les endpoints multiples (cluster distribué MinIO)
    # Le client MinIO Python ne supporte qu'un seul endpoint à la fois
    # Pour un cluster distribué, on utilise le premier endpoint
    # Le nœud MinIO gérera la communication avec le reste du cluster
    if "," in cleaned:
        endpoints_list = [e.strip() for e in cleaned.split(",") if e.strip()]
        if not endpoints_list:
            raise ValueError(f"Aucun endpoint valide trouvé dans: '{endpoint}'")
        
        if len(endpoints_list) > 1:
            logger.warning(
                f"Endpoint MinIO contient plusieurs adresses (cluster distribué): {endpoints_list}. "
                f"Le client MinIO Python ne supporte qu'un seul endpoint. "
                f"Utilisation du premier endpoint: '{endpoints_list[0]}'. "
                f"Le nœud MinIO gérera la communication avec le reste du cluster."
            )
        cleaned = endpoints_list[0]
    
    # Valider le format host:port
    if ":" not in cleaned:
        raise ValueError(
            f"Format d'endpoint MinIO invalide: '{endpoint}'. "
            f"Format attendu: 'host:port' (ex: 'localhost:9000' ou '10.101.1.212:9000')"
        )
    
    # Extraire host et port
    parts = cleaned.split(":", 1)
    host = parts[0].strip()
    port_str = parts[1].strip() if len(parts) > 1 else ""
    
    # Valider que le host n'est pas vide
    if not host:
        raise ValueError(f"Host MinIO ne peut pas être vide dans l'endpoint: '{endpoint}'")
    
    # Valider que le port n'est pas vide
    if not port_str:
        raise ValueError(f"Port MinIO ne peut pas être vide dans l'endpoint: '{endpoint}'")
    
    # Valider le port est un nombre valide
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError(f"Port invalide: {port}. Le port doit être entre 1 et 65535")
    except ValueError as e:
        if "invalid literal" in str(e).lower():
            raise ValueError(
                f"Port invalide dans l'endpoint MinIO '{endpoint}': '{port_str}' n'est pas un nombre valide"
            ) from e
        raise
    
    logger.debug(f"Endpoint MinIO nettoyé: '{endpoint}' -> '{cleaned}'")
    return cleaned


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
        endpoint: URL du serveur MinIO (peut être au format host:port, http://host:port, etc.)
        access_key: Clé d'accès MinIO
        secret_key: Clé secrète MinIO
        secure: Utiliser HTTPS
        bucket_name: Nom du bucket par défaut

    Returns:
        MinioService: Instance du service MinIO
        
    Raises:
        ValueError: Si l'endpoint est invalide ou si l'initialisation échoue
    """
    global minio_service
    
    # Log l'endpoint original pour debug
    logger.info(f"Initialisation MinIO avec endpoint original: '{endpoint}'")
    
    # Nettoyer et valider l'endpoint
    try:
        cleaned_endpoint = _clean_and_validate_endpoint(endpoint)
        logger.info(f"Endpoint MinIO nettoyé et validé: '{cleaned_endpoint}'")
    except ValueError as e:
        logger.error(f"Validation de l'endpoint MinIO échouée: {e}")
        raise
    
    # Valider les credentials
    if not access_key:
        raise ValueError("MinIO access_key est requis")
    if not secret_key:
        raise ValueError("MinIO secret_key est requis")
    
    try:
        minio_service = MinioService(
            endpoint=cleaned_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            bucket_name=bucket_name
        )
        logger.info("Service MinIO initialisé avec succès")
        return minio_service
    except Exception as e:
        logger.error(f"Échec de l'initialisation du service MinIO: {e}")
        logger.error(f"Endpoint utilisé: '{cleaned_endpoint}', Secure: {secure}")
        minio_service = None  # S'assurer que le service global est None en cas d'échec
        raise
