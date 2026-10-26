import json
from typing import Any, Tuple, Union
import rfc8785
from eth_utils import keccak
from app.core.exceptions import AppException


def _duplicate_key_detector(ordered_pairs):
    """
    RFC 8785 Section 3.1 & JSON specification constraint:
    Rejects duplicate JSON object keys to prevent silent data truncation or ambiguous interpretation.
    """
    res = {}
    for key, val in ordered_pairs:
        if key in res:
            raise ValueError(f"Duplicate JSON key detected: '{key}'")
        res[key] = val
    return res


def canonicalize_and_hash_metadata(
    metadata_input: Union[str, bytes, dict, list]
) -> Tuple[str, bytes]:
    """
    Parses and canonicalizes JSON metadata according to RFC 8785 (JSON Canonicalization Scheme - JCS).
    Computes Keccak-256 digest over the resulting canonical UTF-8 bytes.

    Returns:
        Tuple of (metadata_digest_hex, canonical_bytes)
    """
    if isinstance(metadata_input, (str, bytes)):
        try:
            if isinstance(metadata_input, bytes):
                metadata_str = metadata_input.decode("utf-8")
            else:
                metadata_str = metadata_input

            parsed_obj = json.loads(
                metadata_str,
                object_pairs_hook=_duplicate_key_detector,
            )
        except json.JSONDecodeError as exc:
            raise AppException(
                message=f"Malformed JSON metadata: {exc.msg} at line {exc.lineno} col {exc.colno}",
                error_code="INVALID_JSON_METADATA",
                status_code=400,
            ) from exc
        except ValueError as exc:
            raise AppException(
                message=str(exc),
                error_code="DUPLICATE_JSON_KEY",
                status_code=400,
            ) from exc
    elif isinstance(metadata_input, (dict, list)):
        parsed_obj = metadata_input
    else:
        raise AppException(
            message="Metadata input must be a JSON string, bytes, or parsed dict/list.",
            error_code="INVALID_METADATA_TYPE",
            status_code=400,
        )

    try:
        canonical_bytes = rfc8785.dumps(parsed_obj)
    except (rfc8785.CanonicalizationError, rfc8785.FloatDomainError, rfc8785.IntegerDomainError) as exc:
        raise AppException(
            message=f"RFC 8785 canonicalization failed: {str(exc)}",
            error_code="CANONICALIZATION_ERROR",
            status_code=400,
        ) from exc
    except Exception as exc:
        raise AppException(
            message=f"Failed to canonicalize metadata: {str(exc)}",
            error_code="CANONICALIZATION_ERROR",
            status_code=400,
        ) from exc

    digest_bytes = keccak(canonical_bytes)
    metadata_digest = "0x" + digest_bytes.hex().lower()

    return metadata_digest, canonical_bytes
