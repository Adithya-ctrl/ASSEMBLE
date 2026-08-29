"""Bounded scrypt and bearer-secret parser tests for the auth lane."""

from __future__ import annotations

import base64

import pytest

from app.auth import crypto


def test_scrypt_parser_rejects_noncanonical_base64_instead_of_accepting_ignored_bytes() -> None:
    password = "ParserBoundaryAa1!"
    encoded = crypto.hash_password(password)
    algorithm, n_text, r_text, p_text, salt_text, digest_text = encoded.split("$")

    # Python's permissive urlsafe_b64decode ignores punctuation.  Stored
    # records must not gain alternate encodings that bypass an integrity check.
    assert not crypto.verify_password(
        password,
        "$".join((algorithm, n_text, r_text, p_text, salt_text + "!", digest_text)),
    )
    assert not crypto.verify_password(
        password,
        "$".join((algorithm, n_text, r_text, p_text, salt_text, digest_text + "?")),
    )
    assert not crypto.verify_password(
        password,
        "$".join((algorithm, n_text, r_text, p_text, salt_text + "===", digest_text)),
    )


@pytest.mark.parametrize(
    "field,value",
    (
        (0, "scrypt-v2"),
        (1, "9" * 1000),
        (2, "9" * 1000),
        (3, "9" * 1000),
    ),
)
def test_scrypt_parser_rejects_forged_algorithm_or_unbounded_parameters_without_kdf(
    monkeypatch: pytest.MonkeyPatch,
    field: int,
    value: str,
) -> None:
    encoded = crypto.hash_password("ParserBoundaryAa1!")
    parts = encoded.split("$")
    parts[field] = value
    called = False

    def forbidden_scrypt(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("forged parameters must not invoke scrypt")

    monkeypatch.setattr(crypto.hashlib, "scrypt", forbidden_scrypt)
    assert not crypto.verify_password("ParserBoundaryAa1!", "$".join(parts))
    assert not called


def test_scrypt_parser_rejects_wrong_decoded_lengths_and_long_encoded_fields() -> None:
    password = "ParserBoundaryAa1!"
    encoded = crypto.hash_password(password)
    parts = encoded.split("$")
    short_salt = base64.urlsafe_b64encode(b"short").decode("ascii")
    short_digest = base64.urlsafe_b64encode(b"digest").decode("ascii")
    assert not crypto.verify_password(password, "$".join(parts[:4] + [short_salt, parts[5]]))
    assert not crypto.verify_password(password, "$".join(parts[:4] + [parts[4], short_digest]))
    assert not crypto.verify_password(password, "$".join(parts[:4] + ["A" * 100_000, parts[5]]))


def test_hash_password_enforces_the_declared_salt_size() -> None:
    with pytest.raises(ValueError, match="salt"):
        crypto.hash_password("ParserBoundaryAa1!", salt=b"short")
    with pytest.raises(ValueError, match="salt"):
        crypto.hash_password("ParserBoundaryAa1!", salt=b"x" * (crypto.SALT_BYTES + 1))


def test_bearer_factory_and_digest_boundaries_are_url_safe_and_nonreversible() -> None:
    token = crypto.new_bearer_token()
    assert len(token) >= crypto.TOKEN_BYTES
    assert all(character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for character in token)
    digest = crypto.token_digest(token)
    assert len(digest) == 64
    assert token not in digest
    assert crypto.opaque_bucket("auth-rate", "login", "client") != crypto.opaque_bucket(
        "auth-rate", "signup", "client"
    )
