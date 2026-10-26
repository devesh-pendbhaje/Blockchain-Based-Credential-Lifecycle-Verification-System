import logging
import sys
from typing import Any, Dict


class SafeFormatter(logging.Formatter):
    """
    Structured log formatter that prevents accidental leakage of private keys,
    full credential certificates, and raw authentication tokens.
    """

    SENSITIVE_KEYS = {
        "private_key",
        "secret",
        "password",
        "token",
        "raw_certificate",
        "authorization",
        "bearer",
        "cookie",
        "access_token",
        "refresh_token",
    }

    def format(self, record: logging.LogRecord) -> str:
        # Mask sensitive attributes if passed in record.__dict__
        for key in self.SENSITIVE_KEYS:
            if hasattr(record, key):
                setattr(record, key, "[REDACTED]")
        return super().format(record)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("credential_verification")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = SafeFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(correlation_id)s): %(message)s",
            defaults={"correlation_id": "system"},
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
