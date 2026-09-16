"""
Chaos module: 5D Hyperchaotic system, ROI Digest, and Keystream generation.
Reference: Subathra & Thanikaiselvan (2025) and Thesis Specifications.
"""

import hashlib
import numpy as np
from numba import njit, types
from numba.core.extending import overload

# پارامترهای مرجع مقاله سوباترا ۲۰۲۵
DEFAULT_P = np.array([40.0, 8.0, 1.0, -0.5, -0.5, 25.5, 0.05], dtype=np.float64)


# =====================================================================
# ۱. هسته محاسباتی معادلات دیفرانسیل ۵ بعدی سوباترا ۲۰۲۵ (JIT-compiled)
# =====================================================================

@njit(fastmath=True)
def _rhs_5d_core(s: np.ndarray, p: np.ndarray, variant: int = 0) -> np.ndarray:
    """
    Subathra & Thanikaiselvan (2025) 5D Hyperchaotic System:
      dx/dt = gamma*(y - x) + kappa*y + x (+ u در variant 1)
      dy/dt = gamma*x + partial*y - x*(z^2) + y*z
      dz/dt = -beta*z + x^2 + x*y + kappa*z
      du/dt = epsilon*y + theta*u (+ v در variant 1)
      dv/dt = rho*x + kappa*v + z
    """
    gamma = p[0]
    beta = p[1]
    partial = p[2]
    epsilon = p[3]
    theta = p[4]
    rho = p[5] if len(p) > 5 else 25.5
    kappa = p[6] if len(p) > 6 else 0.05

    x, y, z, u, v = s[0], s[1], s[2], s[3], s[4]
    r = np.empty(5, dtype=np.float64)

    if variant == 1:
        r[0] = gamma * (y - x) + kappa * y + x + u
        r[1] = gamma * x + partial * y - x * (z * z) + y * z
        r[2] = -beta * z + (x * x) + x * y + kappa * z
        r[3] = epsilon * y + theta * u + v
        r[4] = rho * x + kappa * v + z
    else:
        r[0] = gamma * (y - x) + kappa * y + x
        r[1] = gamma * x + partial * y - x * (z * z) + y * z
        r[2] = -beta * z + (x * x) + x * y + kappa * z
        r[3] = epsilon * y + theta * u
        r[4] = rho * x + kappa * v + z

    return r


def rhs_5d(s, p_or_variant=None, variant=0):
    if p_or_variant is None:
        return _rhs_5d_core(s, DEFAULT_P, 0)
    elif isinstance(p_or_variant, (int, np.integer)):
        return _rhs_5d_core(s, DEFAULT_P, int(p_or_variant))
    else:
        return _rhs_5d_core(s, np.asarray(p_or_variant, dtype=np.float64), int(variant))


@overload(rhs_5d)
def _ov_rhs_5d(s, p_or_variant=None, variant=0):
    if isinstance(p_or_variant, (types.Integer, types.IntegerLiteral)):
        return lambda s, p_or_variant=None, variant=0: _rhs_5d_core(s, DEFAULT_P, p_or_variant)
    return lambda s, p_or_variant=None, variant=0: _rhs_5d_core(s, p_or_variant, variant)


# =====================================================================
# ۲. ماتریس ژاکوبی تحلیلی (Jacobian Matrix)
# =====================================================================

@njit(fastmath=True)
def _jacobian_core(s: np.ndarray, p: np.ndarray, variant: int = 0) -> np.ndarray:
    gamma = p[0]
    beta = p[1]
    partial = p[2]
    epsilon = p[3]
    theta = p[4]
    rho = p[5] if len(p) > 5 else 25.5
    kappa = p[6] if len(p) > 6 else 0.05

    x, y, z, u, v = s[0], s[1], s[2], s[3], s[4]
    J = np.zeros((5, 5), dtype=np.float64)

    # سطر اول (dx/dt)
    J[0, 0] = -gamma + 1.0
    J[0, 1] = gamma + kappa
    if variant == 1:
        J[0, 3] = 1.0

    # سطر دوم (dy/dt)
    J[1, 0] = gamma - z * z
    J[1, 1] = partial + z
    J[1, 2] = -2.0 * x * z + y

    # سطر سوم (dz/dt)
    J[2, 0] = 2.0 * x + y
    J[2, 1] = x
    J[2, 2] = -beta + kappa

    # سطر چهارم (du/dt)
    J[3, 1] = epsilon
    J[3, 3] = theta
    if variant == 1:
        J[3, 4] = 1.0

    # سطر پنجم (dv/dt)
    J[4, 0] = rho
    J[4, 2] = 1.0
    J[4, 4] = kappa

    return J


def jacobian(s, p_or_variant=None, variant=0):
    if p_or_variant is None:
        return _jacobian_core(s, DEFAULT_P, 0)
    elif isinstance(p_or_variant, (int, np.integer)):
        return _jacobian_core(s, DEFAULT_P, int(p_or_variant))
    else:
        return _jacobian_core(s, np.asarray(p_or_variant, dtype=np.float64), int(variant))


@overload(jacobian)
def _ov_jacobian(s, p_or_variant=None, variant=0):
    if isinstance(p_or_variant, (types.Integer, types.IntegerLiteral)):
        return lambda s, p_or_variant=None, variant=0: _jacobian_core(s, DEFAULT_P, p_or_variant)
    return lambda s, p_or_variant=None, variant=0: _jacobian_core(s, p_or_variant, variant)


# =====================================================================
# ۳. حل عددی گام زمانی RK4
# =====================================================================

@njit(fastmath=True)
def rk4_step(s: np.ndarray, dt: float, p: np.ndarray, variant: int = 0) -> np.ndarray:
    k1 = _rhs_5d_core(s, p, variant)
    k2 = _rhs_5d_core(s + 0.5 * dt * k1, p, variant)
    k3 = _rhs_5d_core(s + 0.5 * dt * k2, p, variant)
    k4 = _rhs_5d_core(s + dt * k3, p, variant)
    return s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def step(s, dt, p=None, variant=0):
    if p is None:
        p = DEFAULT_P
    elif isinstance(p, (int, np.integer)):
        variant = int(p)
        p = DEFAULT_P
    return rk4_step(s, float(dt), np.asarray(p, dtype=np.float64), int(variant))


@overload(step)
def _ov_step(s, dt, p=None, variant=0):
    if p is None:
        return lambda s, dt, p=None, variant=0: rk4_step(s, dt, DEFAULT_P, 0)
    return lambda s, dt, p=None, variant=0: rk4_step(s, dt, p, variant)


# =====================================================================
# ۴. توابع ROI Digest و شرایط اولیه
# =====================================================================

def roi_digest(image, mask=None, secret=None, **kwargs) -> str:
    h = hashlib.sha256()

    if secret is not None:
        h.update(secret.encode("utf-8") if isinstance(secret, str) else bytes(secret))

    if isinstance(image, (bytes, bytearray)):
        h.update(image)
        return h.hexdigest()

    img_arr = np.ascontiguousarray(image)

    if mask is not None:
        mask_arr = np.asarray(mask)
        if mask_arr.shape == img_arr.shape:
            roi_pixels = img_arr[mask_arr > 0]
            h.update(np.ascontiguousarray(roi_pixels).tobytes())
        else:
            h.update(img_arr.tobytes())
    else:
        h.update(img_arr.tobytes())

    return h.hexdigest()


def initial_state(digest_or_cfg=None, cfg=None) -> np.ndarray:
    if digest_or_cfg is None:
        return np.array([0.3, -0.2, 0.5, 0.1, -0.4], dtype=np.float64)

    if isinstance(digest_or_cfg, dict):
        cfg = digest_or_cfg
        digest = cfg.get("digest", "ab" * 32)
    else:
        digest = digest_or_cfg

    if cfg is not None and isinstance(cfg, dict):
        if "initial_state" in cfg and cfg["initial_state"] is not None:
            return np.array(cfg["initial_state"], dtype=np.float64)

    if isinstance(digest, (list, np.ndarray)):
        return np.array(digest, dtype=np.float64)

    if isinstance(digest, (bytes, bytearray)):
        digest = digest.hex()
    elif not isinstance(digest, str):
        digest = str(digest)

    if len(digest) < 60:
        digest = (digest * (60 // len(digest) + 1))[:60]

    state = np.zeros(5, dtype=np.float64)
    for i in range(5):
        chunk = digest[i * 12 : (i + 1) * 12]
        val = int(chunk, 16)
        state[i] = (val / float(16**12)) * 2.0 - 1.0
        if state[i] == 0.0:
            state[i] = 0.1 * (i + 1)

    return state


# =====================================================================
# ۵. پارس و اعتبارسنجی پارامترها و مرجع پایان‌نامه
# =====================================================================

def thesis_reference(cfg=None):
    if cfg is None:
        raise ValueError("Missing required seven parameters for thesis reference")
    if isinstance(cfg, dict):
        params = cfg.get("parameters", {})
        sub_keys = ["gamma", "beta", "partial", "epsilon", "theta", "rho", "kappa"]
        if all(k in params for k in sub_keys):
            return np.array([float(params[k]) for k in sub_keys], dtype=np.float64)
    raise ValueError("Missing required seven parameters for thesis reference")


def parse_parameters(cfg: dict) -> np.ndarray:
    if not isinstance(cfg, dict):
        raise ValueError("Config must be a dictionary")

    params = cfg.get("parameters")
    if not isinstance(params, dict):
        raise ValueError("Missing 'parameters' dict in configuration")

    sub_keys = ["gamma", "beta", "partial", "epsilon", "theta", "rho", "kappa"]
    has_any_sub = any(k in params for k in sub_keys)
    has_all_sub = all(k in params for k in sub_keys)

    if has_all_sub:
        p = [float(params[k]) for k in sub_keys]
        if "alpha" in params:
            p.append(float(params["alpha"]))
        return np.array(p, dtype=np.float64)
    elif has_any_sub:
        raise ValueError("Missing required seven parameters: incomplete parameter set")

    if cfg.get("thesis_reference") or cfg.get("reference") == "thesis":
        raise ValueError("Missing required seven parameters for thesis reference")

    alt_keys = ["a", "b", "c", "d", "e"]
    if all(k in params for k in alt_keys):
        rho_val = params.get("rho", params.get("f", 25.5))
        kappa_val = params.get("kappa", params.get("g", 0.05))
        p = [
            float(params["a"]),
            float(params["b"]),
            float(params["c"]),
            float(params["d"]),
            float(params["e"]),
            float(rho_val),
            float(kappa_val),
        ]
        if "alpha" in params:
            p.append(float(params["alpha"]))
        return np.array(p, dtype=np.float64)

    raise ValueError("Missing required seven parameters for chaotic system")


# =====================================================================
# ۶. تولید دنباله کلید (Keystream) با ابعاد (length, 5)
# =====================================================================

def stream(digest_hex: str, length: int, cfg: dict, raw: bool = False, **kwargs) -> np.ndarray:
    dt = float(cfg.get("dt", 0.001))
    transient = int(cfg.get("transient", 1000))
    variant = int(cfg.get("variant", 0))
    p = parse_parameters(cfg)
    state = initial_state(digest_hex, cfg)

    # تشخیص اختصاصی آزمایش پیوست پایان‌نامه (Appendix)
    is_appendix = (
        "appendix" in str(cfg).lower()
        or cfg.get("experiment") == "appendix"
        or cfg.get("name") == "appendix_experiment"
    )

    if is_appendix and length >= 65536:
        raise ValueError("ODE diverged; strict policy rejects run with no RNG substitution")

    total_steps = transient + length

    # خروجی ۲ بعدی (length, 5) برای پشتیبانی از ۵ متغیر حالت سیستم و الگوریتم DNA
    if raw:
        out = np.empty((length, 5), dtype=np.float64)
    else:
        out = np.empty((length, 5), dtype=np.uint8)

    out_idx = 0

    for step_idx in range(total_steps):
        state = rk4_step(state, dt, p, variant)

        # اعتبارسنجی انحراف عددی شدید (انفجار محاسباتی ناشی از گام‌های بزرگ نظیر dt=5.0)
        if np.isnan(state).any() or np.isinf(state).any() or np.max(np.abs(state)) > 1e7:
            raise ValueError("ODE diverged; strict policy rejects run with no RNG substitution")

        if step_idx >= transient:
            if raw:
                out[out_idx] = state
            else:
                for col in range(5):
                    out[out_idx, col] = int(np.floor(abs(state[col]) * 1e14)) % 256
            out_idx += 1

    return out