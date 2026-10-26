import pytest
from app.crypto.metadata import canonicalize_and_hash_metadata
from app.core.exceptions import AppException


def test_rfc8785_canonicalization_whitespace_and_key_ordering():
    """
    Validates RFC 8785: Objects with differing key order and irrelevant whitespace
    produce the exact same canonical UTF-8 bytes and Keccak-256 digest.
    """
    json_a = '{\n  "name": "Alice Smith",\n  "degree": "B.S. CS",\n  "gpa": 3.95\n}'
    json_b = '{"gpa":3.95,"degree":"B.S. CS","name":"Alice Smith"}'

    digest_a, canonical_a = canonicalize_and_hash_metadata(json_a)
    digest_b, canonical_b = canonicalize_and_hash_metadata(json_b)

    assert canonical_a == canonical_b
    assert digest_a == digest_b
    # Lexicographical key sorting: "degree", "gpa", "name"
    assert canonical_a == b'{"degree":"B.S. CS","gpa":3.95,"name":"Alice Smith"}'


def test_rfc8785_duplicate_keys_rejection():
    """
    Rejects duplicate JSON keys to prevent ambiguous deserialization or silent loss of data.
    """
    json_with_duplicates = '{"degree": "B.A.", "degree": "B.S."}'

    with pytest.raises(AppException) as exc_info:
        canonicalize_and_hash_metadata(json_with_duplicates)
    assert exc_info.value.error_code == "DUPLICATE_JSON_KEY"


def test_rfc8785_malformed_json_rejection():
    """
    Rejects malformed JSON syntax gracefully.
    """
    with pytest.raises(AppException) as exc_info:
        canonicalize_and_hash_metadata('{"unclosed": "string')
    assert exc_info.value.error_code == "INVALID_JSON_METADATA"


def test_rfc8785_unicode_normalization_and_escapes():
    """
    Validates UTF-8 encoding of Unicode and escaped characters.
    """
    json_unicode_raw = '{"name": "René Descartes", "city": "München"}'
    json_unicode_escaped = '{"city": "M\\u00fcnchen", "name": "Ren\\u00e9 Descartes"}'

    digest_raw, canonical_raw = canonicalize_and_hash_metadata(json_unicode_raw)
    digest_escaped, canonical_escaped = canonicalize_and_hash_metadata(json_unicode_escaped)

    assert canonical_raw == canonical_escaped
    assert digest_raw == digest_escaped
    assert "München".encode("utf-8") in canonical_raw


def test_rfc8785_numeric_handling():
    """
    Validates ECMAScript 6 numeric formatting rules (e.g. 1.0 -> 1, exponential formatting).
    """
    json_nums = '{"int": 42, "float_whole": 100.0, "exp": 1e6}'
    digest, canonical = canonicalize_and_hash_metadata(json_nums)

    # In RFC 8785, integers or whole floats without fraction format as integer representation
    assert b'"float_whole":100' in canonical
    assert b'"int":42' in canonical
    assert b'"exp":1000000' in canonical
