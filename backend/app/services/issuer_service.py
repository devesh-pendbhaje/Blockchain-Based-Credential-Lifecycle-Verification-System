import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.issuer import Issuer
from app.repositories.issuer_repository import IssuerRepository
from app.repositories.credential_repository import CredentialRepository
from app.schemas.issuer import IssuerCreateRequest, IssuerResponse, IssuerStatusResponse
from app.core.exceptions import EntityNotFoundException, EntityConflictException
from app.blockchain.client import blockchain_client


class IssuerService:
    def __init__(self, db: Session):
        self.db = db
        self.issuer_repo = IssuerRepository(db)
        self.cred_repo = CredentialRepository(db)

    def create_issuer(self, req: IssuerCreateRequest) -> IssuerResponse:
        correlation_id = str(uuid.uuid4())
        existing = self.issuer_repo.get_by_issuer_id(req.issuer_id)
        if existing:
            self.cred_repo.record_audit(
                event_type="ISSUER_CREATION_REJECTED",
                entity_type="ISSUER",
                entity_id=req.issuer_id,
                outcome="FAILURE",
                correlation_id=correlation_id,
                details_json=json.dumps({"reason": "Duplicate issuer ID"}),
            )
            self.db.commit()
            raise EntityConflictException(f"Issuer with ID '{req.issuer_id}' already exists in database.")

        issuer = Issuer(
            issuer_id=req.issuer_id,
            display_name=req.display_name,
            metadata_uri=req.metadata_uri,
            status=req.status,
        )
        self.issuer_repo.create(issuer)

        self.cred_repo.record_audit(
            event_type="ISSUER_CREATED",
            entity_type="ISSUER",
            entity_id=req.issuer_id,
            outcome="SUCCESS",
            correlation_id=correlation_id,
            details_json=json.dumps({"display_name": req.display_name, "status": req.status}),
        )
        self.db.commit()

        # Check on-chain presence if available
        available, is_active, on_chain_st = blockchain_client.get_issuer_status_on_chain(req.issuer_id)
        on_chain_reg = is_active if available else None

        return IssuerResponse(
            issuer_id=issuer.issuer_id,
            display_name=issuer.display_name,
            metadata_uri=issuer.metadata_uri,
            status=issuer.status,
            created_at=issuer.created_at,
            updated_at=issuer.updated_at,
            on_chain_registered=on_chain_reg,
        )

    def get_issuer(self, issuer_id: str) -> IssuerResponse:
        issuer = self.issuer_repo.get_by_issuer_id(issuer_id)
        if not issuer:
            raise EntityNotFoundException(f"Issuer with ID '{issuer_id}' was not found.")

        available, is_active, on_chain_st = blockchain_client.get_issuer_status_on_chain(issuer_id)
        on_chain_reg = is_active if available else None

        return IssuerResponse(
            issuer_id=issuer.issuer_id,
            display_name=issuer.display_name,
            metadata_uri=issuer.metadata_uri,
            status=issuer.status,
            created_at=issuer.created_at,
            updated_at=issuer.updated_at,
            on_chain_registered=on_chain_reg,
        )

    def get_issuer_status(self, issuer_id: str) -> IssuerStatusResponse:
        issuer = self.issuer_repo.get_by_issuer_id(issuer_id)
        if not issuer:
            raise EntityNotFoundException(f"Issuer with ID '{issuer_id}' was not found.")

        available, is_active, on_chain_st = blockchain_client.get_issuer_status_on_chain(issuer_id)

        return IssuerStatusResponse(
            issuer_id=issuer.issuer_id,
            db_status=issuer.status,
            on_chain_status=on_chain_st if available else "UNAVAILABLE",
            is_on_chain_active=is_active if available else None,
            checked_at=datetime.now(timezone.utc),
        )

    def register_issuer_on_chain(
        self,
        issuer_id: str,
        signing_address: str,
        metadata_uri: str = "",
    ):
        """
        Submits on-chain issuer registration to IssuerRegistry contract.
        Requires signer configured with governance admin authority.
        """
        issuer = self.issuer_repo.get_by_issuer_id(issuer_id)
        if not issuer:
            raise EntityNotFoundException(f"Issuer with ID '{issuer_id}' was not found.")

        meta_uri = metadata_uri or issuer.metadata_uri or ""
        return blockchain_client.register_issuer_on_chain(
            issuer_id_hex=issuer_id,
            signing_address=signing_address,
            metadata_uri=meta_uri,
        )
