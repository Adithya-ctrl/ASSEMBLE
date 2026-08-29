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
    actual_salt = salt or secrets.token_bytes(SALT_BYTES)
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


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n_text, r_text, p_text, salt_text, digest_text = encoded.split("$")
        n, r, p = int(n_text), int(r_text), int(p_text)
        if algorithm != "scrypt-v1" or (n, r, p) != (SCRYPT_N, SCRYPT_R, SCRYPT_P):
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        if len(salt) != SALT_BYTES or len(expected) != SCRYPT_DKLEN or len(password.encode("utf-8")) > 1024:
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
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
