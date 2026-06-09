"""
Sleutelbeheer voor de Kadaster KIK Inzage koppeling.
=====================================================
OAuth 2.0 Client Credentials Flow met signed JWT (private_key_jwt, RFC 7523):
- Onze backend ondertekent een JWT met een PRIVÉsleutel (RS256).
- Het Kadaster valideert die met de PUBLIEKE sleutel uit ons JWKS-endpoint.

De privésleutel staat als PEM in env var KADASTER_JWT_PRIVATE_KEY (geheim, in Render).
De publieke JWK wordt hier deterministisch uit afgeleid en publiek geserveerd via
GET /kadaster/jwks.json — die URL vul je in bij de KIK Inzage-aanvraag (JWKS URI).

Genereer een sleutelpaar met:  python -m kadaster.keys
"""

import os
import json
import base64
import hashlib
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ALG = "RS256"
ENV_PRIVATE_KEY = "KADASTER_JWT_PRIVATE_KEY"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_uint(value: int) -> str:
    """Positief integer → base64url zonder padding (JWK n/e formaat)."""
    length = (value.bit_length() + 7) // 8 or 1
    return _b64url(value.to_bytes(length, "big"))


def is_configured() -> bool:
    return bool(os.environ.get(ENV_PRIVATE_KEY))


@lru_cache(maxsize=1)
def load_private_key() -> rsa.RSAPrivateKey:
    pem = os.environ.get(ENV_PRIVATE_KEY)
    if not pem:
        raise RuntimeError(f"{ENV_PRIVATE_KEY} ontbreekt")
    # Render bewaart newlines soms als letterlijke \n — normaliseren.
    pem = pem.replace("\\n", "\n").strip()
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RuntimeError(f"{ENV_PRIVATE_KEY} is geen RSA-privésleutel")
    return key


def _jwk_thumbprint(n_b64: str, e_b64: str) -> str:
    """RFC 7638 JWK-thumbprint → stabiele, herleidbare kid."""
    canonical = json.dumps(
        {"e": e_b64, "kty": "RSA", "n": n_b64},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _b64url(hashlib.sha256(canonical).digest())


def public_jwk_from_key(private_key: rsa.RSAPrivateKey) -> dict:
    pub = private_key.public_key().public_numbers()
    n_b64 = _b64url_uint(pub.n)
    e_b64 = _b64url_uint(pub.e)
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": ALG,
        "kid": _jwk_thumbprint(n_b64, e_b64),
        "n": n_b64,
        "e": e_b64,
    }


@lru_cache(maxsize=1)
def public_jwk() -> dict:
    return public_jwk_from_key(load_private_key())


def jwks() -> dict:
    """Publieke JWKS (alleen de publieke sleutel)."""
    return {"keys": [public_jwk()]}


def generate_keypair(bits: int = 2048) -> tuple[str, dict]:
    """
    Genereer een nieuw RSA-sleutelpaar.

    Retourneert (private_key_pem, public_jwk). De PEM zet je in Render als
    KADASTER_JWT_PRIVATE_KEY; de JWK wordt automatisch via /kadaster/jwks.json
    geserveerd.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    return pem, public_jwk_from_key(private_key)


if __name__ == "__main__":
    # Lokaal sleutelpaar genereren. Schrijft de privésleutel NIET naar de repo.
    pem, jwk = generate_keypair()
    print("=== PRIVATE KEY (zet als KADASTER_JWT_PRIVATE_KEY in Render) ===")
    print(pem)
    print("=== PUBLIC JWK (ter controle, wordt via /kadaster/jwks.json geserveerd) ===")
    print(json.dumps({"keys": [jwk]}, indent=2))
