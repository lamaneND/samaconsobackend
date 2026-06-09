"""
Tests unitaires pour app/auth.py

Couvre les fonctions pures sans base de données ni réseau :
- Hachage et vérification des mots de passe / PIN
- Création et décodage des tokens JWT
- Création et vérification des refresh tokens
- Extraction de l'adresse IP client
"""

import pytest
from datetime import timedelta
from unittest.mock import MagicMock

from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    hash_refresh_token,
    verify_refresh_token,
    create_token_pair,
    get_client_ip,
)
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


# ── Hachage des mots de passe ─────────────────────────────────────────────────

class TestPasswordHashing:

    def test_hash_different_from_plaintext(self):
        hashed = get_password_hash("monmotdepasse")
        assert hashed != "monmotdepasse"

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = get_password_hash("monmotdepasse")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_two_hashes_of_same_password_are_different(self):
        """bcrypt utilise un sel aléatoire — deux hashs du même mot de passe diffèrent."""
        h1 = get_password_hash("memepassword")
        h2 = get_password_hash("memepassword")
        assert h1 != h2

    def test_verify_correct_password(self):
        password = "Senelec@2024"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_empty_password_against_hash(self):
        hashed = get_password_hash("quelquechose")
        assert verify_password("", hashed) is False

    def test_hash_and_verify_pin(self):
        pin = "1234"
        hashed_pin = get_password_hash(pin)
        assert verify_password(pin, hashed_pin) is True
        assert verify_password("9999", hashed_pin) is False


# ── Tokens JWT (access token) ─────────────────────────────────────────────────

class TestAccessToken:

    def test_create_access_token_returns_string(self):
        token = create_access_token(data={"sub": "42"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        token = create_access_token(data={"sub": "42"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_token_contains_expiry(self):
        token = create_access_token(data={"sub": "1"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_custom_expiry_is_respected(self):
        import jwt, time
        short_delta = timedelta(seconds=5)
        token = create_access_token(data={"sub": "7"}, expires_delta=short_delta)
        payload = decode_access_token(token)
        assert payload is not None
        # La date d'expiration doit être dans les prochaines secondes
        remaining = payload["exp"] - time.time()
        assert 0 < remaining <= 10

    def test_decode_invalid_token_returns_none(self):
        assert decode_access_token("ceci.nest.pas.un.token") is None

    def test_decode_token_with_wrong_secret_returns_none(self):
        import jwt
        token = jwt.encode({"sub": "1"}, "mauvaise_cle", algorithm=ALGORITHM)
        assert decode_access_token(token) is None

    def test_decode_expired_token_returns_none(self):
        expired_token = create_access_token(
            data={"sub": "1"},
            expires_delta=timedelta(seconds=-1),  # déjà expiré
        )
        assert decode_access_token(expired_token) is None

    def test_decode_empty_string_returns_none(self):
        assert decode_access_token("") is None


# ── Refresh token ─────────────────────────────────────────────────────────────

class TestRefreshToken:

    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token()
        assert isinstance(token, str)

    def test_create_refresh_token_length(self):
        """secrets.token_urlsafe(32) génère ~43 caractères."""
        token = create_refresh_token()
        assert len(token) >= 40

    def test_two_refresh_tokens_are_unique(self):
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2

    def test_refresh_token_is_url_safe(self):
        import re
        token = create_refresh_token()
        # URL-safe base64 : uniquement lettres, chiffres, - et _
        assert re.match(r'^[A-Za-z0-9_\-]+$', token)

    def test_hash_and_verify_refresh_token(self):
        token = create_refresh_token()
        hashed = hash_refresh_token(token)
        assert verify_refresh_token(token, hashed) is True

    def test_verify_wrong_refresh_token(self):
        token = create_refresh_token()
        hashed = hash_refresh_token(token)
        assert verify_refresh_token("mauvais_token", hashed) is False

    def test_hash_refresh_token_different_from_plain(self):
        token = create_refresh_token()
        hashed = hash_refresh_token(token)
        assert hashed != token


# ── Paire de tokens ───────────────────────────────────────────────────────────

class TestCreateTokenPair:

    def test_returns_tuple_of_two_strings(self):
        access, refresh = create_token_pair(user_id=1)
        assert isinstance(access, str)
        assert isinstance(refresh, str)

    def test_access_token_contains_user_id(self):
        access, _ = create_token_pair(user_id=99)
        payload = decode_access_token(access)
        assert payload["sub"] == "99"

    def test_refresh_token_is_not_jwt(self):
        """Le refresh token est un token opaque (pas un JWT)."""
        _, refresh = create_token_pair(user_id=1)
        # Un JWT contient 2 points séparant header.payload.signature
        parts = refresh.split(".")
        assert len(parts) != 3  # Pas un JWT


# ── Extraction de l'IP client ─────────────────────────────────────────────────

class TestGetClientIp:

    def _make_request(self, headers: dict, client_host: str = "192.168.1.1"):
        """Crée un mock de Request FastAPI."""
        mock_request = MagicMock()
        mock_request.headers = headers
        mock_request.client = MagicMock()
        mock_request.client.host = client_host
        return mock_request

    def test_returns_direct_ip_when_no_proxy_headers(self):
        req = self._make_request({}, client_host="10.0.0.5")
        assert get_client_ip(req) == "10.0.0.5"

    def test_x_forwarded_for_single_ip(self):
        req = self._make_request({"X-Forwarded-For": "203.0.113.5"})
        assert get_client_ip(req) == "203.0.113.5"

    def test_x_forwarded_for_chain_returns_first_ip(self):
        req = self._make_request({"X-Forwarded-For": "203.0.113.5, 10.0.0.1, 172.16.0.1"})
        assert get_client_ip(req) == "203.0.113.5"

    def test_x_real_ip_header(self):
        req = self._make_request({"X-Real-IP": "198.51.100.10"})
        assert get_client_ip(req) == "198.51.100.10"

    def test_x_forwarded_for_takes_priority_over_x_real_ip(self):
        req = self._make_request({
            "X-Forwarded-For": "203.0.113.5",
            "X-Real-IP": "198.51.100.10",
        })
        assert get_client_ip(req) == "203.0.113.5"

    def test_no_client_returns_unknown(self):
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None
        assert get_client_ip(mock_request) == "unknown"
