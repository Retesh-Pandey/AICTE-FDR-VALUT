"""Workflow configuration defining authoritative state transitions and role permissions.

Single source of truth for all FDR lifecycle state machines.
"""

from typing import Any, Dict

# Release Workflow State Machine Transitions and Required Roles
RELEASE_WORKFLOW: Dict[str, Dict[str, Dict[str, Any]]] = {
    "release_requested": {
        "under_review": {"roles": ["officer"]},
    },
    "under_review": {
        "conditions_checked": {"roles": ["officer"]},
        "rejected": {"roles": ["officer"]},
    },
    "conditions_checked": {
        "approval_pending": {"roles": ["officer"]},
        "rejected": {"roles": ["officer"]},
    },
    "approval_pending": {
        "approved": {"roles": ["admin"]},
        "rejected": {"roles": ["admin"]},
    },
    "approved": {
        "completed": {"roles": ["admin"]},
    },
}

# Renewal Workflow State Machine Transitions and Required Roles
RENEWAL_WORKFLOW: Dict[str, Dict[str, Dict[str, Any]]] = {
    "renewal_review": {
        "approved": {"roles": ["officer"]},
        "rejected": {"roles": ["officer"]},
    },
}

# Default configurable reminder day intervals before maturity
REMINDER_DEFAULTS = [30, 15, 7]
