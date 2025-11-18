"""
Configuration de base de données optimisée pour Docker
Utilise les variables d'environnement pour la flexibilité
"""
import sqlalchemy as _sql
from fastapi import Depends
import sqlalchemy.ext.declarative as _declarative
from sqlalchemy.orm import Session
import sqlalchemy.orm as _orm
import pyodbc
from typing import Annotated
import os
import logging

logger = logging.getLogger(__name__)

# ============= PostgreSQL (Base principale) =============
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:s3n3l3c123@10.101.1.171:5432/samaconso"
)

engine = _sql.create_engine(DATABASE_URL)
SessionLocal = _orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = _declarative.declarative_base()

def get_db_samaconso():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[_orm.Session, Depends(get_db_samaconso)]


# ============= SQL Server - Configuration via ENV =============

def _build_sql_server_connection_string(
    host: str,
    database: str,
    username: str,
    password: str,
    port: int = None,
    driver: str = "ODBC Driver 18 for SQL Server",
    trust_certificate: bool = True,
    encrypt: bool = False
) -> str:
    """
    Construit une chaîne de connexion SQL Server

    Args:
        host: Nom du serveur ou IP
        database: Nom de la base
        username: Utilisateur
        password: Mot de passe
        port: Port (optionnel, défaut None)
        driver: Driver ODBC (défaut: ODBC Driver 18)
        trust_certificate: Accepter les certificats auto-signés
        encrypt: Activer le chiffrement
    """
    conn_parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={host}" + (f",{port}" if port else ""),
        f"DATABASE={database}",
        f"UID={username}",
        f"PWD={password}",
    ]

    if trust_certificate:
        conn_parts.append("TrustServerCertificate=yes")

    if encrypt:
        conn_parts.append("Encrypt=yes")
    else:
        conn_parts.append("Encrypt=no")

    return ";".join(conn_parts) + ";"


# ============= SQL Server SIC =============
def get_db_connection_sic():
    """
    Connexion au serveur SIC (Client data)
    Utilise les variables d'environnement en priorité
    """
    try:
        # Configuration via variables d'environnement (Docker)
        host = os.getenv("SQL_SERVER_SIC_HOST", "srv-asreports")
        database = os.getenv("SQL_SERVER_SIC_DATABASE", "SIC")
        username = os.getenv("SQL_SERVER_SIC_USER", "stagiaireddes")
        password = os.getenv("SQL_SERVER_SIC_PASSWORD", "Senelec123")

        conn_str = _build_sql_server_connection_string(
            host=host,
            database=database,
            username=username,
            password=password,
            trust_certificate=True,
            encrypt=False
        )

        logger.info(f"🔌 Tentative de connexion SIC: {host}/{database}")
        conn = pyodbc.connect(conn_str, timeout=10)
        logger.info(f"✅ Connexion SIC réussie")
        return conn

    except pyodbc.Error as e:
        logger.error(f"❌ Erreur connexion SIC: {e}")
        # En Docker, afficher plus d'infos pour debug
        if os.getenv("DEBUG", "false").lower() == "true":
            logger.debug(f"Connection string (sans password): {conn_str.replace(password, '***')}")
        return None


# ============= SQL Server Postpaid =============
def get_db_connection_postpaid():
    """
    Connexion au serveur Postpaid (Factures)
    """
    try:
        host = os.getenv("SQL_SERVER_POSTPAID_HOST", "srv-commercial")
        port = int(os.getenv("SQL_SERVER_POSTPAID_PORT", "1433"))
        database = os.getenv("SQL_SERVER_POSTPAID_DATABASE", "HISTH2MC")
        username = os.getenv("SQL_SERVER_POSTPAID_USER", "commercial_dev")
        password = os.getenv("SQL_SERVER_POSTPAID_PASSWORD", "Senelec2023")

        conn_str = _build_sql_server_connection_string(
            host=host,
            database=database,
            username=username,
            password=password,
            port=port,
            trust_certificate=True,
            encrypt=False
        )

        logger.info(f"🔌 Tentative de connexion Postpaid: {host}:{port}/{database}")
        conn = pyodbc.connect(conn_str, timeout=10)
        logger.info(f"✅ Connexion Postpaid réussie")
        return conn

    except pyodbc.Error as e:
        logger.error(f"❌ Erreur connexion Postpaid: {e}")
        return None


# ============= SQL Server Postpaid Customer =============
def get_db_connection_postpaid_customer():
    """
    Connexion au serveur BI_ODS (Données clients postpaid)
    """
    try:
        host = os.getenv("SQL_SERVER_CUSTOMER_HOST", "srv-asreports")
        database = os.getenv("SQL_SERVER_CUSTOMER_DATABASE", "BI_ODS")
        username = os.getenv("SQL_SERVER_CUSTOMER_USER", "stagiaireddes")
        password = os.getenv("SQL_SERVER_CUSTOMER_PASSWORD", "Senelec123")

        conn_str = _build_sql_server_connection_string(
            host=host,
            database=database,
            username=username,
            password=password,
            trust_certificate=True,
            encrypt=False
        )

        logger.info(f"🔌 Tentative de connexion Customer: {host}/{database}")
        conn = pyodbc.connect(conn_str, timeout=10)
        logger.info(f"✅ Connexion Customer réussie")
        return conn

    except pyodbc.Error as e:
        logger.error(f"❌ Erreur connexion Customer: {e}")
        return None


# ============= Fonction de test de connectivité =============
def test_all_connections():
    """
    Teste toutes les connexions SQL Server
    Utile pour le démarrage et le monitoring
    """
    results = {
        "postgresql": False,
        "sql_server_sic": False,
        "sql_server_postpaid": False,
        "sql_server_customer": False,
    }

    # Test PostgreSQL
    try:
        with engine.connect() as conn:
            conn.execute(_sql.text("SELECT 1"))
            results["postgresql"] = True
            logger.info("✅ PostgreSQL: OK")
    except Exception as e:
        logger.error(f"❌ PostgreSQL: {e}")

    # Test SQL Server SIC
    conn_sic = get_db_connection_sic()
    if conn_sic:
        results["sql_server_sic"] = True
        conn_sic.close()

    # Test SQL Server Postpaid
    conn_postpaid = get_db_connection_postpaid()
    if conn_postpaid:
        results["sql_server_postpaid"] = True
        conn_postpaid.close()

    # Test SQL Server Customer
    conn_customer = get_db_connection_postpaid_customer()
    if conn_customer:
        results["sql_server_customer"] = True
        conn_customer.close()

    return results


# ============= Export pour compatibilité =============
if __name__ == "__main__":
    # Test de connectivité au démarrage
    print("🧪 Test de toutes les connexions...")
    results = test_all_connections()

    print("\n📊 Résultats:")
    for db, status in results.items():
        print(f"  {'✅' if status else '❌'} {db}")

    # Exit code pour Docker healthcheck
    import sys
    sys.exit(0 if all(results.values()) else 1)
