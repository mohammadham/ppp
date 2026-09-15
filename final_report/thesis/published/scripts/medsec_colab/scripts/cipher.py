"""Chapter 3 pseudocode and separately selected equation-feedback interpretation."""
from functools import lru_cache
import numpy as np
from .chaos import roi_digest, stream

# A=0, C=1, G=2, T=3. Rows map bit pairs 00,01,10,11 to DNA bases.
RULES=np.array([[0,1,2,3],[0,2,1,3],[1,0,3,2],[1,3,0,2],
                [2,0,3,1],[2,3,0,1],[3,1,2,0],[3,2,1,0]],dtype=np.uint8)
INVERSE=np.argsort(RULES,axis=1).astype(np.uint8)

@lru_cache(maxsize=16)
def zigzag_indices(h,w):
    indices=[]
    for diagonal in range(h+w-1):
        rows=range(max(0,diagonal-w+1),min(h-1,diagonal)+1)
        if diagonal%2==0: rows=reversed(rows)
        indices.extend(r*w+diagonal-r for r in rows)
    out=np.array(indices,dtype=np.int64); out.flags.writeable=False
    return out

def encode_dna(values,rules):
    pairs=(np.asarray(values,dtype=np.uint8)[:,None]>>np.array([6,4,2,0],dtype=np.uint8))&3
    return RULES[np.asarray(rules)[:,None],pairs]

def decode_dna(bases,rules):
    pairs=INVERSE[np.asarray(rules)[:,None],bases]
    return np.sum(pairs.astype(np.uint16)<<np.array([6,4,2,0]),axis=1).astype(np.uint8)

def dna_transform(values,keys,variant,inverse=False):
    rules=keys[:,0]%8
    bases=encode_dna(values,rules); key=encode_dna(keys[:,1],rules)
    flip=(keys[:,2]%2==1) if variant=='pseudocode_3_3' else (keys[:,2]>128)
    if variant=='equation_3_3_feedback' and inverse:
        # C[-1]=AAAA is an explicit convention, absent from the equation.
        previous=np.vstack((np.zeros((1,4),dtype=np.uint8),bases[:-1]))
        bases=bases^previous
    result=bases^key^(flip[:,None].astype(np.uint8)*3)
    if variant=='equation_3_3_feedback' and not inverse:
        result=np.bitwise_xor.accumulate(result,axis=0)
    return decode_dna(result,rules)

def encrypt(image,roi,cfg,digest=None):
    if image.ndim!=2 or image.dtype!=np.uint8: raise ValueError('2D uint8 only')
    if roi.shape != image.shape or roi.dtype != bool: raise ValueError('Boolean aligned ROI required')
    digest=digest or roi_digest(image,roi)[0]
    keys=stream(digest,image.size,cfg)
    idx=zigzag_indices(*image.shape) if not cfg.get('no_zigzag') else np.arange(image.size)
    permuted=image.ravel()[idx]
    cipher=permuted if cfg.get('no_dna') else dna_transform(permuted,keys,cfg['dna_variant'])
    return cipher.reshape(image.shape),digest

def decrypt(cipher,digest,cfg):
    if cipher.ndim != 2 or cipher.dtype != np.uint8: raise ValueError('2D uint8 cipher required')
    keys=stream(digest,cipher.size,cfg)
    idx=zigzag_indices(*cipher.shape) if not cfg.get('no_zigzag') else np.arange(cipher.size)
    flat=cipher.ravel() if cfg.get('no_dna') else dna_transform(cipher.ravel(),keys,cfg['dna_variant'],True)
    plain=np.empty(cipher.size,np.uint8); plain[idx]=flat
    return plain.reshape(cipher.shape)

def protected_mask(roi,cfg):
    idx=zigzag_indices(*roi.shape) if not cfg.get('no_zigzag') else np.arange(roi.size)
    moved=roi.ravel()[idx].reshape(roi.shape)
    if cfg['roi_coordinates']=='permuted_union_original': return moved|roi
    if cfg['roi_coordinates']=='original': return roi.copy()
    raise ValueError('Unknown ROI coordinate convention')