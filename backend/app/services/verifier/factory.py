import logging
from app.core.config import settings
from app.services.verifier.interface import BankVerifierAdapter
from app.services.verifier.mock_adapter import MockBankVerifierAdapter

logger = logging.getLogger(__name__)


def get_bank_verifier() -> BankVerifierAdapter:
    """
    Factory function returning the configured Bank Verification Adapter.
    Uses settings.VERIFIER_MODE ('mock', 'simulated', or 'real').
    Throws an informative error if 'real' is configured without certified banking credentials,
    ensuring no accidental or unauthorized claims of bank connectivity.
    """
    mode = (settings.VERIFIER_MODE or "mock").strip().lower()

    if mode in ("mock", "simulated"):
        return MockBankVerifierAdapter(mode_name=mode)
    elif mode == "real":
        raise NotImplementedError(
            "Live bank gateway integration is not configured. "
            "Production bank connectivity requires an officially sanctioned banking API adapter "
            "and regulatory clearance. Set VERIFIER_MODE=mock for demonstration and testing."
        )
    else:
        logger.warning(f"Unknown VERIFIER_MODE '{mode}'. Falling back to safe mock adapter.")
        return MockBankVerifierAdapter(mode_name="mock")
