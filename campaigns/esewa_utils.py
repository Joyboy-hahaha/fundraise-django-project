
import base64
import hashlib
import hmac
import json

import requests
from django.conf import settings


def generate_esewa_signature(total_amount, transaction_uuid, product_code):
    """
    Builds the exact message eSewa expects and signs it with HMAC-SHA256,
    returning a base64-encoded signature string.

    IMPORTANT: the field order and formatting here must match exactly what
    is sent in the form (see build_esewa_payload below), or eSewa will
    reject the payment as tampered.
    """
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    secret_key_bytes = settings.ESEWA_SECRET_KEY.encode('utf-8')
    message_bytes = message.encode('utf-8')
    hmac_hash = hmac.new(secret_key_bytes, message_bytes, hashlib.sha256).digest()
    return base64.b64encode(hmac_hash).decode('utf-8')


def build_esewa_payload(donation, success_url, failure_url):
    """
    Builds the full dict of form fields to POST to eSewa's payment page
    for a given Donation instance.
    """
    # Always use exactly 2 decimal places - eSewa is strict about this
    # since the signature is computed over the exact string sent.
    total_amount = f"{donation.amount:.2f}"
    transaction_uuid = donation.transaction_uuid
    product_code = settings.ESEWA_PRODUCT_CODE

    signature = generate_esewa_signature(total_amount, transaction_uuid, product_code)

    return {
        'amount': total_amount,
        'tax_amount': '0',
        'total_amount': total_amount,
        'transaction_uuid': transaction_uuid,
        'product_code': product_code,
        'product_service_charge': '0',
        'product_delivery_charge': '0',
        'success_url': success_url,
        'failure_url': failure_url,
        'signed_field_names': 'total_amount,transaction_uuid,product_code',
        'signature': signature,
    }


def decode_esewa_response(encoded_data):
    """
    Decodes the base64 'data' query param eSewa sends back to success_url.
    Returns a dict, or None if it can't be decoded.
    """
    try:
        decoded_bytes = base64.b64decode(encoded_data)
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        return None


def verify_esewa_signature(data_dict):
    """
    Re-computes the signature over the fields eSewa says it signed, and
    checks it matches the signature eSewa sent us. This proves the response
    actually came from eSewa and wasn't altered in transit.
    """
    try:
        signed_field_names = data_dict['signed_field_names'].split(',')
        message = ','.join(f"{field.strip()}={data_dict[field.strip()]}" for field in signed_field_names)
        secret_key_bytes = settings.ESEWA_SECRET_KEY.encode('utf-8')
        expected_signature = base64.b64encode(
            hmac.new(secret_key_bytes, message.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')
        return hmac.compare_digest(expected_signature, data_dict.get('signature', ''))
    except Exception:
        return False


def check_esewa_status(total_amount, transaction_uuid, product_code=None):
    """
    Server-to-server check against eSewa's status API. This is the real
    source of truth — we never trust the browser redirect alone. Returns
    the status string (e.g. 'COMPLETE', 'PENDING', 'NOT_FOUND') or None if
    the request itself failed.
    """
    product_code = product_code or settings.ESEWA_PRODUCT_CODE
    try:
        response = requests.get(
            settings.ESEWA_STATUS_CHECK_URL,
            params={
                'product_code': product_code,
                'total_amount': total_amount,
                'transaction_uuid': transaction_uuid,
            },
            timeout=5,
        )
        response.raise_for_status()
        return response.json().get('status')
    except Exception:
        return None
