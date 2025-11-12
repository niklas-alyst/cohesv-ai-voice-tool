"""Twilio signature generation for E2E tests."""

import hmac
import hashlib
from urllib.parse import urlencode
from typing import Dict


def generate_twilio_signature(url: str, params: Dict[str, str], auth_token: str) -> str:
    """
    Generate a valid Twilio signature for webhook validation.

    This matches Twilio's signature algorithm:
    1. Concatenate the URL and sorted parameters
    2. HMAC-SHA1 hash with auth token
    3. Base64 encode

    Args:
        url: Full webhook URL (e.g., https://api.example.com/webhook)
        params: POST parameters as dict
        auth_token: Twilio auth token

    Returns:
        Base64-encoded signature string
    """
    # Twilio concatenates: URL + sorted(key+value for each param)
    data = url + ''.join([f'{k}{v}' for k, v in sorted(params.items())])

    # HMAC-SHA1 hash
    signature = hmac.new(
        auth_token.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha1
    ).digest()

    # Base64 encode
    import base64
    return base64.b64encode(signature).decode('utf-8')


def create_webhook_request_body(params: Dict[str, str]) -> str:
    """
    Create URL-encoded form body for webhook POST request.

    Args:
        params: Webhook parameters

    Returns:
        URL-encoded form data string
    """
    return urlencode(params)
