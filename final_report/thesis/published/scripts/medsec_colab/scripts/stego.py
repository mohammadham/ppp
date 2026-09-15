import hashlib
import struct
import zlib
import numpy as np
from scipy.ndimage import uniform_filter, gaussian_filter

HEADER=struct.Struct('>4sQQ32s')

class CapacityError(ValueError):
    def __init__(self, required_bits, available_bits):
        self.details = {'error_code': 'NO_ELIGIBLE_PIXELS' if available_bits == 0 else 'INSUFFICIENT_CAPACITY',
                        'required_bits': required_bits, 'available_bits': available_bits,
                        'embedded_bits': 0, 'roi_protection_relaxed': False}
        guidance = ('No eligible background remains: inspect segmentation and mask conventions; do not bypass ROI protection.'
                    if available_bits == 0 else 'Packet including framing does not fit; choose a documented smaller payload or report failure.')
        super().__init__(f'Insufficient capacity: need {required_bits} bits; available {available_bits}; nothing embedded. {guidance}')

def saliency(image,cfg):
    freq=np.fft.fft2(image.astype(np.float64))
    logamp=np.log(np.maximum(np.abs(freq),np.finfo(np.float64).eps))
    residual=logamp-uniform_filter(logamp,size=cfg['saliency_filter'],mode='reflect')
    spatial=np.abs(np.fft.ifft2(np.exp(residual+1j*np.angle(freq))))**2
    return gaussian_filter(spatial,cfg['saliency_sigma'])

def embedding_mask(cipher,protected,cfg):
    if protected.dtype != bool or protected.shape != cipher.shape: raise ValueError('Boolean aligned protected mask required')
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
    if cipher.dtype != np.uint8 or cipher.ndim != 2 or eligible.dtype != bool: raise ValueError('2D uint8 and boolean mask required')
    if not isinstance(payload, bytes): raise ValueError('Payload must be bytes')
    compressed=zlib.compress(payload,level=cfg['compression_level'])
    packet=HEADER.pack(b'MST1',len(compressed),len(payload),hashlib.sha256(payload).digest())+compressed
    positions=np.flatnonzero(eligible.ravel())
    needed=len(packet)*4
    if needed>positions.size:
        raise CapacityError(needed*2, int(positions.size)*2)
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
    positions=np.asarray(positions)
    if stego.dtype != np.uint8 or stego.ndim != 2: raise ValueError('2D uint8 stego required')
    if positions.ndim != 1 or positions.dtype.kind not in 'iu' or (positions<0).any() or (positions>=stego.size).any():
        raise ValueError('Invalid extraction positions')
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
    if len(original_lsb) != (len(positions)*2+7)//8: raise ValueError('Recovery bit length mismatch')
    out=stego.ravel().copy()
    values=unpack_pairs(original_lsb,len(positions))
    if len(values)!=len(positions): raise ValueError('Missing recovery bits')
    out[positions]=(out[positions]&252)|values
    return out.reshape(stego.shape)