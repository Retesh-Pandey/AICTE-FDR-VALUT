
from pydantic import BaseModel


class RenewalDecisionRequest(BaseModel):
    remarks: str
