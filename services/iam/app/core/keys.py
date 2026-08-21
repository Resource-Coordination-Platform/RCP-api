"""RS256 signing-key management.

IAM is the only service holding the private key. Everyone else verifies
via the public JWKS document served at /.well-known/jwks.json.
The kid is a truncated SHA-256 thumbprint of the DER-encoded public key,
so key rotation (a new PEM file) automatically yields a new kid.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.hazmat.primitives import serialization

from app.core.config import settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _int_to_b64url(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return _b64url(value.to_bytes(length, "big"))


class KeyManager:
    def __init__(self, private_key_path: str):
        # Allow passing the PEM directly via env var (useful for ECS/Secrets Manager)
        import os
        pem_content = os.getenv("JWT_PRIVATE_KEY")
        if pem_content:
            key_bytes = pem_content.encode("utf-8")
        else:
            with open(private_key_path, "rb") as fh:
                key_bytes = fh.read()
        self._private_key = serialization.load_pem_private_key(key_bytes, password=None)

        public_key = self._private_key.public_key()
        der = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.kid = _b64url(hashlib.sha256(der).digest())[:16]

        self.private_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

        numbers = public_key.public_numbers()
        self.jwk = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": _int_to_b64url(numbers.n),
            "e": _int_to_b64url(numbers.e),
        }

    @property
    def jwks(self) -> dict:
        # on rotation, append the retiring public key here until all
        # tokens signed with it have expired
        return {"keys": [self.jwk]}


@lru_cache
def get_key_manager() -> KeyManager:
    return KeyManager(settings.JWT_PRIVATE_KEY_PATH)
