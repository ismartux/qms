# =====================================================
# SUBMISSION WORKFLOW STATES
# =====================================================

class WorkflowState:
    # Core states
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SYNC_PENDING = "SYNC_PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"

    # Django model choices
    CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (SYNC_PENDING, "Sync Pending"),
        (SYNCED, "Synced"),
        (FAILED, "Failed"),
        (CLOSED, "Closed"),
    ]

    # All valid states
    ALL = {
        DRAFT,
        SUBMITTED,
        SYNC_PENDING,
        SYNCED,
        FAILED,
        CLOSED,
    }

    # Terminal states (no further transitions allowed)
    TERMINAL = {CLOSED}

    @classmethod
    def is_valid(cls, state: str) -> bool:
        return state in cls.ALL

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state in cls.TERMINAL


# =====================================================
# CAPA STATES
# =====================================================

class CapaState:
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    ACTION_DONE = "ACTION_DONE"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"

    CHOICES = [
        (OPEN, "Open"),
        (ASSIGNED, "Assigned"),
        (IN_PROGRESS, "In Progress"),
        (ACTION_DONE, "Action Done"),
        (VERIFIED, "Verified"),
        (CLOSED, "Closed"),
    ]

    ALL = {
        OPEN,
        ASSIGNED,
        IN_PROGRESS,
        ACTION_DONE,
        VERIFIED,
        CLOSED,
    }

    TERMINAL = {CLOSED}

    @classmethod
    def is_valid(cls, state: str) -> bool:
        return state in cls.ALL


# =====================================================
# APPROVAL STATES
# =====================================================

class ApprovalState:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    ALL = {
        PENDING,
        APPROVED,
        REJECTED,
    }

    TERMINAL = {APPROVED, REJECTED}

    @classmethod
    def is_valid(cls, state: str) -> bool:
        return state in cls.ALL