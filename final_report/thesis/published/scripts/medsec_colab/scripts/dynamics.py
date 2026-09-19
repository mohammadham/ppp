"""Finite-time Lyapunov spectrum: coupled variational RK4 with QR reorthogonalization."""
import numpy as np
from numba import njit
from .chaos import rhs as rhs_5d, system_jacobian as jacobian, step, initial_state
from .config import ode_parameters, system_variant
from .artifacts import environment, write_json


# @njit(cache=True)
# def jacobian(s, p, variant):
#     x, y, z, u, v = s
#     a, b, c, d = p[:4]
#     j = np.zeros((5, 5))
#     j[0, 0] = -a; j[0, 1] = a; j[0, 3] = 1
#     j[1, 0] = c-z; j[1, 1] = d; j[1, 2] = -x; j[1, 4] = 1
#     j[2, 0] = y; j[2, 1] = x; j[2, 2] = -b
#     if variant == 0:
#         j[3, 0] = -p[4]; j[4, 1] = p[5]; j[4, 4] = -p[6]
#     else:
#         j[3, 1] = -z; j[3, 2] = -y; j[3, 3] = p[4]
#         j[4, 0] = z; j[4, 2] = x; j[4, 4] = -p[4]
#     return j

"""
Dynamics analysis: Variational equations and Lyapunov tracking via QR decomposition.
"""



@njit(cache=True)
def variational_steps(
    s: np.ndarray,
    q: np.ndarray,
    count: int,
    dt: float,
    p: np.ndarray,
    variant: int = 0,
):
    """Integrates state vector and tangent variational frame over 'count' steps."""
    for _ in range(count):
        # 1. State derivative and tangent linearization
        a = rhs_5d(s, p, variant)
        A = jacobian(s, p, variant) @ q

        # Runge-Kutta 4th order for coupled variational equations
        k1_s = a
        k1_q = A

        s_half1 = s + 0.5 * dt * k1_s
        q_half1 = q + 0.5 * dt * k1_q
        k2_s = rhs_5d(s_half1, p, variant)
        k2_q = jacobian(s_half1, p, variant) @ q_half1

        s_half2 = s + 0.5 * dt * k2_s
        q_half2 = q + 0.5 * dt * k2_q
        k3_s = rhs_5d(s_half2, p, variant)
        k3_q = jacobian(s_half2, p, variant) @ q_half2

        s_end = s + dt * k3_s
        q_end = q + dt * k3_q
        k4_s = rhs_5d(s_end, p, variant)
        k4_q = jacobian(s_end, p, variant) @ q_end

        s = s + (dt / 6.0) * (k1_s + 2.0 * k2_s + 2.0 * k3_s + k4_s)
        q = q + (dt / 6.0) * (k1_q + 2.0 * k2_q + 2.0 * k3_q + k4_q)

        # QR belongs to the caller: discarding R here destroys all growth rates.
        if not np.isfinite(s).all() or not np.isfinite(q).all() or np.max(np.abs(s)) > 1e12:
            raise ValueError('Variational system diverged; no Lyapunov conclusion')

    return s, q

def lyapunov(digest, cfg, steps=100000, qr_interval=10, output=None):
    result = {'method': 'coupled_variational_RK4_QR_finite_time', 'config': cfg, 'digest': digest,
              'steps': steps, 'qr_interval': qr_interval, 'environment': environment(), 'proof_of_hyperchaos': False}
    try:
        if steps < 1 or qr_interval < 1: raise ValueError('Positive steps and QR interval required')
        p = ode_parameters(cfg); variant = system_variant(cfg)
        s = initial_state(digest, cfg['hash_mapping']); dt = cfg['dt']
        for _ in range(cfg['transient']):
            s = step(s, dt, p, variant)
            if not np.isfinite(s).all() or np.max(np.abs(s)) > 1e12: raise ValueError('Transient diverged')
        q = np.eye(5); sums = np.zeros(5); history = []; phase = []; amplitude = 0.
        completed = 0
        while completed < steps:
            count = min(qr_interval, steps-completed)
            s, q = variational_steps(s, q, count, dt, p, variant)
            q, r = np.linalg.qr(q); diagonal = np.abs(np.diag(r))
            if (diagonal <= 0).any(): raise ValueError('Singular tangent flow')
            sums += np.log(diagonal); completed += count; amplitude = max(amplitude, float(np.abs(s).max()))
            if len(phase) < 5000: phase.append(s.tolist())
            if completed == steps or completed % (qr_interval*100) == 0:
                history.append({'time': completed*dt, 'spectrum': (sums/(completed*dt)).tolist()})
        spectrum = sums/(steps*dt)
        result.update({'status': 'ok', 'spectrum': spectrum.tolist(), 'positive_count_finite_time': int((spectrum > 0).sum()),
                       'convergence': history, 'phase': phase, 'max_abs_state': amplitude,
                       'discretization_exceeds_float64_exact_integer_range': amplitude*cfg['scale'] > 2**53,
                       'sum_spectrum': float(spectrum.sum()), 'analytic_divergence': float(np.trace(jacobian(s, p, variant)))})
    except Exception as exc: result.update({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
    if output: write_json(output, result)
    return result