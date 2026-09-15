"""Explicit repair extension: authenticated encrypted external recovery sidecar.

Not the thesis's impossible receiver-only U-Net reconstruction. The sidecar is
required, counted in bandwidth, and never embeds the original full image.
"""
import base64
import hashlib
import json
import secrets
import time
import zlib
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .cipher import encrypt,decrypt,protected_mask
from .stego import embedding_mask,embed,extract,restore_cipher

AAD=b'medsec-recovery-extension-v1'
b64=lambda b:base64.b64encode(b).decode('ascii')
unb64=lambda s:base64.b64decode(s,validate=True)

def seal(context,secret):
    if len(secret)!=32: raise ValueError('A 32-byte separately shared secret is required')
    nonce=secrets.token_bytes(12)
    data=json.dumps(context,sort_keys=True,separators=(',',':')).encode()
    return b'MSR1'+nonce+AESGCM(secret).encrypt(nonce,zlib.compress(data),AAD)

def open_sidecar(sidecar,secret):
    if sidecar[:4]!=b'MSR1': raise ValueError('Unknown recovery format')
    data=AESGCM(secret).decrypt(sidecar[4:16],sidecar[16:],AAD)
    return json.loads(zlib.decompress(data))

def send(image,roi,payload,cfg,secret):
    start=time.perf_counter(); cipher,digest=encrypt(image,roi,cfg)
    cipher_time=time.perf_counter()-start
    start=time.perf_counter(); protected=protected_mask(roi,cfg)
    eligible=embedding_mask(cipher,protected,cfg)
    stego,pos,old,info=embed(cipher,payload,eligible,cfg)
    embedding_time=time.perf_counter()-start
    context={'version':1,'shape':list(image.shape),'digest':digest,'config':cfg,
             'positions':b64(pos.astype('<u8').tobytes()),'old_lsb':b64(old),
             'plain_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
             'stego_sha256':hashlib.sha256(stego.tobytes()).hexdigest()}
    start=time.perf_counter(); sidecar=seal(context,secret); wrap_time=time.perf_counter()-start
    info.update({'sidecar_bytes':len(sidecar),'sidecar_bpp':8*len(sidecar)/image.size,
                 'total_transport_bytes_raw':image.nbytes+len(sidecar),
                 'cipher_seconds':cipher_time,'embedding_seconds':embedding_time,'sidecar_seconds':wrap_time})
    return {'cipher':cipher,'stego':stego,'sidecar':sidecar,'protected':protected,'info':info}

def receive(stego,sidecar,secret):
    ctx=open_sidecar(sidecar,secret)
    if list(stego.shape)!=ctx['shape'] or hashlib.sha256(stego.tobytes()).hexdigest()!=ctx['stego_sha256']:
        raise ValueError('Image tampering/shape mismatch detected; authenticated recovery rejected')
    pos=np.frombuffer(unb64(ctx['positions']),dtype='<u8').astype(np.int64)
    if len(np.unique(pos))!=len(pos) or (pos<0).any() or (pos>=stego.size).any():
        raise ValueError('Invalid recovery positions')
    payload=extract(stego,pos)
    restored=restore_cipher(stego,pos,unb64(ctx['old_lsb']))
    plain=decrypt(restored,ctx['digest'],ctx['config'])
    if hashlib.sha256(plain.tobytes()).hexdigest()!=ctx['plain_sha256']:
        raise ValueError('Plaintext hash mismatch: check floating-point environment/configuration')
    return plain,payload