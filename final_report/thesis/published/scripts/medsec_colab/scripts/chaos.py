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
    """
    تبدیل کلید هَش ۲۵۶ بیتی به شرایط اولیه نرمال‌شده در بازه مناسب جاذبه ۵بعدی
    """
    raw = bytes.fromhex(digest)
    if len(raw) != 32:
        raise ValueError('SHA256 must be 32 bytes')

    blocks = [int.from_bytes(raw[i:i+6], 'big') for i in range(0, 30, 6)]
    # نرمالisation شرایط اولیه به بازه [-2.0, 2.0] جهت قرارگیری درون جاذبه غریب
    states = np.array([(v % 10**8 / 10**8) * 4.0 - 2.0 for v in blocks], dtype=np.float64)
    return states

# ---------------------------------------------------------
# 3. تابع RHS سیستم ۵بعدی ابرآشوبی (مطابق مقاله سوباترا ۲۰۲۵)
# ---------------------------------------------------------
@njit(cache=True)
def rhs_5d(s, second=None, third=None):
    """5D hyperchaotic system RHS per Subathra & Thanikaiselvan (2025).

    Parameters
    ----------
    s : np.ndarray
        State vector [x, y, z, u, v]
    second : int or np.ndarray, optional
        If int: variant number (0 or 1)
        If np.ndarray: parameters p [a, b, c, d, e]
    third : int, optional
        Variant number (used when second is parameters array)
    """
    x, y, z, u, v = s

    # پارامترهای کنترلی مرجع مقاله سوباترا (Nature Sci Rep 2025)
    gamma = 40.0
    beta = 8.0
    partial = 1.0
    epsilon = -0.5
    vartheta = -0.5
    rho = 25.5
    kappa = 0.05

    # تشخیص فراخوانی بر اساس تعداد آرگومان‌ها
    if third is not None:
        # فراخوانی سه آرگومان: rhs_5d(s, p, variant)
        p = second
        variant = third
        # استفاده از فرمول‌های vintage با پارامترهای داده‌شده
        r = np.empty(5, dtype=np.float64)
        r[0] = p[0] * (y - x) + u
        r[1] = p[2] * x - x * z + p[3] * y + v
        r[2] = x * y - p[1] * z
        if variant == 0:
            r[3] = -p[3] * x
            r[4] = p[5] * y - p[6] * v
        else:
            r[3] = -y * z - p[3] * u
            r[4] = x * z - p[3] * v
        return r
    elif second is not None:
        # فراخوانی دو آرگومان: rhs_5d(s, variant)
        variant = second
        # استفاده از پارامترهای استاندارد سوباترا
        r = np.empty(5, dtype=np.float64)
        r[0] = gamma * (y - x) + kappa * y + x
        r[1] = gamma * x + partial * y - x * (z**2) + y * z
        r[2] = -beta * z + (x**2) + x * y + kappa * z
        r[3] = epsilon * y + vartheta * u
        r[4] = rho * x + kappa * v + z
        return r
    else:
        # فراخوانی یک آرگومان: rhs_5d(s)
        # استفاده از پارامترهای استاندارد سوباترا
        r = np.empty(5, dtype=np.float64)
        r[0] = gamma * (y - x) + kappa * y + x
        r[1] = gamma * x + partial * y - x * (z**2) + y * z
        r[2] = -beta * z + (x**2) + x * y + kappa * z
        r[3] = epsilon * y + vartheta * u
        r[4] = rho * x + kappa * v + z
        return r

# ---------------------------------------------------------
# 4. یک گام حل_numberی به روش رونگه-کوتا مرتبه ۴ (RK4)
# ---------------------------------------------------------
@njit(cache=True)
def step_rk4(s, dt):
    k1 = rhs_5d(s, 0)
    k2 = rhs_5d(s + 0.5 * dt * k1, 0)
    k3 = rhs_5d(s + 0.5 * dt * k2, 0)
    k4 = rhs_5d(s + dt * k3, 0)
    return s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

# ---------------------------------------------------------
# 5. انتگرالگیری پیوسته و تولید توالی‌های آشوبی
# ---------------------------------------------------------
@njit(cache=True)
def integrate_5d(s, n, transient=1000, dt=0.0005):
    out = np.empty((n, 5), dtype=np.float64)
    total_steps = n + transient

    for i in range(total_steps):
        s = step_rk4(s, dt)

        # بررسی پایداری
        if not np.isfinite(s).all() or np.max(np.abs(s)) > 1e5:
            raise ValueError('ODE diverged at step '+str(i+1)+'; stopped, no RNG substitution')

        if i >= transient:
            out[i - transient] = s

    return out

# ---------------------------------------------------------
# 6. تابع اصلی تولید توالی کلیدهای ۸ بیتی رمزی
# ---------------------------------------------------------
def stream(digest, n, cfg=None, transient=1000, dt=0.0005, scale=1e14, raw=False):
    """Generate 8-bit key stream from SHA-256 digest using Subathra & Thanikaiselvan (2025) 5D hyperchaos.

    Parameters
    ----------
    digest : str
        SHA-256 hex digest (32 bytes)
    n : int
        Number of key bytes to generate
    cfg : dict, optional
        Configuration dict with 'hash_mapping' key for old API compatibility
    transient : int, optional
        Number of transient steps to discard (default 1000)
    dt : float, optional
        Integration time step (default 0.0005)
    scale : float, optional
        Quantization scale for 8-bit conversion (default 1e14)
    raw : bool, optional
        If True, return raw integration states instead of quantized 8-bit keys (default False)

    Returns
    -------
    keys_8bit : np.ndarray
        Array of uint8 key bytes, shape (n,)
        Or raw states if raw=True
    """
    if cfg is not None and 'hash_mapping' in cfg:
        s0 = initial_state(digest, cfg['hash_mapping'])
    else:
        s0 = initial_state(digest)

    if raw:
        states = integrate_5d(s0, n, transient=transient, dt=dt)
        return states

    states = integrate_5d(s0, n, transient=transient, dt=dt)

    # گسسته‌سازی اعشاری به مقادیر بایر ۸ بیتی
    keys_8bit = np.remainder(np.floor(np.abs(states) * scale), 256).astype(np.uint8)
    return keys_8bit

# Old API: rhs(s, p, variant) for equation 3.2 and subathra variants.
# Defined separately from rhs_5d so that 'from scripts.chaos import rhs'
# gives callers the original 3-argument signature they expect.
@njit(cache=True)
def rhs(s, p, variant):
    x, y, z, u, v = s
    a, b, c, d = p[:4]
    r = np.empty(5, dtype=np.float64)
    r[0] = a * (y - x) + u
    r[1] = c * x - x * z + d * y + v
    r[2] = x * y - b * z
    if variant == 0:
        r[3] = -d * x
        r[4] = p[5] * y - p[6] * v
    else:
        r[3] = -y * z - d * u
        r[4] = x * z - d * v
    return r
# Backward-compatible aliases for old imports (dynamics.py, config.py, etc.)
step = step_rk4

# rhs = rhs_5d
# (defined separately so 'from scripts.chaos import rhs' works)
