import secrets

SYMBOLS = ["@", "#", "$", "%", "&"]


def generate_employee_password(first_name: str, employee_id: str) -> str:
    """
    Password format:
    <CapitalizedFirstName><1-2 random symbols><last 4 digits of employee_id>

    Example:
    Rohit@6023
    Rohit#%6023
    """

    # Safe first name handling
    first_name = (first_name or "").strip().capitalize()
    if not first_name:
        first_name = "User"

    # Cryptographically secure symbol selection
    symbol_count = secrets.choice([1, 2])
    symbols = "".join(secrets.choice(SYMBOLS) for _ in range(symbol_count))

    # Safe employee_id handling
    employee_id_str = str(employee_id or "")
    last_four = employee_id_str[-4:] if len(employee_id_str) >= 4 else employee_id_str

    return f"{first_name}{symbols}{last_four}"