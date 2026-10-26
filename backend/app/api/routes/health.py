from fastapi import APIRouter, Response, status
from app.db.session import check_db_connectivity
from app.blockchain.client import blockchain_client

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness Probe")
def liveness_probe():
    """
    Returns 200 if application server process is alive.
    Independent of PostgreSQL or external dependencies.
    """
    return {"status": "live"}


@router.get("/health/ready", summary="Readiness Probe")
def readiness_probe(response: Response):
    """
    Verifies that core application dependencies (PostgreSQL) are operational.
    Reports 503 if database connectivity fails.
    Separately reports EVM blockchain connectivity, chain ID verification, contract bytecode
    deployment status, and transaction submission capabilities.
    """
    db_ok = check_db_connectivity()
    diag = blockchain_client.get_diagnostics()
    blockchain_ok = diag["rpc_connected"]

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": "disconnected",
            "blockchain_rpc": "connected" if blockchain_ok else "unavailable",
            "blockchain": diag,
        }

    return {
        "status": "ready",
        "database": "connected",
        "blockchain_rpc": "connected" if blockchain_ok else "unavailable",
        "blockchain": diag,
    }


@router.get("/health/blockchain", summary="Blockchain Diagnostics")
def blockchain_diagnostics_probe():
    """
    Detailed non-secret diagnostic probe for EVM blockchain integration.
    Reports RPC status, connected chain ID vs expected chain ID, contract bytecode presence,
    and signer transaction capability.
    """
    return blockchain_client.get_diagnostics(force_refresh=True)
