import hashlib
import secrets
from functools import lru_cache
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError

password_hasher = PasswordHasher(type=Type.ID)


@lru_cache
def dummy_hash() -> str:
    return password_hasher.hash(secrets.token_urlsafe(32))


def verify_password(encoded: str | None, password: str) -> bool:
    try:
        valid = password_hasher.verify(encoded or dummy_hash(), password)
        return bool(encoded) and valid
    except (VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
