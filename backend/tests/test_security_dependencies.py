"""Regresiones de autenticación para la actualización de dependencias."""

import pytest
import jwt

from app.core.config import settings
from app.core.security import decode_access_token, get_password_hash, verify_password


@pytest.mark.parametrize("prefix", ["2a", "2b", "2y"])
def test_hash_passlib_existente_conserva_acceso(prefix):
    """Los hashes sintéticos anteriores siguen verificándose sin regenerarlos."""
    encoded = f"${prefix}$12$abcdefghijklmnopqrstuu/Vsbzq8H1.Z/WxkqfYEa00eZi34KXfe"
    assert verify_password("prueba-sintetica", encoded)
    assert not verify_password("password-distinta", encoded)


def test_hash_unicode_largo_conserva_compatibilidad_bcrypt():
    """El límite histórico se aplica a bytes UTF-8, no a caracteres."""
    encoded = "$2b$12$abcdefghijklmnopqrstuu34OeXO/Y6zbOPhHdmLBuxHKKffYhJoq"
    assert verify_password("á" * 40, encoded)
    assert not verify_password("é" * 40, encoded)
    fresh = get_password_hash("contraseña-nueva")
    assert fresh.startswith("$2b$12$")
    assert verify_password("contraseña-nueva", fresh)


@pytest.mark.parametrize("password", ["a" * 4097, "a\x00b"])
def test_limites_anteriores_no_se_relajan(password):
    """Se conservan el máximo de entrada y el rechazo de caracteres nulos."""
    with pytest.raises(ValueError):
        get_password_hash(password)


@pytest.mark.parametrize("claim", ["exp", "iat", "nbf"])
@pytest.mark.parametrize("value", [None, [], {}])
def test_claim_temporal_malformado_es_rechazo_y_no_error_interno(claim, value):
    """PyJWT debe devolver un fallo de autenticación ante claims no numéricos."""
    token = jwt.encode(
        {"sub": "synthetic@example.test", claim: value},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(token) is None


def test_payload_jwt_profundo_es_rechazo_controlado():
    """Un JSON profundamente anidado no propaga RecursionError al servicio."""
    payload = b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"
    token = jwt.api_jws.encode(
        payload, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    assert decode_access_token(token) is None
