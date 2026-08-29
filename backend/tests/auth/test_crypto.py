from __future__ import annotations

from app.auth.crypto import hash_password, token_digest, verify_password


def test_scrypt_hashes_are_salted_versioned_and_verify() -> None:
    password = "Correct-Horse-42"
    first = hash_password(password)
    second = hash_password(password)
    assert first.startswith("scrypt-v1$16384$8$1$")
    assert second.startswith("scrypt-v1$16384$8$1$")
    assert first != second
    assert verify_password(password, first)
    assert not verify_password("Wrong-Horse-42", first)


def test_forged_scrypt_parameters_and_malformed_encoding_fail_closed() -> None:
    encoded = hash_password("Correct-Horse-42")
    assert not verify_password("Correct-Horse-42", encoded.replace("$16384$", "$1048576$", 1))
    assert not verify_password("Correct-Horse-42", "scrypt-v1$malformed")


def test_token_digest_does_not_contain_raw_bearer() -> None:
    token = "opaque-secret-value"
    digest = token_digest(token)
    assert token not in digest
    assert len(digest) == 64
