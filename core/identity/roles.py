class Roles:
    """
    Central role constants.
    These MUST match Role.code values stored in the database.
    """

    OPERATOR = "OPERATOR"
    IPQC = "IPQC"
    IPQC_PACK = "IPQC_PACK"
    PQE = "PQE"
    ADMIN = "ADMIN"
    SUPERUSER = "SUPERUSER"
    EHS_AUDITOR = "EHS_AUDITOR"
    EHS_ADMIN = "EHS_ADMIN"

    ALL_ROLES = (
        OPERATOR,
        IPQC,
        IPQC_PACK,
        PQE,
        ADMIN,
        SUPERUSER,
        EHS_AUDITOR,
        EHS_ADMIN,
    )

    @classmethod
    def is_valid(cls, role_code: str) -> bool:
        """
        Validate role code safely.
        """
        return role_code in cls.ALL_ROLES