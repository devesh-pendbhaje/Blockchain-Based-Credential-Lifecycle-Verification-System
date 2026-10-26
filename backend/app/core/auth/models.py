from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AuthenticatedPrincipal(BaseModel):
    """
    Cryptographically authenticated security principal derived from validated token claims.
    Never constructed from untrusted caller-supplied query parameters or headers.
    """
    subject: str = Field(..., description="Unique authenticated user or service principal identifier (sub)")
    roles: List[str] = Field(default_factory=list, description="Validated authorization roles")
    issuer_id: Optional[str] = Field(None, description="Bound institutional 32-byte hex ID for issuer principals")
    verifier_id: Optional[str] = Field(None, description="Bound institutional or organization ID for verifier principals")
    email: Optional[str] = Field(None, description="Optional principal email for audit trails")
    raw_claims: Dict[str, Any] = Field(default_factory=dict, description="Raw validated token claims")

    def has_role(self, required_role: str) -> bool:
        """
        Role-based access check. Admin role inherently satisfies any requirement.
        """
        role_set = {r.lower() for r in self.roles}
        return "admin" in role_set or required_role.lower() in role_set

    def is_admin(self) -> bool:
        return "admin" in {r.lower() for r in self.roles}
