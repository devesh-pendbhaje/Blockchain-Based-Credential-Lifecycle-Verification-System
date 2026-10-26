from datetime import timedelta
import pytest
from app.services.challenge_service import ChallengeService
from app.repositories.challenge_repository import ChallengeRepository
from app.core.exceptions import AppException
from app.db.base import utc_now


def test_challenge_issuance_and_no_raw_nonce_in_database(db_session):
    """
    Validates challenge issuance:
    1. Returns 256-bit nonce to caller.
    2. Stores ONLY SHA-256 hash in PostgreSQL to prevent database disclosure.
    """
    svc = ChallengeService(db_session)
    result = svc.create_challenge(
        verifier_session_id="verifier-session-42",
        credential_fingerprint="0x" + "a" * 64,
    )

    nonce = result["challenge_nonce"]
    challenge_id = result["challenge_id"]

    assert nonce.startswith("0x")
    assert len(nonce) == 66  # 0x + 64 hex characters (256 bits)

    # Inspect database row
    repo = ChallengeRepository(db_session)
    stored_row = repo.get_by_challenge_id(challenge_id)
    assert stored_row is not None
    assert stored_row.status == "ISSUED"

    # CRITICAL: Verify raw nonce is NOT stored in the database column
    assert stored_row.challenge_hash != nonce
    assert stored_row.challenge_hash.lower() == svc._hash_nonce(nonce).lower()


def test_challenge_atomic_single_use_consumption(db_session):
    """
    Validates single-use lifecycle:
    1. First validation succeeds and marks challenge CONSUMED.
    2. Second validation (replay attempt) is rejected with HTTP 409.
    """
    svc = ChallengeService(db_session)
    res = svc.create_challenge(verifier_session_id="session-alice")

    cid = res["challenge_id"]
    nonce = res["challenge_nonce"]

    # 1. First consumption succeeds
    outcome1 = svc.validate_and_consume_challenge(
        challenge_id=cid,
        challenge_nonce=nonce,
        verifier_session_id="session-alice",
    )
    assert outcome1["status"] == "CONSUMED"

    # 2. Second consumption attempt fails (replay protection)
    with pytest.raises(AppException) as exc_info:
        svc.validate_and_consume_challenge(
            challenge_id=cid,
            challenge_nonce=nonce,
            verifier_session_id="session-alice",
        )
    assert exc_info.value.error_code == "CHALLENGE_ALREADY_CONSUMED"


def test_challenge_session_and_fingerprint_binding(db_session):
    """
    Guarantees challenge cannot be verified by the wrong verifier session
    or presented for the wrong credential fingerprint.
    """
    svc = ChallengeService(db_session)
    scoped_fp = "0x" + "b" * 64
    res = svc.create_challenge(
        verifier_session_id="verifier-authorized",
        credential_fingerprint=scoped_fp,
    )

    cid = res["challenge_id"]
    nonce = res["challenge_nonce"]

    # 1. Wrong session ID rejected
    with pytest.raises(AppException) as exc_info:
        svc.validate_and_consume_challenge(
            challenge_id=cid,
            challenge_nonce=nonce,
            verifier_session_id="verifier-imposter",
            credential_fingerprint=scoped_fp,
        )
    assert exc_info.value.error_code == "VERIFIER_SESSION_MISMATCH"

    # 2. Wrong credential fingerprint rejected
    with pytest.raises(AppException) as exc_info:
        svc.validate_and_consume_challenge(
            challenge_id=cid,
            challenge_nonce=nonce,
            verifier_session_id="verifier-authorized",
            credential_fingerprint="0x" + "c" * 64,
        )
    assert exc_info.value.error_code == "CHALLENGE_SCOPE_MISMATCH"


def test_challenge_expiration(db_session):
    """
    Rejects expired challenges even if nonce and session match.
    """
    svc = ChallengeService(db_session)
    repo = ChallengeRepository(db_session)

    # Issue challenge with past expiration
    res = svc.create_challenge(verifier_session_id="session-expired", expiry_seconds=300)
    cid = res["challenge_id"]
    nonce = res["challenge_nonce"]

    # Artificially set expires_at in the past
    row = repo.get_by_challenge_id(cid)
    row.expires_at = utc_now() - timedelta(seconds=10)
    db_session.commit()

    with pytest.raises(AppException) as exc_info:
        svc.validate_and_consume_challenge(
            challenge_id=cid,
            challenge_nonce=nonce,
            verifier_session_id="session-expired",
        )
    assert exc_info.value.error_code == "CHALLENGE_EXPIRED"


def test_challenge_concurrency_race_condition(db_session):
    """
    Simulates race condition: two concurrent consumers attempting to consume
    the same challenge atomically. Only one can succeed.
    """
    svc = ChallengeService(db_session)
    res = svc.create_challenge(verifier_session_id="race-session")
    cid = res["challenge_id"]
    nonce = res["challenge_nonce"]
    hash_val = svc._hash_nonce(nonce)

    repo = ChallengeRepository(db_session)

    # Consumer A succeeds
    consumed_a = repo.consume_atomically(cid, hash_val)
    assert consumed_a is True

    # Consumer B fails immediately (atomic rowcount == 0)
    consumed_b = repo.consume_atomically(cid, hash_val)
    assert consumed_b is False
