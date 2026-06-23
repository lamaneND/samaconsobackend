"""
Fixtures partagées pour la suite de tests SamaConso.

Stratégie :
- BDD de test : SQLite en mémoire (override de get_db_samaconso)
- Services externes mockés : Redis, RabbitMQ, MinIO (non disponibles hors réseau Senelec)
- Firebase : ignoré si le fichier credentials est absent (comportement natif)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# ── Base de données SQLite pour les tests ────────────────────────────────────
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./tests/test_samaconso.db"

engine_test = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

# Import anticipé de l'app pour que le module app.main soit résolu
# avant les patches (les fonctions mockées sont résolues à l'appel, pas à l'import)
import app.main as _main_module  # noqa: E402
from app.database import Base, get_db_samaconso  # noqa: E402


# ── Fixtures BDD ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_session():
    """
    Session SQLite isolée par test.
    Crée toutes les tables avant le test, les supprime après.
    """
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)


# ── Fixture client HTTP ───────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def client(db_session):
    """
    Client HTTP FastAPI avec :
    - BDD SQLite (override de get_db_samaconso)
    - Redis / RabbitMQ / MinIO mockés au niveau du module app.main
    """

    def override_get_db():
        yield db_session

    _main_module.app.dependency_overrides[get_db_samaconso] = override_get_db

    # Patch des services au niveau de app.main (là où on_startup les appelle)
    with patch("app.main.init_redis", new=AsyncMock(return_value=None)), \
         patch("app.main.close_redis", new=AsyncMock(return_value=None)), \
         patch("app.main.init_rabbitmq", new=AsyncMock(return_value=None)), \
         patch("app.main.init_minio_service", new=MagicMock(return_value=None)):

        with TestClient(_main_module.app, raise_server_exceptions=True) as test_client:
            yield test_client

    _main_module.app.dependency_overrides.clear()


# ── Fixtures données de test ──────────────────────────────────────────────────

@pytest.fixture
def plain_password() -> str:
    return "MotDePasse@2024"


@pytest.fixture
def plain_pin() -> str:
    return "4521"


@pytest.fixture
def test_user(db_session, plain_password, plain_pin):
    """
    Utilisateur actif en base SQLite avec login + téléphone.
    Utilisé par les tests d'intégration.
    """
    from app.models.models import User
    from app.auth import get_password_hash

    user = User(
        firstName="Amadou",
        lastName="Diallo",
        login="amadou.diallo",
        password=get_password_hash(plain_password),
        phoneNumber="771000001",
        codePin=get_password_hash(plain_pin),
        is_activate=True,
        ldap=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_tokens(client, test_user, plain_password):
    """
    Retourne (access_token, refresh_token) d'un login réussi.
    Pratique pour les tests qui ont besoin d'un utilisateur déjà connecté.
    """
    response = client.post(
        "/auth/token",
        data={"username": test_user.login, "password": plain_password},
    )
    assert response.status_code == 200, f"Login fixture failed: {response.text}"
    data = response.json()
    return data["access_token"], data["refresh_token"]
