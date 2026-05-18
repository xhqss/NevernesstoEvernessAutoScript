"""
Spec §25-27 — Security Runtime.

AESGCM encryption (cryptography lib with pure-Python fallback).
Log desensitization: phone numbers, Bearer tokens, credentials.
SecurityRuntime: audit trail tracking.
"""

import hashlib
import os
import re
import time
from collections import deque

from module.runtime.event_bus import bus
from module.runtime.base_module import BaseModule
from module.runtime import RuntimeContext
from module.util.logger import logger

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _CryptoAESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


# ── AESGCM encryptor ──────────────────────────────────────────────────

class AESGCM:
    """AES-256-GCM encryptor with cryptography fallback to XOR obfuscation."""

    def __init__(self, key: bytes | None = None):
        if key is None:
            key = hashlib.sha256(os.urandom(64)).digest()
        self._key = key[:32]
        self._native: _CryptoAESGCM | None = None
        if HAS_CRYPTOGRAPHY:
            self._native = _CryptoAESGCM(self._key)

    def encrypt(self, plaintext: bytes) -> bytes:
        if self._native is not None:
            nonce = os.urandom(12)
            return nonce + self._native.encrypt(nonce, plaintext, None)
        # Fallback XOR obfuscation
        return self._xor_mask(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        if self._native is not None:
            nonce = ciphertext[:12]
            return self._native.decrypt(nonce, ciphertext[12:], None)
        return self._xor_mask(ciphertext)

    def _xor_mask(self, data: bytes) -> bytes:
        key_cycle = (self._key * (len(data) // len(self._key) + 1))[:len(data)]
        return bytes(a ^ b for a, b in zip(data, key_cycle))

    @property
    def is_native(self) -> bool:
        return self._native is not None


# Global encryptor instance
encryptor = AESGCM()


# ── Desensitize ───────────────────────────────────────────────────────

_PHONE_RE = re.compile(r'(1[3-9]\d)\d{4}(\d{4})')
_BEARER_RE = re.compile(r'(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)')
_CREDENTIAL_RE = re.compile(r'(?i)((?:password|token|secret|key|auth)\s*[:=]\s*)(\S+)')


def desensitize(text: str) -> str:
    """Strip sensitive data from log strings."""
    text = _PHONE_RE.sub(r'\1****\2', text)
    text = _BEARER_RE.sub(r'\1****', text)
    text = _CREDENTIAL_RE.sub(r'\1****', text)
    return text


# ── SecurityRuntime ───────────────────────────────────────────────────

class SecurityRuntime(BaseModule):
    """Audit-trail security monitor.

    Tracks: encryption operations, access attempts, sensitive-data access.
    """

    def __init__(self, ctx: RuntimeContext):
        super().__init__()
        self.ctx = ctx
        self._running = False
        self._audit_log: deque[tuple[float, str, str, dict]] = deque(maxlen=1000)
        self._access_count: dict[str, int] = {}
        self._encryption_ops = 0

        bus.subscribe("SECURITY_AUDIT", self._on_audit)

    def start(self):
        self._running = True
        logger.info('SecurityRuntime started')

    def stop(self):
        self._running = False
        logger.info('SecurityRuntime stopped')

    def pause(self):
        pass

    def tick(self):
        pass

    def recover(self) -> bool:
        return True

    def healthcheck(self) -> dict:
        return {
            "audit_entries": len(self._audit_log),
            "encryption_ops": self._encryption_ops,
            "running": self._running,
        }

    def record(self, category: str, action: str, details: dict | None = None):
        entry = (time.time(), category, action, details or {})
        self._audit_log.append(entry)

    def _on_audit(self, event_type: str, payload: dict):
        self.record(
            payload.get("category", "general"),
            payload.get("action", "unknown"),
            payload,
        )

    def encrypt(self, data: bytes) -> bytes:
        self._encryption_ops += 1
        return encryptor.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        self._encryption_ops += 1
        return encryptor.decrypt(data)

    def log_safe(self, msg: str) -> str:
        return desensitize(msg)

    def audit_entries(self, limit: int = 50) -> list[tuple[float, str, str, dict]]:
        return list(self._audit_log)[-limit:]

    @property
    def stats(self) -> dict:
        return self.healthcheck()
