from fastapi import APIRouter, Depends, status
from app.crypto.merkle import (
    SaltedAttributeMerkleTree,
    verify_merkle_proof,
)
from app.schemas.merkle import (
    MerkleBuildTreeRequest,
    MerkleBuildTreeResponse,
    MerkleVerifyProofRequest,
    MerkleVerifyProofResponse,
)
from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import get_current_principal

router = APIRouter(prefix="/merkle", tags=["merkle"])


@router.post(
    "/build-tree",
    response_model=MerkleBuildTreeResponse,
    status_code=status.HTTP_200_OK,
    summary="Build Salted Attribute Merkle Tree",
)
def build_tree(
    req: MerkleBuildTreeRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Constructs a domain-separated, salted attribute Merkle tree matching DomainSeparatedMerkle.sol.
    Generates cryptographically random 256-bit salts for attributes if not provided.
    Returns the Merkle root, leaf hashes, salts, and sibling proofs.
    """
    tree = SaltedAttributeMerkleTree(
        attributes=req.attributes,
        salts=req.salts,
    )

    return MerkleBuildTreeResponse(
        merkle_root=tree.root,
        ordered_keys=tree.keys,
        leaves=tree.leaves,
        salts=tree.salts,
        proofs=tree.get_all_proofs(),
    )


@router.post(
    "/verify-proof",
    response_model=MerkleVerifyProofResponse,
    summary="Verify Domain-Separated Merkle Proof",
)
def verify_proof(
    req: MerkleVerifyProofRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Verifies a domain-separated Merkle proof against a target root matching
    Solidity DomainSeparatedMerkle.verifyProof.
    """
    is_valid = verify_merkle_proof(
        proof=req.proof,
        root=req.root,
        leaf=req.leaf,
    )
    return MerkleVerifyProofResponse(is_valid=is_valid)
