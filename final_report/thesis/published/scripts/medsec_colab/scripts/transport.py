"""Explicit repair extension: authenticated encrypted external recovery sidecar.

Implements secure transport pipeline:
  - Integration with 5D hyperchaotic DNA cipher (Subathra 2025).
  - Reversible LSB embedding via saliency-filtered non-ROI masking.
  - Authenticated symmetric payload packaging using AES-GCM-256.
  - Bit-exact plaintext and payload roundtrip guarantees.
"""
import base64
import hashlib
import json
import secrets
import time
import zlib
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .cipher import encrypt, decrypt, protected_mask
from .stego import embedding_mask, embed, extract, restore_cipher

AAD = b'medsec-recovery-extension-v1'


def b64(b: bytes) -> str:
    """Fast Base64 ASCII encoding."""
    return base64.b64encode(b).decode('ascii')


def unb64(s: str) -> bytes:
    """Strictly validated Base64 decoding."""
    return base64.b64decode(s, validate=True)


def seal(context: dict, secret: bytes) -> bytes:
    """Compresses context JSON and encrypts via AES-256-GCM with a fresh 96-bit nonce."""
    if len(secret) != 32:
        raise ValueError('A 32-byte separately shared secret is required')
    nonce = secrets.token_bytes(12)
    data = json.dumps(context, sort_keys=True, separators=(',', ':')).encode('utf-8')
    compressed = zlib.compress(data, level=9)
    ciphertext = AESGCM(secret).encrypt(nonce, compressed, AAD)
    return b'MSR1' + nonce + ciphertext


def open_sidecar(sidecar: bytes, secret: bytes) -> dict:
    """Decrypts and unpacks recovery sidecar context with cryptographic authentication."""
    if len(sidecar) < 16 or sidecar[:4] != b'MSR1':
        raise ValueError('Unknown recovery format')
    nonce = sidecar[4:16]
    ciphertext = sidecar[16:]
    decompressed = zlib.decompress(AESGCM(secret).decrypt(nonce, ciphertext, AAD))
    return json.loads(decompressed.decode('utf-8'))


def send(image: np.ndarray, roi: np.ndarray, payload: bytes, cfg: dict, secret: bytes) -> dict:
    """End-to-end sender pipeline: full hyperchaotic encryption followed by steganographic packaging."""
    start = time.perf_counter()
    cipher, digest = encrypt(image, roi, cfg)
    cipher_time = time.perf_counter() - start
    return send_prepared(image, roi, payload, cfg, secret, cipher, digest, cipher_time)


def send_prepared(
    image: np.ndarray,
    roi: np.ndarray,
    payload: bytes,
    cfg: dict,
    secret: bytes,
    cipher: np.ndarray,
    digest: str,
    cipher_time: float,
) -> dict:
    """Packages an already generated cipher image, preventing redundant ODE integration runs."""
    start = time.perf_counter()
    protected = protected_mask(roi, cfg)
    eligible = embedding_mask(cipher, protected, cfg)
    stego, pos, old, info = embed(cipher, payload, eligible, cfg)
    embedding_time = time.perf_counter() - start

    context = {
        'version': 1,
        'shape': list(image.shape),
        'digest': digest,
        'config': cfg,
        'positions': b64(pos.astype('<u8').tobytes()),
        'old_lsb': b64(old),
        'plain_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
        'stego_sha256': hashlib.sha256(stego.tobytes()).hexdigest(),
    }

    start = time.perf_counter()
    sidecar = seal(context, secret)
    wrap_time = time.perf_counter() - start

    info.update({
        'sidecar_bytes': len(sidecar),
        'sidecar_bpp': 8.0 * len(sidecar) / image.size,
        'total_transport_bytes_raw': image.nbytes + len(sidecar),
        'cipher_seconds': cipher_time,
        'embedding_seconds': embedding_time,
        'sidecar_seconds': wrap_time,
    })
    return {
        'cipher': cipher,
        'stego': stego,
        'sidecar': sidecar,
        'protected': protected,
        'info': info,
    }


def receive(stego: np.ndarray, sidecar: bytes, secret: bytes) -> tuple[np.ndarray, bytes]:
    """Authenticated receiver pipeline: verifies integrity, extracts payload, and restores plaintext."""
    ctx = open_sidecar(sidecar, secret)
    if list(stego.shape) != ctx['shape'] or hashlib.sha256(stego.tobytes()).hexdigest() != ctx['stego_sha256']:
        raise ValueError('Image tampering/shape mismatch detected; authenticated recovery rejected')

    pos = np.frombuffer(unb64(ctx['positions']), dtype='<u8').astype(np.int64)
    if len(np.unique(pos)) != len(pos) or (pos < 0).any() or (pos >= stego.size).any():
        raise ValueError('Invalid recovery positions')

    payload = extract(stego, pos)
    restored = restore_cipher(stego, pos, unb64(ctx['old_lsb']))
    plain = decrypt(restored, ctx['digest'], ctx['config'])

    if hashlib.sha256(plain.tobytes()).hexdigest() != ctx['plain_sha256']:
        raise ValueError('Plaintext hash mismatch: check floating-point environment/configuration')

    return plain, payload