"""Finite-time Lyapunov spectrum: coupled variational RK4 with QR reorthogonalization.

Strict zero-divergence fallback policy; adheres to exact variational equations
and analytic Jacobian traces for all variants (0, 1, and Subathra 2025 variant 2).
"""
import numpy as np
from numba import njit
from .chaos import rhs, system_jacobian, step, initial_state
from .config import ode_parameters, system_variant
from .artifacts import environment, write_json


@njit(cache=True)
def variational_steps(
    s: np.ndarray,
    q: np.ndarray,
    count: int,
    dt: float,
    p: np.ndarray,
    variant: int,
):
    """Integrates state vector and tangent variational frame over 'count' steps.
    
    Coupled 4th-order Runge-Kutta integration of:
      ds/dt = f(s)
      dq/dt = J(s) * q
    """
    for _ in range(count):
        # Sub-step 1
        k1_s = rhs(s, p, variant)
        k1_q = system_jacobian(s, p, variant) @ q

        # Sub-step 2
        s_half1 = s + 0.5 * dt * k1_s
        q_half1 = q + 0.5 * dt * k1_q
        k2_s = rhs(s_half1, p, variant)
        k2_q = system_jacobian(s_half1, p, variant) @ q_half1

        # Sub-step 3
        s_half2 = s + 0.5 * dt * k2_s
        q_half2 = q + 0.5 * dt * k2_q
        k3_s = rhs(s_half2, p, variant)
        k3_q = system_jacobian(s_half2, p, variant) @ q_half2

        # Sub-step 4
        s_end = s + dt * k3_s
        q_end = q + dt * k3_q
        k4_s = rhs(s_end, p, variant)
        k4_q = system_jacobian(s_end, p, variant) @ q_end

        # State and tangent update
        s = s + (dt / 6.0) * (k1_s + 2.0 * k2_s + 2.0 * k3_s + k4_s)
        q = q + (dt / 6.0) * (k1_q + 2.0 * k2_q + 2.0 * k3_q + k4_q)

        if not np.isfinite(s).all() or not np.isfinite(q).all() or np.max(np.abs(s)) > 1e12:
            raise ValueError('Variational system diverged; no Lyapunov conclusion')

    return s, q


def lyapunov(digest, cfg, steps=100000, qr_interval=10, output=None):
    """Computes finite-time Lyapunov exponent spectrum using QR decomposition."""
    result = {
        'method': 'coupled_variational_RK4_QR_finite_time',
        'config': cfg,
        'digest': digest,
        'steps': steps,
        'qr_interval': qr_interval,
        'environment': environment(),
        'proof_of_hyperchaos': False,
    }
    try:
        if steps < 1 or qr_interval < 1:
            raise ValueError('Positive steps and QR interval required')

        p = ode_parameters(cfg)
        variant = system_variant(cfg)
        s = initial_state(digest, cfg['hash_mapping'])
        dt = float(cfg['dt'])

        # Transient elimination
        for _ in range(cfg['transient']):
            s = step(s, dt, p, variant)
            if not np.isfinite(s).all() or np.max(np.abs(s)) > 1e12:
                raise ValueError('Transient diverged')

        q = np.eye(5, dtype=np.float64)
        sums = np.zeros(5, dtype=np.float64)
        history = []
        phase = []
        amplitude = 0.0
        completed = 0

        while completed < steps:
            count = min(qr_interval, steps - completed)
            s, q = variational_steps(s, q, count, dt, p, variant)
            q, r = np.linalg.qr(q)
            diagonal = np.abs(np.diag(r))
            if (diagonal <= 0.0).any():
                raise ValueError('Singular tangent flow')

            sums += np.log(diagonal)
            completed += count
            amplitude = max(amplitude, float(np.abs(s).max()))

            if len(phase) < 5000:
                phase.append(s.tolist())
            if completed == steps or completed % (qr_interval * 100) == 0:
                history.append({'time': completed * dt, 'spectrum': (sums / (completed * dt)).tolist()})

        spectrum = sums / (steps * dt)
        j_final = system_jacobian(s, p, variant)
        result.update({
            'status': 'ok',
            'spectrum': spectrum.tolist(),
            'positive_count_finite_time': int((spectrum > 0).sum()),
            'convergence': history,
            'phase': phase,
            'max_abs_state': amplitude,
            'discretization_exceeds_float64_exact_integer_range': amplitude * cfg['scale'] > 2**53,
            'sum_spectrum': float(spectrum.sum()),
            'analytic_divergence': float(np.trace(j_final)),
        })
    except Exception as exc:
        result.update({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})

    if output:
        write_json(output, result)
    return result