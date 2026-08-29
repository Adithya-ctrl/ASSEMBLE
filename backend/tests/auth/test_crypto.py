from __future__ import annotations

import pytest

from app.auth import crypto
from app.auth.crypto import hash_password, is_supported_password_hash, token_digest, verify_password


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


def test_noncanonical_scrypt_base64_is_rejected_before_kdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = "Correct-Horse-42"
    encoded = hash_password(password, salt=b"\xfb" * 16)
    parts = encoded.split("$")

    alternate_alphabet = parts.copy()
    alternate_alphabet[4] = alternate_alphabet[4].replace("-", "+").replace("_", "/")

    alternate_salt_pad_bits = parts.copy()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    salt_character = alternate_salt_pad_bits[4][-3]
    alternate_salt_pad_bits[4] = (
        alternate_salt_pad_bits[4][:-3]
        + alphabet[alphabet.index(salt_character) | 1]
        + "=="
    )

    alternate_digest_pad_bits = parts.copy()
    digest_character = alternate_digest_pad_bits[5][-2]
    alternate_digest_pad_bits[5] = (
        alternate_digest_pad_bits[5][:-2]
        + alphabet[alphabet.index(digest_character) | 1]
        + "="
    )

    missing_padding = parts.copy()
    missing_padding[4] = missing_padding[4].rstrip("=")

    extra_padding = parts.copy()
    extra_padding[5] += "="

    punctuation = parts.copy()
    punctuation[4] = "!" + punctuation[4][1:]

    whitespace = parts.copy()
    whitespace[5] = whitespace[5][:-1] + " "

    oversized = parts.copy()
    oversized[4] = "A" * 10_000

    oversized_parameter = parts.copy()
    oversized_parameter[1] = "1" * 10_000

    def unexpected_scrypt(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("noncanonical records must be rejected before scrypt")

    monkeypatch.setattr(crypto.hashlib, "scrypt", unexpected_scrypt)
    for candidate in (
        alternate_alphabet,
        alternate_salt_pad_bits,
        alternate_digest_pad_bits,
        missing_padding,
        extra_padding,
        punctuation,
        whitespace,
        oversized,
        oversized_parameter,
    ):
        candidate_text = "$".join(candidate)
        assert not is_supported_password_hash(candidate_text)
        assert not verify_password(password, candidate_text)


@pytest.mark.parametrize(
    "salt",
    (
        b"",
        b"x" * 15,
        b"x" * 17,
        bytearray(b"x" * 16),
        memoryview(b"x" * 16),
        "sixteen-byte-salt",
    ),
)
def test_hash_password_rejects_non_exact_supplied_salt_before_kdf(
    monkeypatch: pytest.MonkeyPatch,
    salt: object,
) -> None:
    def unexpected_scrypt(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("invalid salts must be rejected before scrypt")

    monkeypatch.setattr(crypto.hashlib, "scrypt", unexpected_scrypt)
    with pytest.raises(ValueError, match="salt must be exactly 16 bytes"):
        hash_password("Correct-Horse-42", salt=salt)  # type: ignore[arg-type]


def test_hash_password_accepts_generated_and_exact_sixteen_byte_salts() -> None:
    password = "Correct-Horse-42"
    assert verify_password(password, hash_password(password))
    assert verify_password(password, hash_password(password, salt=b"x" * 16))


def test_token_digest_does_not_contain_raw_bearer() -> None:
    token = "opaque-secret-value"
    digest = token_digest(token)
    assert token not in digest
    assert len(digest) == 64
