import hashlib
import struct
import zlib
import numpy as np
from scipy.ndimage import uniform_filter, gaussian_filter

HEADER=struct.Struct('>4sQQ32s')

def saliency(image,cfg):
    freq=np.fft.fft2(image.astype(np.float64))
    logamp=np.log(np.maximum(np.abs(freq),np.finfo(np.float64).eps))
    residual=logamp-uniform_filter(logamp,size=cfg['saliency_filter'],mode='reflect')
    spatial=np.abs(np.fft.ifft2(np.exp(residual+1j*np.angle(freq))))**2
    return gaussian_filter(spatial,cfg['saliency_sigma'])

def embedding_mask(cipher,protected,cfg):
    if cfg.get('no_saliency'): return ~protected
    s=saliency(cipher,cfg); threshold=np.quantile(s,cfg['saliency_quantile'])
    return (s<threshold)&(~protected)

def pack_pairs(values):
    values=np.asarray(values,np.uint8)
    bits=((values[:,None]>>np.array([1,0],np.uint8))&1).ravel()
    return np.packbits(bits).tobytes()

def unpack_pairs(data,count):
    bits=np.unpackbits(np.frombuffer(data,np.uint8))[:2*count].reshape(-1,2)
    return (bits[:,0]*2+bits[:,1]).astype(np.uint8)

def embed(cipher,payload,eligible,cfg):
    if cipher.shape!=eligible.shape: raise ValueError('Mask shape mismatch')
    compressed=zlib.compress(payload,level=cfg['compression_level'])
    packet=HEADER.pack(b'MST1',len(compressed),len(payload),hashlib.sha256(payload).digest())+compressed
    positions=np.flatnonzero(eligible.ravel())
    needed=len(packet)*4
    if needed>positions.size:
        raise ValueError(f'Insufficient capacity: need {needed*2} bits; available {positions.size*2}; nothing embedded')
    positions=positions[:needed]
    flat=cipher.ravel().copy(); original=pack_pairs(flat[positions]&3)
    flat[positions]=(flat[positions]&252)|unpack_pairs(packet,needed)
    info={'compressed_bytes':len(compressed),'payload_bytes':len(payload),'framing_bytes':HEADER.size,
          'embedded_bits':len(packet)*8,'available_bits':int(np.count_nonzero(eligible))*2,
          'payload_bpp':len(payload)*8/cipher.size,'compressed_bpp':len(compressed)*8/cipher.size,
          'gross_embedded_bpp':len(packet)*8/cipher.size,
          'available_bpp':int(np.count_nonzero(eligible))*2/cipher.size,
          'compression_saving_pct':100*(1-len(compressed)/len(payload)) if payload else None}
    return flat.reshape(cipher.shape),positions,original,info

def extract(stego,positions,max_payload_bytes=64*1024*1024):
    packet=pack_pairs(stego.ravel()[positions]&3)
    if len(packet)<HEADER.size: raise ValueError('Truncated header')
    magic,n,raw_size,expected=HEADER.unpack(packet[:HEADER.size])
    if magic!=b'MST1' or n!=len(packet)-HEADER.size or raw_size>max_payload_bytes:
        raise ValueError('Corrupt length/magic or payload exceeds receiver limit')
    d=zlib.decompressobj(); out=d.decompress(packet[HEADER.size:],raw_size+1)
    if not d.eof or d.unused_data or len(out)!=raw_size or hashlib.sha256(out).digest()!=expected:
        raise ValueError('Corrupt compressed payload/checksum')
    return out

def restore_cipher(stego,positions,original_lsb):
    out=stego.ravel().copy()
    values=unpack_pairs(original_lsb,len(positions))
    if len(values)!=len(positions): raise ValueError('Missing recovery bits')
    out[positions]=(out[positions]&252)|values
    return out.reshape(stego.shape)