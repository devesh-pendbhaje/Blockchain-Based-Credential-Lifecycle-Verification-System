"""Issuer-scoped accounts; local provisioned keys are encrypted at rest."""
import json
import os
from pathlib import Path
from threading import RLock
from eth_account import Account
from app.core.config import settings
from app.core.exceptions import AppException
from app.schemas.common import validate_bytes32_hex
from app.storage.encryption import EnvelopeEncryption

provision_lock = RLock()


def _aad(client):
    return f'issuer-signers:v1:{client.chain_id}:{client.issuer_registry_address.lower()}'.encode()


def _path():
    return Path(settings.STORAGE_ROOT_DIR) / 'issuer-signers.json.enc'


def _read(client):
    path = _path()
    if not path.exists():
        return {}
    try:
        crypto = EnvelopeEncryption(bytes.fromhex(settings.STORAGE_ENCRYPTION_KEY))
        return json.loads(crypto.decrypt(json.loads(path.read_text()), expected_aad=_aad(client)))
    except Exception as exc:
        raise AppException('Cannot unlock issuer signing keys. Restore the matching storage key and chain configuration.',
                           'ISSUER_KEYSTORE_UNAVAILABLE', 503) from exc


def get_account(client, issuer_id):
    if not issuer_id:
        return None
    issuer_id = validate_bytes32_hex(issuer_id, allow_zero=False).lower()
    for configured_id, secret in settings.BLOCKCHAIN_ISSUER_PRIVATE_KEYS.items():
        if configured_id.lower() == issuer_id:
            try:
                return Account.from_key(secret.get_secret_value())
            except Exception as exc:
                raise AppException('Configured issuer signing key is invalid.', 'INVALID_ISSUER_SIGNER', 503) from exc
    # Local keys are never automatically loaded for an external deployment.
    if settings.is_local_dev:
        with provision_lock:
            key = _read(client).get(issuer_id)
            if key:
                return Account.from_key(key)
    return None


def create_local_account(client, issuer_id):
    """Caller must enforce local-chain and governance guards before invoking."""
    issuer_id = validate_bytes32_hex(issuer_id, allow_zero=False).lower()
    with provision_lock:
        existing = get_account(client, issuer_id)
        if existing:
            return existing
        keys = _read(client)
        account = Account.create()
        keys[issuer_id] = account.key.hex()
        envelope = EnvelopeEncryption(bytes.fromhex(settings.STORAGE_ENCRYPTION_KEY)).encrypt(
            json.dumps(keys).encode(), aad=_aad(client))
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(envelope, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        return account
