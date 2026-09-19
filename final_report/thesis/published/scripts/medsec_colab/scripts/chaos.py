"""Explicit ODE dispatch, float64 RK4, no clipping/reseeding/fastmath.

Restores the documented (digest, moments) contract. This is a research cipher,
not a cryptographic security claim; fixed-mask moment collisions remain visible.
"""
import hashlib
import json
import warnings
import numpy as np
from numba import njit
from .config import ode_parameters, system_variant

# Compatibility for direct diagnostic rhs_5d calls, never a config fallback.
DEFAULT_P = np.array([40., 8., 1., -.5, -.5, 25.5, .05])


def roi_digest(image, roi):
    if image.dtype != np.uint8 or image.ndim != 2 or roi.shape != image.shape or roi.dtype != bool:
        raise ValueError('Expected 2D uint8 and aligned boolean ROI')
    pixels = image[roi].astype(np.float64)
    if not pixels.size:
        raise ValueError('Empty ROI: no medical/key fallback is allowed')
    mu = float(pixels.mean()); centered = pixels - mu
    var = float(np.mean(centered**2))
    if var == 0:
        raise ValueError('Constant ROI: skewness/kurtosis undefined; report sample failure')
    features = [mu, var, float(np.mean(centered**3)/var**1.5), float(np.mean(centered**4)/var**2)]
    serial = '|'.join([format(x, '.17g') for x in features] + [str(image.shape[1]), str(image.shape[0])])
    return hashlib.sha256(serial.encode('ascii')).hexdigest(), features


def initial_state(digest, mapping='mod_1e8'):
    if isinstance(mapping, dict): mapping = mapping['hash_mapping']
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError('SHA256 digest must contain exactly 64 hex characters; no repetition/padding')
    raw = bytes.fromhex(digest)
    if len(raw) != 32: raise ValueError('SHA256 must be 32 bytes')
    if mapping == 'equation_byte_mean':
        return np.array([sum(raw[a:b])/((b-a)*255) for a, b in [(0,6),(6,12),(12,18),(18,24),(24,32)]])
    blocks = [int.from_bytes(raw[i:i+6], 'big') for i in range(0, 30, 6)]
    if mapping == 'mod_1e8': return np.array([v % 10**8 / 10**8 for v in blocks])
    if mapping == 'appendix_fraction': return np.array([v / 2**48 for v in blocks])
    raise ValueError('Unknown hash mapping')


@njit(cache=True)
def rhs(s, p, variant):
    """0=equation 3-2; 1=thesis appendix; 2=legacy Subathra-labelled diagnostic."""
    x, y, z, u, v = s
    r = np.empty(5, np.float64)
    a, b, c, d = p[:4]
    if variant == 2:
        theta, rho, kappa = p[4:7]
        r[0] = a*(y-x)+kappa*y+x
        r[1] = a*x+c*y-x*z*z+y*z
        r[2] = -b*z+x*x+x*y+kappa*z
        r[3] = d*y+theta*u
        r[4] = rho*x+kappa*v+z
    else:
        r[0] = a*(y-x)+u; r[1] = c*x-x*z+d*y+v; r[2] = x*y-b*z
        if variant == 0:
            r[3] = -p[4]*x; r[4] = p[5]*y-p[6]*v
        elif variant == 1:
            r[3] = -y*z+p[4]*u; r[4] = x*z-p[4]*v
        else: raise ValueError('Unknown ODE variant')
    return r


@njit(cache=True)
def system_jacobian(s, p, variant):
    x, y, z, u, v = s; a, b, c, d = p[:4]
    j = np.zeros((5, 5))
    if variant == 2:
        j[0,0] = -a+1; j[0,1] = a+p[6]
        j[1,0] = a-z*z; j[1,1] = c+z; j[1,2] = -2*x*z+y
        j[2,0] = 2*x+y; j[2,1] = x; j[2,2] = -b+p[6]
        j[3,1] = d; j[3,3] = p[4]
        j[4,0] = p[5]; j[4,2] = 1; j[4,4] = p[6]
    else:
        j[0,0] = -a; j[0,1] = a; j[0,3] = 1
        j[1,0] = c-z; j[1,1] = d; j[1,2] = -x; j[1,4] = 1
        j[2,0] = y; j[2,1] = x; j[2,2] = -b
        if variant == 0:
            j[3,0] = -p[4]; j[4,1] = p[5]; j[4,4] = -p[6]
        elif variant == 1:
            j[3,1] = -z; j[3,2] = -y; j[3,3] = p[4]
            j[4,0] = z; j[4,2] = x; j[4,4] = -p[4]
        else: raise ValueError('Unknown ODE variant')
    return j


# Legacy direct-call helpers retained; stream/dynamics use explicit system dispatch.
def rhs_5d(s, p=DEFAULT_P, variant=0):
    result = rhs(s, p, 2)
    if variant == 1: result[0] += s[3]; result[3] += s[4]
    return result


def jacobian(s, p=DEFAULT_P, variant=0):
    result = system_jacobian(s, p, 2)
    if variant == 1: result[0,3] = 1; result[3,4] = 1
    return result


@njit(cache=True)
def step(s, dt, p, variant):
    k1 = rhs(s,p,variant); k2 = rhs(s+dt*k1/2,p,variant)
    k3 = rhs(s+dt*k2/2,p,variant); k4 = rhs(s+dt*k3,p,variant)
    return s+dt*(k1+2*k2+2*k3+k4)/6


@njit(cache=True)
def integrate(s, n, transient, dt, p, variant):
    out = np.empty((n,5), np.float64)
    for i in range(n+transient):
        s = step(s,dt,p,variant)
        if not np.isfinite(s).all() or np.max(np.abs(s)) > 1e12:
            raise ValueError('ODE diverged/nonfinite at integration step '+str(i+1)+'; stopped, no RNG substitution')
        if i >= transient: out[i-transient] = s
    return out


def quantize_states(states, scale):
    values = np.abs(np.asarray(states, dtype=np.float64))*scale
    if not np.isfinite(values).all(): raise ValueError('Nonfinite quantization; no clipping allowed')
    if np.any(values > 2**53):
        warnings.warn('Quantization exceeds float64 exact-integer range; low-bit precision loss, not randomness', RuntimeWarning)
    return np.remainder(np.floor(values), 256).astype(np.uint8)


def stream(digest, n, cfg, raw=False):
    if not isinstance(n, (int, np.integer)) or n < 1: raise ValueError('Positive integer sample count required')
    p = ode_parameters(cfg)
    states = integrate(initial_state(digest, cfg['hash_mapping']), n, cfg['transient'], cfg['dt'], p, system_variant(cfg))
    return states if raw else quantize_states(states, cfg['scale'])


parse_parameters = ode_parameters


def environment_fingerprint(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()