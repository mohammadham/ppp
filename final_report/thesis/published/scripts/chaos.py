"""Float64 RK4; no fastmath, no random or solver fallback."""
import hashlib
import json
import numpy as np
from numba import njit
from .config import ode_parameters

def roi_digest(image, roi):
    if image.dtype != np.uint8 or image.ndim != 2 or roi.shape != image.shape:
        raise ValueError('Expected 2D uint8 and aligned mask')
    pixels = image[np.asarray(roi, dtype=bool)].astype(np.float64)
    if not pixels.size:
        raise ValueError('Empty ROI: no medical/key fallback is allowed')
    mu=float(pixels.mean()); centered=pixels-mu; var=float(np.mean(centered**2))
    if var == 0:
        raise ValueError('Constant ROI: skewness/kurtosis undefined; sample must be reported as failure')
    features=[mu, var, float(np.mean(centered**3)/var**1.5), float(np.mean(centered**4)/var**2)]
    # Population moments, Pearson kurtosis; canonical delimited 17-digit decimal representation.
    serial='|'.join([format(x,'.17g') for x in features]+[str(image.shape[1]),str(image.shape[0])])
    return hashlib.sha256(serial.encode('ascii')).hexdigest(), features

def initial_state(digest, mapping='mod_1e8'):
    raw=bytes.fromhex(digest)
    if len(raw)!=32: raise ValueError('SHA256 must be 32 bytes')
    if mapping=='equation_byte_mean':
        return np.array([sum(raw[a:b])/((b-a)*255) for a,b in [(0,6),(6,12),(12,18),(18,24),(24,32)]])
    blocks=[int.from_bytes(raw[i:i+6],'big') for i in range(0,30,6)]
    if mapping=='mod_1e8': return np.array([v%10**8/10**8 for v in blocks])
    if mapping=='appendix_fraction': return np.array([v/2**48 for v in blocks])
    raise ValueError('Unknown hash mapping')

@njit(cache=True)
def rhs(s, p, variant):
    x,y,z,u,v=s
    a,b,c,d=p[:4]
    r=np.empty(5,np.float64)
    r[0]=a*(y-x)+u; r[1]=c*x-x*z+d*y+v; r[2]=x*y-b*z
    if variant==0:
        r[3]=-p[4]*x; r[4]=p[5]*y-p[6]*v
    else:
        r[3]=-y*z+p[4]*u; r[4]=x*z-p[4]*v
    return r

@njit(cache=True)
def step(s, dt, p, variant):
    k1=rhs(s,p,variant); k2=rhs(s+dt*k1/2,p,variant)
    k3=rhs(s+dt*k2/2,p,variant); k4=rhs(s+dt*k3,p,variant)
    return s+dt*(k1+2*k2+2*k3+k4)/6

@njit(cache=True)
def integrate(s, n, transient, dt, p, variant):
    out=np.empty((n,5),np.float64)
    for i in range(n+transient):
        s=step(s,dt,p,variant)
        if not np.isfinite(s).all() or np.max(np.abs(s))>1e12:
            raise ValueError('ODE diverged/nonfinite; experiment stopped, no RNG substitution')
        if i>=transient: out[i-transient]=s
    return out

def stream(digest, n, cfg, raw=False):
    if n<1: raise ValueError('Positive sample count required')
    states=integrate(initial_state(digest,cfg['hash_mapping']), n, cfg['transient'], cfg['dt'],
                     ode_parameters(cfg), 0 if cfg['system']=='equation_3_2' else 1)
    if raw: return states
    # np.remainder BEFORE integer conversion avoids int64 overflow.
    return np.remainder(np.floor(np.abs(states)*cfg['scale']),256).astype(np.uint8)

def environment_fingerprint(cfg):
    return hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()