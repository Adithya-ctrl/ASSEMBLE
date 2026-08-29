"""Password and bearer-secret primitives with bounded parsing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets


SCRYPT_N = 1 << 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_MAXMEM = 64 * 1024 * 1024
SALT_BYTES = 16
TOKEN_BYTES = 32
_SALT_B64_LENGTH = len(base64.urlsafe_b64encode(bytes(SALT_BYTES)))
_DIGEST_B64_LENGTH = len(base64.urlsafe_b64encode(bytes(SCRYPT_DKLEN)))

USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])?$")


def normalize_username(value: str) -> str:
    normalized = value.strip().casefold()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("username must be 3-64 URL-safe characters and begin and end alphanumeric")
    return normalized


def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if not (3 <= len(normalized) <= 254) or normalized.count("@") != 1:
        raise ValueError("email must contain one @ and be at most 254 characters")
    local, domain = normalized.split("@", 1)
    if not local or not domain or "." not in domain or any(char.isspace() for char in normalized):
        raise ValueError("email is not valid")
    return normalized


def validate_password(value: str) -> str:
    if not (12 <= len(value) <= 128):
        raise ValueError("password must contain 12-128 characters")
    categories = (
        any(char.islower() for char in value),
        any(char.isupper() for char in value),
        any(char.isdigit() for char in value),
        any(not char.isalnum() for char in value),
    )
    if sum(categories) < 3:
        raise ValueError("password must use at least three character classes")
    if len(value.encode("utf-8")) > 1024:
        raise ValueError("password encoding is too large")
    return value


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    validate_password(password)
    if salt is not None and (not isinstance(salt, bytes) or len(salt) != SALT_BYTES):
        raise ValueError(f"salt must be exactly {SALT_BYTES} bytes")
    actual_salt = secrets.token_bytes(SALT_BYTES) if salt is None else salt
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )
    return "$".join(
        (
            "scrypt-v1",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(actual_salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def _decode_password_hash(encoded: object) -> tuple[bytes, bytes] | None:
    try:
        if not isinstance(encoded, str):
            return None
        algorithm, n_text, r_text, p_text, salt_text, digest_text = encoded.split("$")
        if (
            algorithm != "scrypt-v1"
            or (n_text, r_text, p_text) != (str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P))
            or len(salt_text) != _SALT_B64_LENGTH
            or len(digest_text) != _DIGEST_B64_LENGTH
        ):
            return None

        salt = base64.b64decode(
            salt_text.encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        expected = base64.b64decode(
            digest_text.encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        if len(salt) != SALT_BYTES or len(expected) != SCRYPT_DKLEN:
            return None
        if (
            base64.urlsafe_b64encode(salt).decode("ascii") != salt_text
            or base64.urlsafe_b64encode(expected).decode("ascii") != digest_text
        ):
            return None

        return salt, expected
    except (ValueError, TypeError, UnicodeError):
        return None


def is_supported_password_hash(encoded: object) -> bool:
    return _decode_password_hash(encoded) is not None


def verify_password(password: str, encoded: str) -> bool:
    try:
        decoded = _decode_password_hash(encoded)
        if decoded is None or len(password.encode("utf-8")) > 1024:
            return False
        salt, expected = decoded

        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
            maxmem=SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def new_bearer_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def opaque_bucket(*parts: str) -> str:
    return token_digest("\0".join(parts))
