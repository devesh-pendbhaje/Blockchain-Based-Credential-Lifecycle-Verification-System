import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.issuer import Issuer
from app.repositories.issuer_repository import IssuerRepository
from app.repositories.credential_repository import CredentialRepository
from app.schemas.issuer import IssuerCreateRequest, IssuerResponse, IssuerStatusResponse
from app.core.exceptions import AppException, EntityNotFoundException, EntityConflictException
from app.blockchain.client import blockchain_client


class IssuerService:
    def __init__(self, db: Session):
        self.db = db
        self.issuer_repo = IssuerRepository(db)
        self.cred_repo = CredentialRepository(db)

    def activate_local_issuer(self, issuer_id: str):
        from urllib.parse import urlparse
        from app.core.config import settings
        from app.blockchain.issuer_signers import provision_lock, get_account, create_local_account
        chain = blockchain_client
        if (not settings.is_local_dev or chain.chain_id != 31337 or
                urlparse(chain.rpc_url).hostname not in {'127.0.0.1', 'localhost', '::1'}):
            raise AppException('Automatic activation is available only on the local Hardhat demo.', 'LOCAL_ACTIVATION_ONLY', 403)
        if (not chain.is_connected() or chain.w3.eth.chain_id != 31337 or
                'hardhat' not in chain.w3.client_version.lower() or not chain.is_contract_ready('issuer')):
            raise AppException('Local Hardhat registry is unavailable.', 'LOCAL_CHAIN_UNAVAILABLE', 503)
        if not chain.signer_address or chain.issuer_contract.functions.owner().call().lower() != chain.signer_address.lower():
            raise AppException('The configured governance signer does not own the issuer registry.', 'GOVERNANCE_REQUIRED', 403)
        issuer = self.issuer_repo.get_by_issuer_id(issuer_id)
        if not issuer:
            raise EntityNotFoundException('Create the university profile first.')
        if issuer.status != 'ACTIVE':
            raise AppException('University profile must be ACTIVE.', 'ISSUER_INACTIVE', 400)
        with provision_lock, chain._tx_lock:
            available, active, standing = chain.get_issuer_status_on_chain(issuer_id)
            if not available:
                raise AppException('Cannot inspect issuer registration.', 'REGISTRY_UNAVAILABLE', 503)
            if standing not in {'NOT_FOUND', 'NONE'}:
                account = get_account(chain, issuer_id)
                account = account or chain.signer_account
                registered = chain.issuer_contract.functions.getIssuer(bytes.fromhex(issuer_id[2:])).call()
                if not active or not account or registered[1].lower() != account.address.lower():
                    raise AppException('Existing registration requires its matching signer and active standing; activation will not overwrite it.', 'EXISTING_ISSUER_AUTHORITY', 409)
                return {'status': 'CONFIRMED', 'issuer_id': issuer_id, 'signing_address': account.address, 'already_registered': True}
            # Persist the key before sending: retries always reuse the same identity.
            account = create_local_account(chain, issuer_id)
            if chain.w3.eth.get_balance(account.address) < 10**18:
                funded = chain.w3.provider.make_request('hardhat_setBalance', [account.address, hex(10 * 10**18)])
                if 'error' in funded:
                    raise AppException('Could not fund local demo signer.', 'LOCAL_FUNDING_FAILED', 503)
            result = chain.register_issuer_on_chain(issuer_id, account.address, issuer.metadata_uri or '')
            if not result.get('success'):
                raise AppException('Registration not confirmed. Inspect chain connectivity and retry activation with the same issuer ID.', 'ISSUER_REGISTRATION_FAILED', 503)
            registered = chain.issuer_contract.functions.getIssuer(bytes.fromhex(issuer_id[2:])).call()
            if registered[1].lower() != account.address.lower() or not chain.get_issuer_status_on_chain(issuer_id)[1]:
                raise AppException('On-chain signer confirmation failed.', 'ISSUER_REGISTRATION_MISMATCH', 409)
            self.cred_repo.record_audit('ISSUER_CHAIN_ACTIVATED', 'ISSUER', issuer_id, 'SUCCESS', str(uuid.uuid4()),
                                       json.dumps({'signing_address': account.address, 'tx_hash': result.get('tx_hash')}))
            self.db.commit()
            return {'status': 'CONFIRMED', 'issuer_id': issuer_id, 'signing_address': account.address, 'tx_hash': result.get('tx_hash')}

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
