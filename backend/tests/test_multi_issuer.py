from types import SimpleNamespace
from unittest.mock import MagicMock
from threading import RLock
import pytest
from eth_account import Account
from pydantic import SecretStr
from app.core.config import settings
from app.core.exceptions import AppException
from app.blockchain.client import BlockchainClient
from app.blockchain import issuer_signers

ISSUER = '0x' + '02' * 32


def test_local_key_persistence_encryption_and_chain_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'STORAGE_ROOT_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'BLOCKCHAIN_ISSUER_PRIVATE_KEYS', {})
    chain = SimpleNamespace(chain_id=31337, issuer_registry_address='0x' + 'ab' * 20)
    account = issuer_signers.create_local_account(chain, ISSUER)
    assert issuer_signers.get_account(chain, ISSUER).address == account.address
    assert issuer_signers.create_local_account(chain, ISSUER).address == account.address
    assert account.key.hex() not in (tmp_path / 'issuer-signers.json.enc').read_text()
    chain.issuer_registry_address = '0x' + 'cd' * 20
    with pytest.raises(AppException):
        issuer_signers.get_account(chain, ISSUER)


def test_routing_does_not_replace_global_governance_signer(monkeypatch):
    primary, university = Account.create(), Account.create()
    monkeypatch.setattr(settings, 'BLOCKCHAIN_ISSUER_PRIVATE_KEYS', {ISSUER: SecretStr(university.key.hex())})
    client = BlockchainClient.__new__(BlockchainClient)
    client.signer_account, client.signer_address = primary, primary.address
    client.can_transact, client._tx_lock = True, RLock()
    seen = []
    def reject_after_check(self, expected):
        seen.append((self.signer_address, expected))
        return False, 'test rejection'
    monkeypatch.setattr(BlockchainClient, 'verify_signer_authorized_for_issuer', reject_after_check)
    result = client._credential_transaction('issueCredential', [], ISSUER)
    assert not result['success']
    assert seen == [(university.address, ISSUER)]
    assert client.signer_address == primary.address
    assert client.signer_account is primary


def test_activation_requires_admin(client, issuer_headers, holder_headers):
    for headers in (issuer_headers, holder_headers):
        assert client.post(f'/api/v1/issuers/{ISSUER}/activate-local', headers=headers).status_code == 403


def test_activation_rejects_external_chain_before_rpc(client, admin_headers, monkeypatch):
    from app.services import issuer_service
    chain = MagicMock(chain_id=11155111, rpc_url='https://example.invalid')
    monkeypatch.setattr(issuer_service, 'blockchain_client', chain)
    response = client.post(f'/api/v1/issuers/{ISSUER}/activate-local', headers=admin_headers)
    assert response.status_code == 403
    chain.is_connected.assert_not_called()


def test_production_does_not_load_local_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'STORAGE_ROOT_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'BLOCKCHAIN_ISSUER_PRIVATE_KEYS', {})
    monkeypatch.setattr(settings, 'AUTH_MODE', 'oidc')
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
    (tmp_path / 'issuer-signers.json.enc').write_text('not a valid keystore')
    assert issuer_signers.get_account(SimpleNamespace(), ISSUER) is None
