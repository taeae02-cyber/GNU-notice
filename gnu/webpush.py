"""
Web Push 발송 (RFC 8291 aes128gcm 암호화 + RFC 8292 VAPID 서명)을 외부 라이브러리 없이 구현.
의존: cryptography, requests

사용:
    from gnu.webpush import send
    status = send(subscription, {"title": "...", "body": "...", "url": "..."}, vapid_private_b64url, "https://사이트주소/")
    # status: HTTP 상태 코드 (201 성공, 404/410 이면 구독이 사라진 것)
"""
import base64
import json
import os
import struct
import time
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64url_decode(s):
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64url_encode(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _hkdf(salt, ikm, info, length):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(plaintext, p256dh_b64, auth_b64, salt=None, as_private=None):
    """구독자의 공개키(p256dh)·auth 로 payload 암호화 → aes128gcm 본문 (bytes)."""
    ua_public_raw = b64url_decode(p256dh_b64)
    auth_secret = b64url_decode(auth_b64)
    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public_raw)
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    as_public_raw = as_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = as_private.exchange(ec.ECDH(), ua_public)
    salt = salt or os.urandom(16)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public_raw + as_public_raw, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    record = plaintext + b"\x02"          # 마지막 레코드 구분자
    ciphertext = AESGCM(cek).encrypt(nonce, record, None)
    header = salt + struct.pack(">I", 4096) + bytes([len(as_public_raw)]) + as_public_raw
    return header + ciphertext


def vapid_headers(endpoint, private_b64url, subject, ttl=3600):
    """VAPID JWT 를 만들어 Authorization 헤더로 돌려줌."""
    d = int.from_bytes(b64url_decode(private_b64url), "big")
    priv = ec.derive_private_key(d, ec.SECP256R1())
    pub_raw = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    u = urlparse(endpoint)
    aud = f"{u.scheme}://{u.netloc}"
    header = b64url_encode(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = b64url_encode(json.dumps({"aud": aud, "exp": int(time.time()) + 12 * 3600, "sub": subject}, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}".encode()
    der = priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    sig = b64url_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    token = f"{header}.{claims}.{sig}"
    return {"Authorization": f"vapid t={token}, k={b64url_encode(pub_raw)}", "TTL": str(ttl)}


def send(subscription, payload, private_b64url, subject, ttl=3600, session=None, timeout=15):
    """
    subscription: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}
    payload: dict 또는 str
    반환: HTTP 상태 코드 (예외는 호출자가 처리)
    """
    endpoint = subscription["endpoint"]
    keys = subscription.get("keys") or {}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if not isinstance(payload, (bytes, str)) else (payload.encode("utf-8") if isinstance(payload, str) else payload)
    body = encrypt(data, keys["p256dh"], keys["auth"])
    headers = vapid_headers(endpoint, private_b64url, subject, ttl)
    headers.update({"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "Urgency": "normal"})
    r = (session or requests).post(endpoint, data=body, headers=headers, timeout=timeout)
    return r.status_code
