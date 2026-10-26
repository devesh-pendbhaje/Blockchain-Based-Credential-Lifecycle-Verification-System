import pytest
from unittest.mock import MagicMock, patch
from web3 import Web3
from eth_account import Account

from app.blockchain.abi_loader import (
    get_issuer_registry_abi,
    get_credential_registry_abi,
    get_issuer_registry_artifact,
    get_credential_registry_artifact,
)
from app.blockchain.client import BlockchainClient, sanitize_rpc_url
from app.crypto.fingerprint import compute_composite_fingerprint


# ==============================================================================
# 1. ABI LOADER & ARTIFACT TESTS
# ==============================================================================

def test_abi_loader_loads_real_and_fallback_artifacts():
    """
    Verifies that ABI loader successfully reads the compiled Hardhat artifacts
    or repository fallback ABIs for both IssuerRegistry and CredentialRegistry.
    """
    ir_art = get_issuer_registry_artifact()
    assert ir_art is not None
    assert "abi" in ir_art
    ir_abi = get_issuer_registry_abi()
    assert isinstance(ir_abi, list)
    ir_fns = [x["name"] for x in ir_abi if x.get("type") == "function"]
    assert "registerIssuer" in ir_fns
    assert "isIssuerActive" in ir_fns
    assert "getIssuer" in ir_fns
    assert "proposeSigningAddress" in ir_fns
    assert "acceptSigningAddress" in ir_fns

    cr_art = get_credential_registry_artifact()
    assert cr_art is not None
    assert "abi" in cr_art
    cr_abi = get_credential_registry_abi()
    assert isinstance(cr_abi, list)
    cr_fns = [x["name"] for x in cr_abi if x.get("type") == "function"]
    assert "issueCredential" in cr_fns
    assert "computeFingerprint" in cr_fns
    assert "verifyCredential" in cr_fns
    assert "suspendCredential" in cr_fns
    assert "reactivateCredential" in cr_fns
    assert "revokeCredential" in cr_fns
    assert "supersedeCredential" in cr_fns
    assert "getCredential" in cr_fns


# ==============================================================================
# 2. RPC URL SANITIZATION TESTS
# ==============================================================================

def test_rpc_url_sanitizer():
    """
    Ensures RPC API keys, tokens, and basic-auth credentials are masked
    before being exposed to logs or health probes.
    """
    # 1. Local node remains unmasked
    assert sanitize_rpc_url("http://127.0.0.1:8545") == "http://127.0.0.1:8545"

    # 2. Infura API key in path is masked
    infura_url = "https://sepolia.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161"
    sanitized_infura = sanitize_rpc_url(infura_url)
    assert "9aa3d95b3bc440fa88ea12eaa4456161" not in sanitized_infura
    assert sanitized_infura == "https://sepolia.infura.io/v3/***"

    # 3. Alchemy API key in path is masked
    alchemy_url = "https://eth-sepolia.g.alchemy.com/v2/demo1234567890abcdef"
    sanitized_alchemy = sanitize_rpc_url(alchemy_url)
    assert "demo1234567890abcdef" not in sanitized_alchemy
    assert sanitized_alchemy == "https://eth-sepolia.g.alchemy.com/v2/***"

    # 4. Basic Auth credentials masked
    auth_url = "https://alice:supersecretpassword@rpc.custom-node.org:8545"
    sanitized_auth = sanitize_rpc_url(auth_url)
    assert "supersecretpassword" not in sanitized_auth
    assert "alice" not in sanitized_auth
    assert sanitized_auth == "https://***:***@rpc.custom-node.org:8545"

    # 5. Empty or None handling
    assert sanitize_rpc_url("") == ""
    assert sanitize_rpc_url(None) == ""


# ==============================================================================
# 3. CONFIGURATION & NETWORK RESILIENCE TESTS
# ==============================================================================

def test_blockchain_client_graceful_handling_without_node():
    """
    When the EVM RPC node is unreachable, the client must fail closed,
    report unready contracts, and return safe empty/unavailable values.
    """
    client = BlockchainClient(rpc_url="http://127.0.0.1:59999", timeout=0.1)
    assert client.is_connected(force_refresh=True) is False
    assert client.get_connected_chain_id() is None
    assert client.is_contract_ready("credential") is False
    assert client.is_contract_ready("issuer") is False

    # Read-only verification returns None (unavailable)
    res = client.verify_credential_on_chain(
        fingerprint_hex="0x" + "11" * 32,
        doc_digest_hex="0x" + "22" * 32,
        meta_digest_hex="0x" + "33" * 32,
        merkle_root_hex="0x" + "44" * 32,
    )
    assert res is None

    # Issuer status returns unavailable tuple
    avail, is_active, status_name = client.get_issuer_status_on_chain("0x" + "55" * 32)
    assert avail is False
    assert is_active is None

    # Diagnostics report unavailable
    diag = client.get_diagnostics()
    assert diag["status"] == "unavailable"
    assert diag["rpc_connected"] is False
    assert diag["authoritative_verification_available"] is False


def test_blockchain_client_wrong_chain_id_blocked():
    """
    If connected chain ID does not match expected chain ID,
    all contract interactions and authoritative checks must be blocked.
    """
    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=11155111,  # Expect Sepolia
        timeout=1.0,
    )
    # Mock connected state on Ethereum Mainnet (Chain ID 1)
    client.w3 = MagicMock()
    client.w3.is_connected.return_value = True
    client.w3.eth.chain_id = 1  # Mismatched chain!

    assert client.is_connected(force_refresh=True) is True
    assert client.get_connected_chain_id(force_refresh=True) == 1

    # Contracts must NOT be marked ready when chain ID mismatches
    client.credential_contract = MagicMock()
    assert client.is_contract_ready("credential") is False

    diag = client.get_diagnostics(force_refresh=True)
    assert diag["status"] == "chain_id_mismatch"
    assert diag["chain_id_match"] is False
    assert diag["expected_chain_id"] == 11155111
    assert diag["actual_chain_id"] == 1
    assert diag["authoritative_verification_available"] is False


def test_blockchain_client_correct_chain_id():
    """
    When connected chain ID matches expected chain ID,
    chain_id_match is confirmed in diagnostics.
    """
    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=11155111,
        timeout=1.0,
    )
    client.w3 = MagicMock()
    client.w3.is_connected.return_value = True
    client.w3.eth.chain_id = 11155111

    assert client.is_connected(force_refresh=True) is True
    assert client.get_connected_chain_id(force_refresh=True) == 11155111
    diag = client.get_diagnostics(force_refresh=True)
    assert diag["chain_id_match"] is True


def test_contract_bytecode_validation():
    """
    Verifies that contract addresses are checked with eth_getCode.
    Addresses without deployed bytecode must be rejected.
    """
    client = BlockchainClient(rpc_url="http://127.0.0.1:8545", timeout=1.0)
    client.w3 = MagicMock()
    client.w3.is_connected.return_value = True

    dummy_addr = "0x5FbDB2315678afecb367f032d93F642f64180aa3"

    # 1. Non-empty bytecode returns True
    client.w3.eth.get_code.return_value = b"\x60\x80\x60\x40\x52\x34\x80\x15"
    assert client.has_contract_code(dummy_addr) is True

    # 2. Empty bytecode (EOA or undeployed) returns False
    client.w3.eth.get_code.return_value = b""
    assert client.has_contract_code(dummy_addr) is False

    client.w3.eth.get_code.return_value = b"0x"
    assert client.has_contract_code(dummy_addr) is False


def test_read_only_mode_without_signer():
    """
    When BLOCKCHAIN_SIGNER_PRIVATE_KEY is not configured, client operates in read-only mode.
    Write operations are blocked with clear error code SIGNER_NOT_CONFIGURED.
    """
    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=31337,
        signer_private_key=None,
    )
    assert client.can_transact is False
    assert client.signer_account is None
    assert client.signer_address is None

    # Attempting to register an issuer fails safely
    res_issuer = client.register_issuer_on_chain(
        issuer_id_hex="0x" + "11" * 32,
        signing_address="0x" + "22" * 20,
        metadata_uri="ipfs://example",
    )
    assert res_issuer["success"] is False
    assert res_issuer["status"] == "UNAVAILABLE"
    assert res_issuer["error"] == "SIGNER_NOT_CONFIGURED"

    # Attempting to anchor credential fails safely
    res_anchor = client.anchor_credential_fingerprint(
        credential_id_hex="0x" + "33" * 32,
        doc_digest_hex="0x" + "44" * 32,
        meta_digest_hex="0x" + "55" * 32,
        merkle_root_hex="0x" + "66" * 32,
        version=1,
    )
    assert res_anchor["success"] is False
    assert res_anchor["status"] == "UNAVAILABLE"
    assert res_anchor["error"] == "SIGNER_NOT_CONFIGURED"


def test_write_mode_with_configured_signer():
    """
    When a valid private key is provided, the client initializes the LocalAccount,
    derives the public address, and sets can_transact to True.
    """
    # Deterministic test private key (never funded, test only)
    test_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    expected_address = Account.from_key(test_key).address

    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=31337,
        signer_private_key=test_key,
    )
    assert client.can_transact is True
    assert client.signer_account is not None
    assert client.signer_address == expected_address


# ==============================================================================
# 4. CONTRACT INTEGRATION & MOCKED LIFECYCLE TESTS
# ==============================================================================

def test_mocked_contract_credential_anchoring_success():
    """
    Verifies that anchor_credential_fingerprint builds, signs, sends, and validates
    the transaction receipt and CredentialIssued event.
    """
    test_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=31337,
        signer_private_key=test_key,
    )
    client.w3 = MagicMock()
    client.w3.is_connected.return_value = True
    client.w3.eth.chain_id = 31337
    client.w3.eth.gas_price = 1000000000
    client.w3.eth.get_transaction_count.return_value = 0

    mock_contract = MagicMock()
    client.credential_contract = mock_contract
    client.credential_registry_address = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
    client.has_contract_code = MagicMock(return_value=True)

    # Mock tx build & send
    mock_func = MagicMock()
    mock_func.estimate_gas.return_value = 150000
    mock_func.build_transaction.return_value = {
        "from": client.signer_address,
        "nonce": 0,
        "gas": 187500,
        "gasPrice": 1000000000,
        "chainId": 31337,
    }
    mock_contract.functions.issueCredential.return_value = mock_func

    # Mock receipt
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_receipt.blockNumber = 42
    mock_receipt.gasUsed = 120000
    client.w3.eth.send_raw_transaction.return_value = b"\xaa" * 32
    client.w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    # Mock event parsing
    expected_fp = "0x" + "77" * 32
    mock_event = {"args": {"fingerprint": bytes.fromhex("77" * 32)}}
    mock_contract.events.CredentialIssued().process_receipt.return_value = [mock_event]

    res = client.anchor_credential_fingerprint(
        credential_id_hex="0x" + "11" * 32,
        doc_digest_hex="0x" + "22" * 32,
        meta_digest_hex="0x" + "33" * 32,
        merkle_root_hex="0x" + "44" * 32,
        version=1,
    )
    assert res["success"] is True
    assert res["status"] == "CONFIRMED"
    assert res["block_number"] == 42
    assert res["fingerprint"] == expected_fp


def test_mocked_contract_credential_anchoring_reverted():
    """
    Verifies that a reverted transaction (status == 0) is correctly captured
    and returned as status REVERTED.
    """
    test_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=31337,
        signer_private_key=test_key,
    )
    client.w3 = MagicMock()
    client.w3.is_connected.return_value = True
    client.w3.eth.chain_id = 31337
    client.w3.eth.gas_price = 1000000000
    client.w3.eth.get_transaction_count.return_value = 0

    mock_contract = MagicMock()
    client.credential_contract = mock_contract
    client.credential_registry_address = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
    client.has_contract_code = MagicMock(return_value=True)

    mock_func = MagicMock()
    mock_func.estimate_gas.return_value = 150000
    mock_func.build_transaction.return_value = {
        "from": client.signer_address,
        "nonce": 0,
        "gas": 187500,
        "gasPrice": 1000000000,
        "chainId": 31337,
    }
    mock_contract.functions.issueCredential.return_value = mock_func

    mock_receipt = MagicMock()
    mock_receipt.status = 0  # Reverted!
    mock_receipt.blockNumber = 43
    client.w3.eth.send_raw_transaction.return_value = b"\xbb" * 32
    client.w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    res = client.anchor_credential_fingerprint(
        credential_id_hex="0x" + "11" * 32,
        doc_digest_hex="0x" + "22" * 32,
        meta_digest_hex="0x" + "33" * 32,
        merkle_root_hex="0x" + "44" * 32,
        version=1,
    )
    assert res["success"] is False
    assert res["status"] == "REVERTED"


def test_mocked_contract_credential_verification_parsing():
    """
    Verifies that on-chain verifyCredential return structs are parsed accurately:
    (isValid, code, storedStatus, issuerId, isIssuerActive, expiresAt)
    """
    client = BlockchainClient(rpc_url="http://127.0.0.1:8545", timeout=1.0)
    mock_contract = MagicMock()
    client.credential_contract = mock_contract
    client.is_contract_ready = MagicMock(return_value=True)

    # Case 1: Valid
    # (bool isValid, uint8 code, uint8 storedStatus, bytes32 issuerId, bool isIssuerActive, uint64 expiresAt)
    mock_contract.functions.verifyCredential().call.return_value = (
        True, 0, 1, bytes.fromhex("11" * 32), True, 1800000000
    )
    res = client.verify_credential_on_chain("0x" + "aa" * 32, "0x" + "bb" * 32, "0x" + "cc" * 32, "0x" + "dd" * 32)
    assert res["is_valid"] is True
    assert res["code"] == "VALID"
    assert res["stored_status"] == "ACTIVE"
    assert res["is_issuer_active"] is True

    # Case 2: Expired
    mock_contract.functions.verifyCredential().call.return_value = (
        False, 4, 1, bytes.fromhex("11" * 32), True, 1600000000
    )
    res_exp = client.verify_credential_on_chain("0x" + "aa" * 32, "0x" + "bb" * 32, "0x" + "cc" * 32, "0x" + "dd" * 32)
    assert res_exp["is_valid"] is False
    assert res_exp["code"] == "EXPIRED"

    # Case 3: Hash Mismatch
    mock_contract.functions.verifyCredential().call.return_value = (
        False, 2, 1, bytes.fromhex("11" * 32), True, 1800000000
    )
    res_mis = client.verify_credential_on_chain("0x" + "aa" * 32, "0x" + "bb" * 32, "0x" + "cc" * 32, "0x" + "dd" * 32)
    assert res_mis["is_valid"] is False
    assert res_mis["code"] == "HASH_MISMATCH"


# ==============================================================================
# 5. PRIVACY & CRYPTOGRAPHIC INVARIANTS
# ==============================================================================

def test_privacy_invariants_no_pii_sent_to_contract():
    """
    Confirms that parameters passed to issueCredential contain ONLY 32-byte cryptographic hashes
    and integers. No student names, certificates, or metadata bytes are committed.
    """
    client = BlockchainClient(
        rpc_url="http://127.0.0.1:8545",
        chain_id=31337,
        signer_private_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    mock_contract = MagicMock()
    client.credential_contract = mock_contract
    client.has_contract_code = MagicMock(return_value=True)
    client.is_connected = MagicMock(return_value=True)
    client.get_connected_chain_id = MagicMock(return_value=31337)
    client.w3 = MagicMock()
    client.w3.eth.gas_price = 1000000000
    client.w3.eth.get_transaction_count.return_value = 0

    doc_digest = "0x" + "11" * 32
    meta_digest = "0x" + "22" * 32
    merkle_root = "0x" + "33" * 32
    cred_id = "0x" + "44" * 32

    client.anchor_credential_fingerprint(
        credential_id_hex=cred_id,
        doc_digest_hex=doc_digest,
        meta_digest_hex=meta_digest,
        merkle_root_hex=merkle_root,
        version=1,
        expires_at=0,
    )

    # Check call arguments
    call_args = mock_contract.functions.issueCredential.call_args[0]
    assert len(call_args) == 6
    # 4 hash digests must be exactly 32 bytes each
    assert len(call_args[0]) == 32
    assert len(call_args[1]) == 32
    assert len(call_args[2]) == 32
    assert len(call_args[3]) == 32
    assert isinstance(call_args[4], int)  # version
    assert isinstance(call_args[5], int)  # expiresAt


def test_get_credential_record_on_chain_decoding():
    """
    Verifies that getCredential on-chain struct is cleanly decoded into Python dictionary.
    """
    client = BlockchainClient(rpc_url="http://127.0.0.1:8545", timeout=1.0)
    mock_contract = MagicMock()
    client.credential_contract = mock_contract
    client.is_contract_ready = MagicMock(return_value=True)

    # Struct: (fingerprint, credentialId, issuerId, docDigest, metaDigest, merkleRoot, version, status, issuedAt, expiresAt, statusUpdatedAt, supersededBy)
    mock_rec = (
        bytes.fromhex("11" * 32),
        bytes.fromhex("22" * 32),
        bytes.fromhex("33" * 32),
        bytes.fromhex("44" * 32),
        bytes.fromhex("55" * 32),
        bytes.fromhex("66" * 32),
        1,  # version
        1,  # ACTIVE
        1700000000,
        1800000000,
        1700000000,
        b"\x00" * 32,
    )
    mock_contract.functions.getCredential().call.return_value = mock_rec

    rec = client.get_credential_record_on_chain("0x" + "11" * 32)
    assert rec is not None
    assert rec["fingerprint"] == "0x" + "11" * 32
    assert rec["credential_id"] == "0x" + "22" * 32
    assert rec["version"] == 1
    assert rec["status"] == "ACTIVE"
    assert rec["issued_at"] == 1700000000
    assert rec["superseded_by"] is None


# ==============================================================================
# 6. HEALTH PROBES & DIAGNOSTICS TESTS
# ==============================================================================

def test_health_blockchain_diagnostics_endpoint(client):
    """
    Verifies that /health/blockchain and /health/ready provide transparent diagnostics
    without exposing private keys or sensitive credentials.
    """
    res = client.get("/health/blockchain")
    assert res.status_code == 200
    diag = res.json()
    assert "status" in diag
    assert "rpc_connected" in diag
    assert "expected_chain_id" in diag
    assert "authoritative_verification_available" in diag
    assert "contracts" in diag
    assert "signer" in diag
    # Ensure no secrets leaked
    assert "private_key" not in str(diag).lower()
    assert "secret" not in str(diag).lower()

    # /health/ready includes blockchain diagnostics
    res_ready = client.get("/health/ready")
    assert res_ready.status_code in (200, 503)
    ready_data = res_ready.json()
    assert "blockchain" in ready_data
    assert "blockchain_rpc" in ready_data


# ==============================================================================
# 7. RECONCILIATION & RECOVERY TESTS
# ==============================================================================

def test_reconciliation_detects_already_anchored_record(db_session, admin_headers):
    """
    Tests idempotent reconciliation: if credential was confirmed on-chain but DB was PENDING,
    reconcile_and_anchor_credential discovers on-chain record and transitions DB to CONFIRMED.
    """
    from app.services.credential_service import CredentialService
    from app.models.credential import Credential
    from app.models.credential_version import CredentialVersion
    from app.blockchain.client import blockchain_client

    cred_id = "0x" + "aa" * 32
    issuer_id = "0x" + "bb" * 32
    fp = "0x" + "cc" * 32

    # Insert pending credential in database
    cred = Credential(credential_id=cred_id, issuer_id=issuer_id, current_version=1, current_fingerprint=fp, current_status="ACTIVE")
    ver = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint=fp,
        document_digest="0x" + "11" * 32,
        metadata_digest="0x" + "22" * 32,
        merkle_root="0x" + "33" * 32,
        issuance_status="PENDING",
    )
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    # Mock blockchain reporting that record is already on chain
    with patch.object(
        blockchain_client,
        "get_credential_record_on_chain",
        return_value={"issued_at": 1700000000, "status": "ACTIVE", "fingerprint": fp},
    ):
        service = CredentialService(db_session)
        resp = service.reconcile_and_anchor_credential(cred_id, 1)

    assert resp.issuance_status == "CONFIRMED"
    updated_ver = db_session.query(CredentialVersion).filter_by(credential_id=cred_id, version=1).first()
    assert updated_ver.issuance_status == "CONFIRMED"

