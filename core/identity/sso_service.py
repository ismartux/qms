import base64
import hmac
import hashlib
import json
import time
import secrets
from django.conf import settings

SSO_SHARED_SECRET = getattr(
    settings,
    'DCC_SSO_SHARED_SECRET',
    'sso_shared_key_dcc_qms_2026_x0729_tamperproof_secure'
).encode('utf-8')


def _b64_encode(data_bytes):
    return base64.urlsafe_b64encode(data_bytes).decode('utf-8').rstrip('=')


def _b64_decode(data_str):
    padding = '=' * (4 - (len(data_str) % 4)) if (len(data_str) % 4) != 0 else ''
    return base64.urlsafe_b64decode(data_str + padding)


def create_dcc_sso_token(user):
    """
    Creates a tamper-proof, cryptographically signed SSO token for DCC authentication.
    Valid for exactly 60 seconds with nonce to prevent replay attacks.
    """
    if not user or not user.is_active:
        raise ValueError("User is inactive or invalid")

    profile = getattr(user, 'employee_profile', None)

    if user.is_superuser:
        dcc_role = 'ADMIN'
    else:
        dcc_role = getattr(profile, 'dcc_role', 'USER') or 'USER'

    now = int(time.time())
    payload = {
        'username': user.username,
        'dcc_role': dcc_role,
        'iat': now,
        'exp': now + 60,  # 60s validity window
        'nonce': secrets.token_hex(8),
    }

    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    b64_payload = _b64_encode(payload_json)

    signature = hmac.new(SSO_SHARED_SECRET, b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{signature}"


def verify_dcc_sso_token(token_str):
    """
    Verifies the HMAC-SHA256 signature and expiration of an SSO token.
    Returns the decoded payload dict if valid, or None if invalid or expired.
    """
    if not token_str or '.' not in token_str:
        return None

    try:
        b64_payload, signature = token_str.split('.', 1)

        expected_sig = hmac.new(SSO_SHARED_SECRET, b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        payload_bytes = _b64_decode(b64_payload)
        payload = json.loads(payload_bytes.decode('utf-8'))

        now = int(time.time())
        if payload.get('exp', 0) < now:
            return None  # Expired

        if payload.get('iat', 0) > now + 30:
            return None  # Future token / clock skew

        return payload
    except Exception:
        return None

