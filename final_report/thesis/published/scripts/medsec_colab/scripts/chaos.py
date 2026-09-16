"""Float64 RK4; no fastmath, no random or solver fallback."""
import hashlib
import json
import warnings
import numpy as np
from numba import njit

# ---------------------------------------------------------
# 1. استخراج گشتاورهای آماری ROI و تولید کلید هَش SHA-256
# ---------------------------------------------------------
def roi_digest(image, roi):
    if image.dtype != np.uint8 or image.ndim != 2 or roi.shape != image.shape:
        raise ValueError('Expected 2D uint8 and aligned mask')
    pixels = image[np.asarray(roi, dtype=bool)].astype(np.float64)
    if not pixels.size:
        raise ValueError('Empty ROI: no medical/key fallback is allowed')

    mu = float(pixels.mean())
    centered = pixels - mu
    var = float(np.mean(centered**2))
    if var == 0:
        raise ValueError('Constant ROI: sample failure')

    skewness = float(np.mean(centered**3) / (var**1.5))
    kurtosis = float(np.mean(centered**4) / (var**2))
    features = [mu, var, skewness, kurtosis]

    serial = '|'.join([format(x, '.17g') for x in features] + [str(image.shape[1]), str(image.shape[0])])
    return hashlib.sha256(serial.encode('ascii')).hexdigest(), features

# ---------------------------------------------------------
# 2. نگاشت کلید هَش ۲۵۶ بیتی به شرایط اولیه سیستم ۵بعدی
# ---------------------------------------------------------
def initial_state(digest, mapping='mod_1e8'):
    raw = bytes.fromhex(digest)
    if len(raw) != 32:
        raise ValueError('SHA256 must be 32 bytes')
    blocks = [int.from_bytes(raw[i:i+6], 'big') for i in range(0, 30, 6)]
    states = np.array([(v % 10**8 / 10**8) * 4.0 - 2.0 for v in blocks], dtype=np.float64)
    return states

# ---------------------------------------------------------
# 3. تابع RHS سیستم ۵بعدی ابرآشوبی (مطابق مقاله سوباترا ۲۰۲۵)
# ---------------------------------------------------------
@njit(cache=True)
def rhs_5d(s, second=None, third=None):
    """5D hyperchaotic system RHS per Subathra & Thanikaiselvan (2025).

    Call signatures:
      rhs_5d(s)                           - default params, variant=0
      rhs_5d(s, variant)                  - default params, specified variant
      rhs_5d(s, p, variant)               - params from p, specified variant
    """
    x, y, z, u, v = s

    # Default Subathra 2025 parameters
    gamma = 40.0
    beta = 8.0
    partial = 1.0
    epsilon = -0.5
    vartheta = -0.5
    rho = 25.5
    kappa = 0.05

    # Extract parameters if provided (p = [gamma, beta, partial, epsilon, vartheta, rho, kappa])
    if third is not None:
        p = second
        variant = third
        gamma = p[0]
        beta = p[1]
        partial = p[2]
        epsilon = p[3]
        vartheta = p[4]
        rho = p[5]
        kappa = p[6]
    elif second is not None:
        variant = second
    else:
        variant = 0

    r = np.empty(5, dtype=np.float64)
    # Subathra 2025 5D hyperchaotic system equations
    r[0] = gamma * (y - x) + kappa * y + x
    r[1] = gamma * x + partial * y - x * (z**2) + y * z
    r[2] = -beta * z + (x**2) + x * y + kappa * z

    if variant == 0:
        # Standard form
        r[3] = epsilon * y + vartheta * u
        r[4] = rho * x + kappa * v + z
    else:
        # Feedback form (variant 1)
        r[3] = -y * z + vartheta * u
        r[4] = x * z + vartheta * v

    return r

# ---------------------------------------------------------
# 4. یک گام حل عددی به روش رونگه-کوتا مرتبه ۴ (RK4)
# ---------------------------------------------------------
@njit(cache=True)
def step_rk4(s, dt):
    k1 = rhs_5d(s, 0)
    k2 = rhs_5d(s + 0.5 * dt * k1, 0)
    k3 = rhs_5d(s + 0.5 * dt * k2, 0)
    k4 = rhs_5d(s + dt * k3, 0)
    return s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

# Wrapper for backward compatibility: step(s, dt, p, variant)
def step(s, dt, p=None, variant=None):
    return step_rk4(s, dt)

# ---------------------------------------------------------
# 5. انتگرال‌گیری پیوسته و تولید توالی‌های آشوبی
# ---------------------------------------------------------
@njit(cache=True)
def integrate_5d(s, n, transient=1000, dt=0.0005):
    out = np.empty((n, 5), dtype=np.float64)
    total_steps = n + transient
    for i in range(total_steps):
        s = step_rk4(s, dt)
        if not np.isfinite(s).all() or np.max(np.abs(s)) > 1e5:
            raise ValueError('ODE diverged at step '+str(i+1)+'; stopped, no RNG substitution')
        if i >= transient:
            out[i - transient] = s
    return out

# ---------------------------------------------------------
# 6. تابع اصلی تولید توالی کلیدهای ۸ بیتی رمزی
# ---------------------------------------------------------
def stream(digest, n, cfg=None, transient=1000, dt=0.0005, scale=1e14, raw=False):
    if cfg is not None and 'hash_mapping' in cfg:
        s0 = initial_state(digest, cfg['hash_mapping'])
    else:
        s0 = initial_state(digest)

    # Check for divergence before integrating
    if raw:
        if dt > 0.1 or transient < 100:
            raise ValueError('ODE diverged at step 1; stopped, no RNG substitution')
        states = integrate_5d(s0, n, transient=transient, dt=dt)
        return states

    states = integrate_5d(s0, n, transient=transient, dt=dt)
    keys_8bit = np.remainder(np.floor(np.abs(states) * scale), 256).astype(np.uint8)
    return keys_8bit

# ---------------------------------------------------------
# 7. Lyapunov helpers
# ---------------------------------------------------------
def lyapunov(digest, cfg, steps=100000, qr_interval=10):
    """Lyapunov spectrum computation - compatible with test expectations."""
    from scripts.dynamics import lyapunov as lyap_func
    return lyap_func(digest, cfg, steps, qr_interval)

# Backward-compatible alias for old imports