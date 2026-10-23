from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.db.models import FDRRecord, User


class BankVerifierAdapter(ABC):
    """
    Abstract interface for Bank Verification adapters.
    Ensures that mock/simulated adapters can be substituted by an officially
    approved bank API gateway in future without altering calling workflows.
    """

    @abstractmethod
    def verify_fdr(
        self,
        fdr: FDRRecord,
        db: Session,
        actor: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Verify FDR details against external or simulated records.
        Returns a structured dictionary with outcome, field comparisons,
        and statutory disclaimers.
        """
        pass
