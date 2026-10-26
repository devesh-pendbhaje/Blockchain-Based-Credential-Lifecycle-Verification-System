from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.issuer import Issuer


class IssuerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_issuer_id(self, issuer_id: str) -> Optional[Issuer]:
        stmt = select(Issuer).where(Issuer.issuer_id == issuer_id)
        return self.db.scalars(stmt).first()

    def create(self, issuer: Issuer) -> Issuer:
        self.db.add(issuer)
        self.db.flush()
        return issuer
