import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.logging import logger

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts" / "artifacts" / "contracts"
FALLBACK_DIR = Path(__file__).resolve().parent / "abi"


def _load_artifact(primary_path: Path, fallback_path: Path) -> Optional[Dict[str, Any]]:
    target = primary_path if primary_path.exists() else fallback_path
    if not target.exists():
        logger.warning(f"Artifact not found at {primary_path} or {fallback_path}")
        return None
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read artifact from {target}: {e}")
        return None


def get_issuer_registry_artifact() -> Optional[Dict[str, Any]]:
    primary = CONTRACTS_DIR / "IssuerRegistry.sol" / "IssuerRegistry.json"
    fallback = FALLBACK_DIR / "IssuerRegistry.json"
    return _load_artifact(primary, fallback)


def get_issuer_registry_abi() -> Optional[List[Dict[str, Any]]]:
    artifact = get_issuer_registry_artifact()
    return artifact.get("abi") if artifact else None


def get_credential_registry_artifact() -> Optional[Dict[str, Any]]:
    primary = CONTRACTS_DIR / "CredentialRegistry.sol" / "CredentialRegistry.json"
    fallback = FALLBACK_DIR / "CredentialRegistry.json"
    return _load_artifact(primary, fallback)


def get_credential_registry_abi() -> Optional[List[Dict[str, Any]]]:
    artifact = get_credential_registry_artifact()
    return artifact.get("abi") if artifact else None
