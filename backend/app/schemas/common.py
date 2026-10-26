import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator

BYTES32_HEX_REGEX = re.compile(r"^0x[0-9a-fA-F]{64}$")
ZERO_BYTES32 = "0x" + "0" * 64


def validate_bytes32_hex(v: str, allow_zero: bool = False) -> str:
    if not isinstance(v, str):
        raise ValueError("Must be a string")
    v_clean = v.strip().lower()
    if not BYTES32_HEX_REGEX.match(v_clean):
        raise ValueError("Must be a valid 0x-prefixed 32-byte hexadecimal string (66 characters total)")
    if not allow_zero and v_clean == ZERO_BYTES32:
        raise ValueError("Zero 32-byte identifier/digest is prohibited")
    return v_clean


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
