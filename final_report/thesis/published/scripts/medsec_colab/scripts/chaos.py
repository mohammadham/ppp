"""
Chaos module: Implements the 5D hyperchaotic system and dynamic DNA key generation.
Reference: Subathra & Thanikaiselvan (2025).
"""

import numpy as np
from numba import njit


@njit(fastmath=True)
def rhs_5d_subathra(s: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Canonical 5D Hyperchaotic System (Subathra & Thanikaiselvan, 2025 - Variant 0).

    State variables: x, y, z, u, v = s[0], s[1], s[2], s[3], s[4]
    Parameters:
      p[0] = gamma   (40.0)
      p[1] = beta    (8.0)
      p[2] = partial (1.0)
      p[3] = epsilon (-0.5)
      p[4] = theta   (-0.5)
      p[5] = rho     (25.5)
      p[6] = kappa   (0.05)
    """
    gamma = p[0]
    beta = p[1]
    partial = p[2]
    epsilon = p[3]
    theta = p[4]
    rho = p[5]
    kappa = p[6]
    alpha = 40.0 if len(p) <= 7 else p[7]

    x, y, z, u, v = s[0], s[1], s[2], s[3], s[4]
    r = np.empty(5, dtype=np.float64)

    r[0] = gamma * (y - x) + kappa * y + x
    r[1] = gamma * x + partial * y - x * (z**2) + y * z
    r[2] = -beta * z + (x**2) + x * y + kappa * z
    r[3] = epsilon * y + theta * alpha * u
    r[4] = rho * x + kappa * v + z
    return r


@njit(fastmath=True)
def rhs_5d_feedback(s: np.ndarray, p: np.ndarray) -> np.ndarray:
    """5D Hyperchaotic System with feedback coupling (Variant 1)."""
    gamma = p[0]
    beta = p[1]
    partial = p[2]
    epsilon = p[3]
    theta = p[4]
    rho = p[5]
    kappa = p[6]
    alpha = 40.0 if len(p) <= 7 else p[7]

    x, y, z, u, v = s[0], s[1], s[2], s[3], s[4]
    r = np.empty(5, dtype=np.float64)

    r[0] = gamma * (y - x) + kappa * y + x + u
    r[1] = gamma * x + partial * y - x * (z**2) + y * z
    r[2] = -beta * z + (x**2) + x * y + kappa * z
    r[3] = epsilon * y + theta * alpha * u + v
    r[4] = rho * x + kappa * v + z
    return r


@njit(fastmath=True)
def rhs_5d(s: np.ndarray, p: np.ndarray, variant: int = 0) -> np.ndarray:
    """Unified dispatcher with strictly uniform signatures for Numba compatibility."""
    if variant == 1:
        return rhs_5d_feedback(s, p)
    return rhs_5d_subathra(s, p)


@njit(fastmath=True)
def jacobian(s: np.ndarray, p: np.ndarray, variant: int = 0) -> np.ndarray:
    """Analytical Jacobian Matrix corresponding to Subathra 2025 equations."""
    gamma = p[0]
    beta = p[1]
    partial = p[2]
    epsilon = p[3]
    theta = p[4]
    rho = p[5]
    kappa = p[6]
    alpha = 40.0 if len(p) <= 7 else p[7]

    x, y, z, u, v = s[0], s[1], s[2], s[3], s[4]
    J = np.zeros((5, 5), dtype=np.float64)

    # Row 0: dx/dt derivatives
    J[0, 0] = -gamma + 1.0
    J[0, 1] = gamma + kappa
    if variant == 1:
        J[0, 3] = 1.0

    # Row 1: dy/dt derivatives
    J[1, 0] = gamma - z**2
    J[1, 1] = partial + z
    J[1, 2] = -2.0 * x * z + y

    # Row 2: dz/dt derivatives
    J[2, 0] = 2.0 * x + y
    J[2, 1] = x
    J[2, 2] = -beta + kappa

    # Row 3: du/dt derivatives
    J[3, 1] = epsilon
    J[3, 3] = theta * alpha
    if variant == 1:
        J[3, 4] = 1.0

    # Row 4: dv/dt derivatives
    J[4, 0] = rho
    J[4, 2] = 1.0
    J[4, 4] = kappa

    return J


@njit(fastmath=True)
def rk4_step(
    s: np.ndarray, dt: float, p: np.ndarray, variant: int = 0
) -> np.ndarray:
    """Classical 4th Order Runge-Kutta numerical integration step."""
    k1 = rhs_5d(s, p, variant)
    k2 = rhs_5d(s + 0.5 * dt * k1, p, variant)
    k3 = rhs_5d(s + 0.5 * dt * k2, p, variant)
    k4 = rhs_5d(s + dt * k3, p, variant)
    return s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def parse_parameters(cfg: dict) -> np.ndarray:
    """Extract ordered parameter array matching Subathra 2025 definition."""
    params = cfg.get("parameters", {})
    keys = ["gamma", "beta", "partial", "epsilon", "theta", "rho", "kappa"]
    if all(k in params for k in keys):
        p_list = [float(params[k]) for k in keys]
    elif all(k in params for k in ("a", "b", "c", "d", "e")):
        # Compatibility fallback for legacy mapped names
        p_list = [
            float(params.get("gamma", params["a"])),
            float(params.get("beta", params["b"])),
            float(params.get("partial", params.get("c", 1.0))),
            float(params.get("epsilon", -0.5)),
            float(params.get("theta", -0.5)),
            float(params.get("rho", 25.5)),
            float(params.get("kappa", 0.05)),
        ]
    else:
        # Standard Subathra (2025) baseline defaults
        p_list = [40.0, 8.0, 1.0, -0.5, -0.5, 25.5, 0.05]

    if "alpha" in params:
        p_list.append(float(params["alpha"]))
    return np.array(p_list, dtype=np.float64)


def stream(digest_hex: str, length: int, cfg: dict) -> np.ndarray:
    """Generate pseudo-random keystream from SHA-256 digest and 5D Hyperchaos."""
    dt = float(cfg.get("dt", 0.001))
    transient = int(cfg.get("transient", 1000))
    variant = int(cfg.get("variant", 0))
    p = parse_parameters(cfg)

    # Initial state derivation from digest
    raw_bytes = bytes.fromhex(digest_hex)
    init_state = np.zeros(5, dtype=np.float64)
    for i in range(5):
        chunk = raw_bytes[i * 6 : (i + 1) * 6]
        val = int.from_bytes(chunk, "big")
        init_state[i] = (val / float(1 << 48)) * 2.0 - 1.0

    state = init_state.copy()

    # Integration loop
    total_steps = transient + length
    out = np.empty(length, dtype=np.uint8)
    out_idx = 0

    for step in range(total_steps):
        state = rk4_step(state, dt, p, variant)

        # Numerical stability & divergence assertion
        if (
            np.isnan(state).any()
            or np.isinf(state).any()
            or np.max(np.abs(state)) > 1e7
        ):
            if cfg.get("experiment") == "appendix" or length >= 65536:
                raise ValueError("ODE diverged during numerical integration")
            raise ValueError(
                "ODE diverged; strict policy rejects run with no RNG substitution"
            )

        if step >= transient:
            # Scale x state to uint8
            raw_val = int(np.floor(abs(state[0]) * 1e14)) % 256
            out[out_idx] = raw_val
            out_idx += 1

    return out